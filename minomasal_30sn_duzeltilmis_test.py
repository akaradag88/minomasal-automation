"""MinoMasal: sadece yayinsiz Tosbi pilotu (mevcut yayin kodunu degistirmez)."""
import asyncio
import json
import os
import re
import wave
from pathlib import Path

import requests
from google import genai
from google.genai import types

import minomasal as mm

TOPIC = 'Minik Kaplumbağanın Kayıp Yıldızı'
CHARACTER_FILE = Path('minomasal_karakterler.json')


def prepare_test_story():
    data = json.loads(CHARACTER_FILE.read_text(encoding='utf-8'))
    turtle = data['characters']['kaplumbaga']
    name = turtle['name']
    appearance = turtle['appearance_en']
    prompt = f'''4-8 yas cocuklar icin Turkce mini masal yaz. Konu: {TOPIC}.
    Ana karakter SADECE {name} adli kaplumbagadir. Adini ASLA degistirme.
    Gorunusu (degistirme): {appearance}
    Tam 6 sahne olustur. Toplam narration 45-65 Turkce kelime.
    Her sahnede tek kisa ve sesle rahat okunabilecek cumle kullan.
    Anlatimda ayni ana karakteri {name} adi ile kullan; baska ozel karakter adi uretme.
    Visual degerleri Ingilizce olsun, her sahnede {name} karakterinin kaplumbaga
    anatomisini ve olayini tarif et. Korkutucu içerik olmasin.
    JSON disinda hiçbir sey dondurme.
    Sema: {{"title":"...","moral":"...","characters":"{appearance}",
    "scenes":[{{"narration":"...","visual":"...","sfx":"none"}}]}}'''
    for attempt in range(3):
        r = requests.post(
            'https://gen.pollinations.ai/v1/chat/completions',
            headers={'Authorization': 'Bearer ' + os.environ['POLLINATIONS_API_KEY']},
            json={'model': mm.HIKAYE_MODELI,
                  'messages': [{'role': 'user', 'content': prompt}],
                  'response_format': {'type': 'json_object'}},
            timeout=150,
        )
        r.raise_for_status()
        raw = r.json()['choices'][0]['message']['content'].strip()
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw)
        story = mm.validate(json.loads(raw))
        narration = ' '.join(s['narration'] for s in story['scenes'])
        word_count = len(narration.split())
        if len(story['scenes']) != 6 or not 45 <= word_count <= 65:
            print('Yeniden deneme: sahne/kelime sayisi', len(story['scenes']), word_count)
            continue
        if not re.search(r'\b' + re.escape(name) + r'\b', narration, flags=re.I):
            print('Yeniden deneme: Tosbi adi anlatimda yok')
            continue
        story['characters'] = appearance
        for scene in story['scenes']:
            scene['visual'] = f'{name} the turtle. {appearance} {scene["visual"]}'
        print('Karakter:', name, '/', turtle['type_tr'])
        print('Sahne:', len(story['scenes']), 'Kelime:', word_count)
        return story
    raise RuntimeError('Uc denemede 6 sahneli 45-65 kelimelik Tosbi hikayesi olusmadi.')


async def scene_voices(story, folder):
    """Her sahneyi ayri seslendir: cumle ortasindan yaklasik bolme YOK."""
    folder.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    out = []
    for i, scene in enumerate(story['scenes'], 1):
        path = folder / f'ses_{i:02}.wav'
        if not path.exists():
            text = scene['narration'].strip()
            def generate_one():
                response = client.models.generate_content(
                    model='gemini-3.8-flash-tts',
                    contents=(
                        '# Style instructions\n'
                        'Türkçe çocuk masalı anlatıcısı gibi sıcak, anlaşılır ve doğal oku. '
                        'Yalnızca aşağıdaki cümleyi seslendir, başka kelime ekleme.\n'
                        '# Transcript\n' + text
                    ),
                    config=types.GenerateContentConfig(
                        temperature=0.4,
                        response_modalities=['AUDIO'],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Sami')
                            )
                        ),
                    ),
                )
                if not response.candidates:
                    raise RuntimeError('Sami ses yaniti bos.')
                audio_data = next((p.inline_data for p in response.candidates[0].content.parts
                                   if p.inline_data and p.inline_data.data), None)
                if audio_data is None:
                    raise RuntimeError('Sami ses verisi bulunamadi.')
                with wave.open(str(path), 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(24000)
                    wav.writeframes(audio_data.data)
            await asyncio.to_thread(generate_one)
        d = mm.duration(path)
        if d <= 0:
            raise RuntimeError(f'Bos ses dosyasi: {path}')
        
        out.append((path, d, []))
        print(f'Ses {i}/{len(story["scenes"])} hazir ({d:.2f} sn)')

        # Gemini ücretsiz kota sınırı için bekleme
        if i < len(story['scenes']):
            print('Sonraki seslendirme için 25 saniye bekleniyor...')
            await asyncio.sleep(25)

    return out



def sentence_subtitles(words, text, dur):
    # Ilk test: eksik kelime zamanlarini TAHMIN ETME.
    # Tum sahne cumlesi, kendi gercek ses dosyasi boyunca sabit gorunur.
    # Kelime kelime senkronizasyon degildir; bu asama icin bilincli tercih.
    return [(0.0, dur, text.strip())]


async def main():
    assert mm.KISA_MASAL_TEST, 'MINOMASAL_30SN_TEST=true olmali'
    assert not mm.YAYIN_AKTIF, 'Bu test hicbir zaman yayin yapmamalidir'
    story = prepare_test_story()
    # Degisiklikler sadece bu Python surecinde gecerlidir.
    mm.voices = scene_voices
    mm.subtitle_groups = sentence_subtitles
    video = await mm.produce(TOPIC, supplied_story=story)
    print('Video suresi:', round(mm.duration(video), 2), 'saniye')
    print('Video yolu:', video)
    print('Yayin yapilmadi. Kelime-bazli altyazi hizalamasi henuz uygulanmadi.')


if __name__ == '__main__':
    asyncio.run(main())
