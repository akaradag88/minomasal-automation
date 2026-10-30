"""MinoMasal2 approved staging candidate for future LIVE workflow.

IMPORTANT: Merely adding this file NEVER activates it. It stages a video only.
Publishing remains exclusively in the existing dual publisher workflow step.
"""
import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path

import minomasal as mm
import minomasal_daily_live as daily
from minomasal_ledger import read
from minomasal_kalite_v2 import create_story_v2
from minomasal_sami_hizalama_v2 import aligned_scene_voices

SPECIAL_FILES = {45: 'hikaye_03.json', 46: 'hikaye_04.json'}
QA_PUBLISH_GUARD = 'MINOMASAL_YOUTUBE_UPLOAD'


def ledger_hash():
    return hashlib.sha256(Path(daily.LEDGER).read_bytes()).hexdigest()


def approved_special(number, topic):
    source = Path(SPECIAL_FILES[number])
    if not source.is_file():
        raise RuntimeError(f'#{number} icin onayli JSON yok: {source}')
    story = json.loads(source.read_text(encoding='utf-8'))
    if story.get('title') != topic or len(story.get('scenes', [])) != 10:
        raise RuntimeError(f'#{number} onayli JSON basligi/sahnesi uyusmuyor.')
    return story


async def main():
    if os.environ.get(QA_PUBLISH_GUARD, 'false').lower() != 'false':
        raise RuntimeError('Staging asamasinda YouTube upload acik olamaz.')
    before = ledger_hash()
    ledger = read(daily.LEDGER)
    number = daily.choose(ledger)
    if number is None:
        print('Yeni hikaye kalmadi.'); return
    topic = mm.KONULAR[number - 1]
    if number in (33, 34):
        raise RuntimeError(f'#{number} onayli ozel gun; yeniden uretme/yayin yapma.')
    if number == 100:
        raise RuntimeError('#100 sozlukte 5 karakterli; manuel onay gerekli.')
    if number < 35:
        raise RuntimeError(f'#{number} eski hikaye; bu yeni kalite yolu kullanilamaz.')
    mm.voices = aligned_scene_voices
    mm.ROOT = Path('minomasal_kalite_v3_daily_data').resolve()
    mm.ROOT.mkdir(parents=True, exist_ok=True)
    if number in SPECIAL_FILES:
        story = approved_special(number, topic)
        video = await mm.produce(topic, supplied_story=story)
        actual = json.loads((video.parent/'hikaye.json').read_text(encoding='utf-8'))
        if actual != story:
            raise RuntimeError('Onayli ozel gun JSON degisti; yayin engellendi.')
    else:
        mm.create_story = lambda t, key, model: create_story_v2(t, key, model, mm.KONULAR)
        video = await mm.produce(topic)
        story = json.loads((video.parent/'hikaye.json').read_text(encoding='utf-8'))
        words = sum(len(s['narration'].split()) for s in story['scenes'])
        if len(story['scenes']) != 10 or not 75 <= words <= 110:
            raise RuntimeError('Hikaye kalite kurali gecilemedi.')
    if not video.is_file() or mm.duration(video) <= 1:
        raise RuntimeError('MP4 yok veya gecersiz.')
    if not (video.parent / 'altyazi.srt').is_file():
        raise RuntimeError('Altyazi dosyasi eksik.')
    if ledger_hash() != before:
        raise RuntimeError('Yayin defteri sahneleme sirasinda degismis; durduruldu.')
    daily.STAGING.mkdir(exist_ok=True, parents=True)
    shutil.copy2(video, daily.STAGING / 'masal_short.mp4')
    meta = {'number': number, 'topic': topic,
            'title': str(story.get('title') or topic).strip() + ' | MinoMasal',
            'video': 'masal_short.mp4', 'mode': 'quality_v3_staging'}
    (daily.STAGING / 'metadata.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # No publication here. Only record validated story number for existing publisher.
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write(f'number={number}\n')
    print('STAGED, NOT PUBLISHED: #', number, topic)


if __name__ == '__main__':
    asyncio.run(main())
