"""MinoMasal2: Gemini Sami tek ses üretimi + güvenli sözcük hizalama.
Günlük 34 numaralı özel hikâye tarafından kullanılır; yayın kararını iş akışı verir.
"""
import asyncio
from difflib import SequenceMatcher
import os
import re
from pathlib import Path
import unicodedata
import wave

from google import genai
from google.genai import types
import minomasal as mm

def _normalize(token):
    token = token.replace("İ", "i").replace("I", "ı").lower()
    token = unicodedata.normalize("NFKD", token).replace("ı", "i")
    return "".join(ch for ch in token if ch.isalnum() and not unicodedata.combining(ch))


def _turkish_number(number):
    """Sayıların söylenişini eşleştir; örn. 29 -> yirmi dokuz, 1923 -> bin dokuz yüz yirmi üç."""
    units = ['', 'bir', 'iki', 'uc', 'dort', 'bes', 'alti', 'yedi', 'sekiz', 'dokuz']
    tens = ['', 'on', 'yirmi', 'otuz', 'kirk', 'elli', 'altmis', 'yetmis', 'seksen', 'doksan']
    if not 0 <= number <= 9999:
        return [str(number)]
    if number == 0:
        return ['sifir']
    output = []
    if number >= 1000:
        thousands = number // 1000
        if thousands > 1:
            output.append(units[thousands])
        output.append('bin')
        number %= 1000
    if number >= 100:
        hundreds = number // 100
        if hundreds > 1:
            output.append(units[hundreds])
        output.append('yuz')
        number %= 100
    if number >= 10:
        output.append(tens[number // 10])
        number %= 10
    if number:
        output.append(units[number])
    return output


def _expected_variants(tokens):
    """Tanınan '29' veya 'yirmi dokuz' biçimlerini ayrı ayrı dene."""
    plain = [(_normalize(token), i) for i, token in enumerate(tokens)]
    expanded = []
    for i, token in enumerate(tokens):
        normalized = _normalize(token)
        match = re.fullmatch(r'(\d{1,4})([a-z]*)', normalized)
        if match:
            n, ending = match.groups()
            spelled = _turkish_number(int(n))
            if ending:
                spelled[-1] += ending
            expanded.extend((part, i) for part in spelled)
        else:
            expanded.append((normalized, i))
    return [plain, expanded]


def _similarity(first, second):
    if first == second:
        return 1.0
    return SequenceMatcher(None, first, second, autojunk=False).ratio()


def _match_times(expected, observed):
    """Metin ve tanınan ses sözcüklerini sıralamayı bozmadan bulanık eşleştir."""
    left = [w for w, _ in expected]
    right = [_normalize(w) for w, _, _ in observed]
    m, n = len(left), len(right)
    dp = [[0.0] * (n + 1) for _ in range(m + 1)]
    steps = [[''] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        dp[i][0] = i
        steps[i][0] = 'D'
    for j in range(1, n + 1):
        dp[0][j] = j
        steps[0][j] = 'I'
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            score = _similarity(left[i-1], right[j-1])
            substitution = dp[i-1][j-1] + ((1-score) if score >= 0.72 else 2.2)
            deletion = dp[i-1][j] + 1.0
            insertion = dp[i][j-1] + 1.0
            best = min(substitution, deletion, insertion)
            if substitution == best:
                steps[i][j] = 'M'
            elif deletion == best:
                steps[i][j] = 'D'
            else:
                steps[i][j] = 'I'
            dp[i][j] = best
    i, j = m, n
    matched = {}
    while i or j:
        step = steps[i][j]
        if step == 'M':
            if _similarity(left[i-1], right[j-1]) >= 0.72:
                source_index = expected[i-1][1]
                a,b = float(observed[j-1][1]),float(observed[j-1][2])
                if source_index in matched:
                    x,y = matched[source_index]
                    matched[source_index] = min(x,a), max(y,b)
                else:
                    matched[source_index] = a,b
            i -= 1
            j -= 1
        elif step == 'D':
            i -= 1
        elif step == 'I':
            j -= 1
        else:
            raise RuntimeError('Kelime hizalama algoritmasında beklenmeyen durum')
    return matched


def _fill_precise_times(matched, total, count):
    """Tam doğrulanabilen kelime zamanlarını doldur; kuşkulu aralıkları reddet."""
    times = [matched.get(i) for i in range(count)]
    anchors = [(i, pair) for i, pair in enumerate(times) if pair is not None]
    if not anchors:
        raise ValueError('Hiç eşleşen kelime bulunamadı.')
    previous_end = -0.01
    for i, (a, b) in anchors:
        if not 0 <= a <= b <= total + 0.2 or a < previous_end - 0.15:
            raise ValueError(f'{i}. kelimede geri dönen/geçersiz zaman: {a:.2f}-{b:.2f}')
        previous_end = b
    i = 0
    while i < len(times):
        if times[i] is not None:
            i += 1
            continue
        first = i
        while i < len(times) and times[i] is None:
            i += 1
        left = times[first-1][1] if first else 0.0
        right = times[i][0] if i < len(times) else total
        missing = i-first
        gap = right-left
        if gap <= 0 or gap > max(3.2, missing*1.5):
            raise ValueError(f'{missing} kelimelik belirsiz aralık: {gap:.2f} saniye')
        for j in range(missing):
            times[first+j] = (left+gap*j/missing, left+gap*(j+1)/missing)
    return times


def _scene_bounds_from_anchors(matched, scene_sizes, total):
    """Kelime-kelime zaman güvenilir değilse cümle bazlı güvenli kesim sınırı.

    Her sahnede en az yarı metni tanımadan tahmini kesim yapma.
    """
    from math import ceil
    offset = 0
    scene_anchors = []
    for scene_no, length in enumerate(scene_sizes, 1):
        anchors = [matched[i] for i in range(offset, offset+length) if i in matched]
        minimum = max(2, ceil(length*0.5))
        if len(anchors) < minimum:
            raise ValueError(f'{scene_no}. sahnede yalnız {len(anchors)}/{length} kelime eşleşti')
        scene_anchors.append((anchors[0][0], anchors[-1][1]))
        offset += length
    borders = [0.0]
    for (left_start, left_end), (right_start, right_end) in zip(scene_anchors, scene_anchors[1:]):
        if right_start < left_end - 0.18:
            raise ValueError('Sahne sınırlarında çakışan veya ters zaman damgası')
        border = (left_end+right_start)/2
        if border-borders[-1] < 0.75:
            raise ValueError('Sahne sınırları aşırı yakın')
        borders.append(border)
    borders.append(total)
    if any(b-a < 0.75 for a,b in zip(borders,borders[1:])):
        raise ValueError('Sahne sürelerinden en az biri güvenilmez')
    return borders


def _timestamp_words(full_wav, expected_tokens, scene_sizes):
    """Önce kelime hizalaması; olmazsa doğrulanmış sahne sınırları + cümle altyazısı.

    Altyazıyı sessizce zaman tahminiyle üretmez. Transkript gerçekten farklıysa durur.
    """
    from faster_whisper import WhisperModel
    if not expected_tokens or sum(scene_sizes) != len(expected_tokens):
        raise RuntimeError('Hikâyenin kelime/sahne listesi eksik veya bozuk.')
    total = mm.duration(full_wav)
    candidates = []
    for model_name in ('base', 'small'):
        model = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=2)
        segments, _ = model.transcribe(
            str(full_wav), language='tr', beam_size=5,
            word_timestamps=True, vad_filter=False,
            condition_on_previous_text=False,
        )
        observed = []
        for segment in segments:
            for word in (segment.words or []):
                if word.start is not None and word.end is not None and _normalize(word.word):
                    observed.append((word.word, float(word.start), float(word.end)))
        del model
        if not observed:
            print(f'[{model_name}] Whisper kelime bulamadı.')
            continue
        for variant_no, variant in enumerate(_expected_variants(expected_tokens)):
            mapped = _match_times(variant, observed)
            coverage = len(mapped)/len(expected_tokens)
            print(f'[{model_name} varyant {variant_no}] kelime eşleşmesi '
                  f'{len(mapped)}/{len(expected_tokens)} (%{coverage*100:.1f})')
            if coverage < 0.72:
                continue
            try:
                times = _fill_precise_times(mapped, total, len(expected_tokens))
                print(f'KELİME ALTYAZISI: {model_name} kontrolü geçti.')
                return times, total, 'word', None
            except ValueError as exc:
                print(f'[{model_name} varyant {variant_no}] kelime zamanlaması uygun değil: {exc}')
            try:
                bounds = _scene_bounds_from_anchors(mapped, scene_sizes, total)
                candidates.append((coverage, bounds, model_name))
                print(f'[{model_name}] sahne/cümle altyazısı için güvenilir sınırlar bulundu.')
            except ValueError as exc:
                print(f'[{model_name} varyant {variant_no}] sahne sınırları da reddedildi: {exc}')
        # Her iki modelin sonucunu değerlendirmeden sonlandırma: base modeli
        # yüksek eşleşme gösterse bile zamanları hatalı olabilir.
    if candidates:
        coverage, bounds, model_name = max(candidates, key=lambda row: row[0])
        print(f'ALTYAZI YEDEK MODU: {model_name}, %{coverage*100:.1f} eşleşme; '
              'kelime kelime değil, konuşmanın SAHNE SÜRESİ boyunca tam cümle gösterilecek.')
        return None, total, 'scene', bounds
    raise RuntimeError(
        'Sami kaydı metinle güvenle hizalanamadı; yanlış altyazı/yayın önlendi. '
        'Whisper eşleşme yüzdelerini ve TTS sesini incelemek gerekiyor.'
    )


async def aligned_scene_voices(story, folder):
    """Bir Gemini Sami cagrisi; sahne ve kelime sinirlari yerel hizalamayla."""
    folder.mkdir(parents=True, exist_ok=True)
    narrations = [s["narration"].strip() for s in story["scenes"]]
    script = " ".join(narrations)
    full_wav = folder / "sami_tam_masal.wav"

    
    if not full_wav.exists():
        from minomasal_sami_tts_interactions import create_sami_wav
        await asyncio.to_thread(create_sami_wav, script, full_wav)
        print("Sami: Gemini Interactions TTS tamamlandı.")


    scene_tokens = [text.split() for text in narrations]
    expected = [word for tokens in scene_tokens for word in tokens]
    times, total, mode, safe_bounds = await asyncio.to_thread(
        _timestamp_words, full_wav, expected, [len(tokens) for tokens in scene_tokens]
    )

    if mode == 'scene':
        boundaries = safe_bounds
    else:
        boundaries = [0.0]
        current = 0
        for tokens in scene_tokens[:-1]:
            current += len(tokens)
            before = times[current - 1][1]
            after = times[current][0]
            boundary = max(boundaries[-1] + 0.1, min(total - 0.1, (before + after) / 2))
            boundaries.append(boundary)
        boundaries.append(total)

    out = []
    pos = 0
    for i, tokens in enumerate(scene_tokens):
        begin, end = boundaries[i], boundaries[i + 1]
        if end - begin < 0.5:
            raise RuntimeError(f"{i+1}. sahne aşırı kısa; kesim iptal edildi.")
        path = folder / f"ses_{i+1:02}.wav"
        if not path.exists():
            mm.run([
                "ffmpeg", "-y", "-loglevel", "error", "-i", full_wav,
                "-ss", f"{begin:.4f}", "-t", f"{end-begin:.4f}",
                "-ar", "24000", "-c:a", "pcm_s16le", path,
            ])
        dur = mm.duration(path)
        stamps = []
        if mode == 'scene':
            # Kelime hizalama güvenilir değilse, sahnenin TAM onaylı anlatımı
            # bu sahne boyunca görünür. Yanlış kelime sıçraması yaşanmaz.
            stamps = [{"text": narrations[i], "start": 0.0, "end": dur}]
        else:
            for token, (a, b) in zip(tokens, times[pos:pos+len(tokens)]):
                a = max(0.0, min(dur, a-begin))
                b = max(a, min(dur, b-begin))
                if b > a:
                    stamps.append({"text": token, "start": a, "end": b})
            if len(stamps) != len(tokens):
                raise RuntimeError(f"{i+1}. sahnenin kelime zamanları eksik; işlem durduruldu.")
        out.append((path, dur, stamps))
        pos += len(tokens)
        print(f"Ses {i+1}/{len(scene_tokens)} hazır ({dur:.2f} sn), altyazı modu: {mode}")
    return out

