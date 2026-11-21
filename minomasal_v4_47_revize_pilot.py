"""MinoMasal2 #47 revised, reference-guided, NO-PUBLISH pilot.

Never edits production stories, daily workflow, publication ledger, or existing MP4.
--check is fully offline; --render uses Pollinations image edits and Gemini TTS.
The rendered result ALWAYS requires human story/image/video review before publishing.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
from pathlib import Path

import requests
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
STORY_PATH = HERE / 'minomasal_v4_47_revize_hikaye.json'
REFERENCE_PATH = HERE / 'tonton_referans.png'
RESULT_PATH = Path('minomasal_v4_47_revize_pilot_rapor.json')
QA_ROOT = Path('minomasal_v4_47_revize_pilot_data')
NUMBER = 47
TOPIC = 'Kaybolan Oyuncak Kamyon'
EDIT_MODEL = os.environ.get('MINOMASAL_IMAGE_EDIT_MODEL', 'kontext')


def no_publish_guard():
    danger = [
        ('PUBLISH_ENABLED', 'true'),
        ('MINOMASAL_YOUTUBE_UPLOAD', 'true'),
        ('MINOMASAL_30SN_TEST', 'true'),
    ]
    for key, blocked in danger:
        if os.environ.get(key, 'false').strip().lower() == blocked:
            raise RuntimeError(f'NO-PUBLISH GUARD: {key}={blocked}; durduruldu')


def validate_story():
    no_publish_guard()
    if not STORY_PATH.is_file() or not REFERENCE_PATH.is_file():
        raise RuntimeError('Revize JSON veya referans PNG yok')
    story = json.loads(STORY_PATH.read_text(encoding='utf-8'))
    scenes = story.get('scenes')
    if not isinstance(scenes, list) or len(scenes) != 10:
        raise ValueError('Tam 10 sahne zorunlu')
    narratives = [s.get('narration', '') for s in scenes]
    if any(not isinstance(x, str) or len(x.split()) < 5 for x in narratives):
        raise ValueError('Eksik veya anlamsiz derecede kisa narration')
    count = sum(len(x.split()) for x in narratives)
    if not 75 <= count <= 110:
        raise ValueError(f'75-110 kelime gerekiyor; bulunan: {count}')
    name_count = sum(x.count('Tonton') for x in narratives)
    if name_count > 3:
        raise ValueError(f'Kahraman adi fazla tekrar ediyor: {name_count}')
    if 'kaybetti' not in narratives[0].casefold():
        raise ValueError('Ilk sahnede kaybolma olayi yok')
    if 'kopru' not in _ascii(' '.join(narratives)):
        raise ValueError('Kaybolan yolun ipucu olan kopru anlatilmiyor')
    if 'isaret' not in _ascii(' '.join(narratives)):
        raise ValueError('Ogretici yol isareti temasi yok')
    unique = len(set(x.casefold() for x in narratives))
    if unique != len(narratives):
        raise ValueError('Tekrarlanan anlatim cumlesi var')
    for i, s in enumerate(scenes, 1):
        visual = s.get('visual')
        if not isinstance(visual, str) or 'same' not in visual.lower() or 'reference' not in visual.lower():
            raise ValueError(f'Sahne {i}: referans koruma tarifi eksik')
        if 'forest' in visual.lower().replace('no forest', ''):
            raise ValueError(f'Sahne {i}: istem disi forest tasviri tespit edildi')
    Image.open(REFERENCE_PATH).verify()
    return story, count, name_count


def _ascii(value):
    import unicodedata
    value = value.casefold().replace('ı', 'i')
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))


def _reply_image(res):
    try:
        obj = res.json()
    except ValueError:
        if res.headers.get('Content-Type', '').startswith('image/'):
            return Image.open(io.BytesIO(res.content))
        raise RuntimeError('Gorsel duzenleme API goruntu/JSON yerine baska veri dondurdu')
    data = obj.get('data') if isinstance(obj, dict) else None
    if not isinstance(data, list) or not data:
        raise RuntimeError('Gorsel duzenleme API data[0] bulunamadi')
    part = data[0]
    if 'b64_json' in part:
        return Image.open(io.BytesIO(base64.b64decode(part['b64_json'])))
    if part.get('url', '').startswith('https://'):
        get = requests.get(part['url'], timeout=90)
        get.raise_for_status()
        return Image.open(io.BytesIO(get.content))
    raise RuntimeError('Gorsel API desteklenmeyen veri tipi dondu')


def reference_images(story, folder, key, ignored_model, local=''):
    """POST /v1/images/edits (reference frame per scene). Never silently falls back to text-only."""
    if not key:
        raise RuntimeError('POLLINATIONS_API_KEY yok')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    output = []
    for i, scene in enumerate(story['scenes'], 1):
        target = folder / f'{i:02d}.jpg'
        if not target.is_file():
            prompt = (
                'Use the attached reference image as the STRICT identity of the single toy truck. '
                'Keep the truck identical in its face, cab, wheel count, orange wheel rims, green eyes, '
                'front grille, roof lamps, cargo bed and blue color. Do not add other vehicles. '
                'Change the forest background to a colorful TOY CONSTRUCTION SITE; no natural forest. '
                'Illustrate precisely this one storyboard scene, with a DIFFERENT meaningful action: '
                + scene['visual']
            )
            with REFERENCE_PATH.open('rb') as im:
                r = requests.post(
                    'https://gen.pollinations.ai/v1/images/edits',
                    headers={'Authorization': 'Bearer ' + key},
                    files={'image': ('tonton_referans.png', im, 'image/png')},
                    data={'model': EDIT_MODEL, 'prompt': prompt},
                    timeout=240,
                )
            if r.status_code != 200:
                raise RuntimeError(f'Image EDIT failed scene={i} status={r.status_code}: {r.text[:300]}')
            image = _reply_image(r)
            image.load()
            tmp = target.with_suffix('.tmp.jpg')
            ImageOps.fit(image.convert('RGB'), (1080, 1920), method=Image.Resampling.LANCZOS).save(tmp, quality=95)
            tmp.replace(target)
        with Image.open(target) as saved:
            saved.verify()
        output.append(target)
        print(f'REFERENCE_IMAGE_{i:02d}_CREATED')
    return output



def make_contact_sheet(image_dir, output_path):
    """Offline 10-scene QA strip. Does NOT claim visual consistency."""
    from PIL import ImageDraw
    width, height = 250, 460
    sheet = Image.new('RGB', (width*5, height*2), '#f2f2f2')
    for i in range(1, 11):
        frame = Image.open(Path(image_dir)/f'{i:02d}.jpg').convert('RGB')
        frame.thumbnail((width-16, height-40))
        x = ((i-1)%5)*width+(width-frame.width)//2
        y = ((i-1)//5)*height+6
        sheet.paste(frame, (x,y))
        draw=ImageDraw.Draw(sheet)
        draw.text((x,y+frame.height+5), f'Sahne {i}', fill='#101010')
    sheet.save(output_path, quality=91)
    return output_path



async def run_render(story, word_count, name_count):
    from minomasal_kalite_35_qa_v3 import get_topics, digest_states
    import minomasal as mm
    from minomasal_sami_hizalama_v2 import aligned_scene_voices
    topics = get_topics()
    if topics[NUMBER-1] != TOPIC:
        raise RuntimeError('KONULAR 47 degismis; durduruldu')
    before = digest_states()
    try:
        mm.make_images = reference_images
        mm.GORSEL_MODELI = f'reference-edit:{EDIT_MODEL}'  # fingerprint reflects the editing model
        mm.voices = aligned_scene_voices
        mm.ROOT = QA_ROOT.resolve()
        mm.ROOT.mkdir(parents=True, exist_ok=True)
        # Supplied, human-edited JSON: no additional story-generation request.
        video = await mm.produce(TOPIC, supplied_story=story)
        sheet = make_contact_sheet(video.parent / 'gorseller', video.parent / 'sahne_karsilastirma.jpg')
        report = {
            'result': 'rendered_no_publish_human_review_required',
            'story_number': NUMBER,
            'title': story['title'],
            'word_count': word_count,
            'character_name_mentions': name_count,
            'scene_count': len(story['scenes']),
            'image_generation': 'Pollinations /v1/images/edits reference-guided',
            'edit_model': EDIT_MODEL,
            'video': str(video),
            'duration_seconds': round(mm.duration(video), 2),
            'story': str(video.parent / 'hikaye.json'),
            'subtitles': str(video.parent / 'altyazi.srt'),
            'scene_images': str(video.parent / 'gorseller'),
            'contact_sheet': str(sheet),
            'published': False,
            'visual_consistency_verified': False,
            'human_review_required': True,
        }
        RESULT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print('V4_47_REVISED_RENDER_COMPLETE_REQUIRES_HUMAN_REVIEW')
        return report
    finally:
        if digest_states() != before:
            raise RuntimeError('YAYIN KAYDI DEGISTI: Yayin defteri guvenlik ihlali')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true', help='Live API call, but absolutely NO publish')
    args = parser.parse_args()
    story, words, mentions = validate_story()
    if not args.render:
        RESULT_PATH.write_text(json.dumps({
            'result':'preflight_ok_no_publish', 'story_number':NUMBER,
            'word_count':words, 'character_name_mentions':mentions, 'scene_count':10,
            'published':False, 'render_requested':False,
        }, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print(f'V4_47_REVISED_PREFLIGHT_OK words={words} tonton_mentions={mentions} scenes=10')
        return
    if not os.environ.get('POLLINATIONS_API_KEY') or not os.environ.get('GEMINI_API_KEY'):
        raise RuntimeError('Render icin POLLINATIONS_API_KEY ve GEMINI_API_KEY gerekli')
    asyncio.run(run_render(story, words, mentions))

if __name__ == '__main__':
    main()
