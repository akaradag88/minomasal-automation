"""MinoMasal izole Tosbi onizlemesi: 1 Sami istegi, yerel kelime zamanlari.

Guvenlik: yayin yapmaz; minomasal.py ve durum dosyalarini degistirmez.
"""
import asyncio
from copy import deepcopy
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import unicodedata
import wave

import requests
from google import genai
from google.genai import types
import minomasal as mm

TOPIC = "Minik Kaplumbağanın Kayıp Yıldızı"
CHARACTER_FILE = Path("minomasal_karakterler.json")


def prepare_test_story():
    data = json.loads(CHARACTER_FILE.read_text(encoding="utf-8"))
    turtle = data["characters"]["kaplumbaga"]
    name, appearance = turtle["name"], turtle["appearance_en"]
    prompt = f'''4-8 yaş çocuklar için Türkçe mini masal yaz. Konu: {TOPIC}.
Ana karakter SADECE {name} adlı kaplumbağadır. Adını ASLA değiştirme.
Görünüşü (değiştirme): {appearance}
Tam 6 sahne. Toplam narration 45-65 Türkçe kelime.
Her sahnede tek, kısa, rahat okunabilecek cümle olsun.
Ana karakterin adı yalnızca {name} olsun, başka özel karakter adı üretme.
Visual alanı İngilizce yazılsın; {name} her sahnede aynı anatomide ve kıyafette görünsün.
Korkutucu içerik olmasın. Yalnız JSON döndür.
Şema: {{"title":"...","moral":"...","characters":"{appearance}",
"scenes":[{{"narration":"...","visual":"...","sfx":"none"}}]}}'''
    for _ in range(3):
        r = requests.post(
            "https://gen.pollinations.ai/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["POLLINATIONS_API_KEY"]},
            json={"model": mm.HIKAYE_MODELI,
                  "messages": [{"role": "user", "content": prompt}],
                  "response_format": {"type": "json_object"}},
            timeout=150,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        story = mm.validate(json.loads(raw))
        narration = " ".join(s["narration"] for s in story["scenes"])
        count = len(narration.split())
        if len(story["scenes"]) != 6 or not 45 <= count <= 65:
            print("Hikâye kurallara uymadı, yeniden deneniyor.")
            continue
        if not re.search(r"\b" + re.escape(name) + r"\b", narration, re.IGNORECASE):
            print("Karakter adı yok, yeniden deneniyor.")
            continue
        story["characters"] = appearance
        for scene in story["scenes"]:
            scene["visual"] = f"{name} the turtle. {appearance} {scene['visual']}"
        print("Karakter:", name, "Sahne:", len(story["scenes"]), "Kelime:", count)
        return story
    raise RuntimeError("Üç denemede geçerli Tosbi hikâyesi üretilemedi.")


def _normalize(token):
    token = token.replace("İ", "i").replace("I", "ı").lower()
    token = unicodedata.normalize("NFKD", token).replace("ı", "i")
    return "".join(ch for ch in token if ch.isalnum() and not unicodedata.combining(ch))


def _timestamp_words(full_wav, expected_tokens):
    """Whisper'in yerel kelime zamanlarını, ONAYLANMIŞ metindeki kelimelerle eşle."""
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=2)
    segments, _ = model.transcribe(
        str(full_wav), language="tr", beam_size=5,
        word_timestamps=True, vad_filter=False,
        condition_on_previous_text=False,
    )
    observed = []
    for segment in segments:
        for word in (segment.words or []):
            if word.start is not None and word.end is not None and _normalize(word.word):
                observed.append((word.word, float(word.start), float(word.end)))
    if not observed:
        raise RuntimeError("Yerel konuşma tanıma hiçbir kelime zamanlaması bulamadı.")

    left = [_normalize(t) for t in expected_tokens]
    right = [_normalize(w[0]) for w in observed]
    matched = {}
    for block in SequenceMatcher(None, left, right, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            matched[block.a + k] = observed[block.b + k][1:3]

    coverage = len(matched) / max(1, len(expected_tokens))
    print(f"Konuşma/metin eşleşmesi: %{coverage * 100:.1f} ({len(matched)}/{len(expected_tokens)})")
    if coverage < 0.78:
        raise RuntimeError(
            "Ses ile hikâye metni yeterince eşleşmedi. "
            "Yanlış altyazı oluşturmamak için test durduruldu."
        )

    total = mm.duration(full_wav)
    times = [matched.get(i) for i in range(len(expected_tokens))]
    # Az sayıdaki tanınmayan kelimeyi iki doğru zaman işareti arasında konumlandır.
    i = 0
    while i < len(times):
        if times[i] is not None:
            i += 1
            continue
        start = i
        while i < len(times) and times[i] is None:
            i += 1
        left_time = times[start - 1][1] if start else 0.0
        right_time = times[i][0] if i < len(times) else total
        if right_time <= left_time:
            raise RuntimeError("Kelime zamanlarında tutarsızlık var; video üretilmedi.")
        count = i - start
        if right_time - left_time > max(2.0, count * 1.5):
            raise RuntimeError("Ses/metin hizalamasında uzun bir belirsiz aralık var; video üretilmedi.")
        for j in range(count):
            times[start + j] = (
                left_time + (right_time - left_time) * j / count,
                left_time + (right_time - left_time) * (j + 1) / count,
            )
    return times, total


async def scene_voices(story, folder):
    """TEK Sami API isteği; sahne ve altyazı bölmeleri yerel zamanlamadan."""
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


async def main():
    assert mm.KISA_MASAL_TEST, "MINOMASAL_30SN_TEST=true olmalı"
    assert not mm.YAYIN_AKTIF, "Bu test hiçbir zaman yayın yapmamalıdır"
    story = prepare_test_story()
    # Yalnız bu işlem için; repodaki günlük yayın kodu değişmez.
    mm.voices = scene_voices
    video = await mm.produce(TOPIC, supplied_story=story)
    print("Video süresi:", round(mm.duration(video), 2), "saniye")
    print("Video yolu:", video)
    print("Yayın yapılmadı. Altyazı zamanları yerel konuşma tanımadan türetildi.")


if __name__ == "__main__":
    asyncio.run(main())
