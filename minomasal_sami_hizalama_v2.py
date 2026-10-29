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


def _timestamp_words(full_wav, expected_tokens):
    """İlk önce hızlı, gerekirse daha doğru modelle Türkçe kelime zamanlarını çıkar."""
    from faster_whisper import WhisperModel
    if not expected_tokens:
        raise RuntimeError('Hikâyenin anlatım metni boş.')
    total = mm.duration(full_wav)
    best = None
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
            continue
        for variant in _expected_variants(expected_tokens):
            mapped = _match_times(variant, observed)
            coverage = len(mapped) / len(expected_tokens)
            candidate = (coverage, mapped, observed, model_name)
            if best is None or coverage > best[0]:
                best = candidate
        if best and best[0] >= 0.76:
            break
    if best is None:
        raise RuntimeError('Sesten kelime zamanları elde edilemedi; yayın durduruldu.')

    coverage, matched, observed, model_name = best
    print(f'Ses/metin eşleşmesi ({model_name}, sayılar + benzer kelimeler): %{coverage*100:.1f} '
          f'({len(matched)}/{len(expected_tokens)})')
    if coverage < 0.72:
        preview = ' '.join(w for w,_,_ in observed)[:550]
        print('Whisper tanıdığı metin (ilk 550 karakter):', preview)
        raise RuntimeError('Ses/hikâye metni yeterince eşleşmedi; yanlış video yayını engellendi.')

    times = [matched.get(i) for i in range(len(expected_tokens))]
    i = 0
    while i < len(times):
        if times[i] is not None:
            i += 1
            continue
        start = i
        while i < len(times) and times[i] is None:
            i += 1
        left_time = times[start-1][1] if start else 0.0
        right_time = times[i][0] if i < len(times) else total
        gap = right_time - left_time
        count = i-start
        if gap <= 0 or gap > max(3.2, count * 1.5):
            raise RuntimeError('Kelime zamanlarında uzun veya ters yönde belirsizlik var; yayın durduruldu.')
        for j in range(count):
            times[start+j] = (left_time+gap*j/count, left_time+gap*(j+1)/count)
    if any(a<0 or b>total+0.2 or b<a for a,b in times):
        raise RuntimeError('Ses zaman damgaları geçersiz; yayın durduruldu.')
    return times, total


async def aligned_scene_voices(story, folder):
    """Bir Gemini Sami cagrisi; sahne ve kelime sinirlari yerel hizalamayla."""
    folder.mkdir(parents=True, exist_ok=True)
    narrations = [s["narration"].strip() for s in story["scenes"]]
    script = " ".join(narrations)
    full_wav = folder / "sami_tam_masal.wav"

    if not full_wav.exists():
        def generate_once():
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            response = client.models.generate_content(
                model="gemini-3.8-flash-tts",
                contents=(
                    "# Style instructions\n"
                    "Türkçe çocuk masalı anlatıcısı gibi sıcak, anlaşılır ve doğal oku. "
                    "Yalnızca aşağıdaki metni sırayla ve eksiksiz seslendir. "
                    "Sahne cümleleri arasında kısa ve doğal durakla.\n"
                    "# Transcript\n" + script
                ),
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sami")
                        )
                    ),
                ),
            )
            if not response.candidates:
                raise RuntimeError("Sami ses yanıtı boş.")
            audio = next(
                (p.inline_data for p in response.candidates[0].content.parts
                 if p.inline_data and p.inline_data.data), None
            )
            if audio is None:
                raise RuntimeError("Sami ses verisi bulunamadı.")
            with wave.open(str(full_wav), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(audio.data)
        await asyncio.to_thread(generate_once)
        print("Sami: bütün hikâye TEK API isteğiyle üretildi.")

    scene_tokens = [text.split() for text in narrations]
    expected = [word for tokens in scene_tokens for word in tokens]
    times, total = await asyncio.to_thread(_timestamp_words, full_wav, expected)

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
        for token, (a, b) in zip(tokens, times[pos:pos+len(tokens)]):
            a = max(0.0, min(dur, a-begin))
            b = max(a, min(dur, b-begin))
            if b > a:
                stamps.append({"text": token, "start": a, "end": b})
        if len(stamps) != len(tokens):
            raise RuntimeError(f"{i+1}. sahnenin kelime zamanları eksik; işlem durduruldu.")
        out.append((path, dur, stamps))
        pos += len(tokens)
        print(f"Ses {i+1}/{len(scene_tokens)} hazır ({dur:.2f} sn), {len(stamps)} kelime hizalı")
    return out

