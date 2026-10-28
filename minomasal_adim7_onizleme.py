"""Adim 7: normal (10 sahne) hikayeyi kalite-v2 ile YAYINSIZ uret.

Mevcut minomasal.py'yi degistirmez; yayin gecmislerini de degistirmez.
Yalnizca manuel GitHub Actions islemiyle calistirilmasi onerilir.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

import minomasal as mm
from minomasal_kalite_v2 import create_story_v2, number_for_topic, PRESERVE_APPROVED
from minomasal_sami_hizalama_v2 import aligned_scene_voices

STATE_FILES = (
    'minomasal_yayin_durumu.json',
    'minomasal_onizleme_durumu.json',
    'minomasal_platform_durumu.json',
    'minomasal_facebook_durumu.json',
)


def _state_hashes():
    return {
        name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
        for name in STATE_FILES if Path(name).is_file()
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--story-number', type=int, default=35)
    args = parser.parse_args()

    # Asla yayin yapma. Ortam degiskeni de kapali olmalidir.
    if os.environ.get('MINOMASAL_YOUTUBE_UPLOAD', 'false').lower() != 'false':
        raise RuntimeError('Guvenlik: MINOMASAL_YOUTUBE_UPLOAD=false olmali.')
    if mm.YAYIN_AKTIF:
        raise RuntimeError('Guvenlik: youtube yayin acik, preview durduruldu.')
    if mm.KISA_MASAL_TEST:
        raise RuntimeError('Bu test 10 sahneli normal masal testidir; 30sn flag kapali olmali.')
    if not (31 <= args.story_number <= len(mm.KONULAR)):
        raise RuntimeError('Bu asama yalnizca 31-99 arasi kayitli karakterli hikayeler icin.')
    if args.story_number in PRESERVE_APPROVED or args.story_number == 100:
        raise RuntimeError('Onayli ozel gun ya da 5 karakterli #100: degistirilmedi, pilot yapilmayacak.')
    topic = mm.KONULAR[args.story_number - 1]
    assert number_for_topic(topic, mm.KONULAR) == args.story_number
    state_before = _state_hashes()

    # minomasal.py'nin produce/montaj/muzik mekanigini KORU.
    # Yalniz bu Python sureci icinde karakterli hikaye uretimini ve sesi degistir.
    mm.create_story = lambda topic_, key, model: create_story_v2(topic_, key, model, mm.KONULAR)
    mm.voices = aligned_scene_voices
    print(f'YAYINSIZ KALITE V2: {args.story_number}. {topic}')
    video = await mm.produce(topic)
    story = json.loads((video.parent / 'hikaye.json').read_text(encoding='utf-8'))
    print('Hikaye:', story['title'])
    print('Sahne:', len(story['scenes']))
    print('Kelime:', sum(len(s['narration'].split()) for s in story['scenes']))
    print('Video suresi:', round(mm.duration(video), 2), 'sn')
    if not (video.parent / 'altyazi.srt').exists():
        raise RuntimeError('Altyazi SRT yok. Video onayi verilemez.')
    if _state_hashes() != state_before:
        raise RuntimeError('YAYIN DURUM DOSYALARINDAN BIRI DEGISTI! Preview testi basarisiz.')
    print('YAYIN YOK. Durum dosyalarina dokunulmadi.')
    print('MP4:', video)
    print('SRT:', video.parent / 'altyazi.srt')
    print('Hikaye JSON:', video.parent / 'hikaye.json')


if __name__ == '__main__':
    asyncio.run(main())
