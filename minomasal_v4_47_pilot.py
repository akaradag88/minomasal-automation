"""MinoMasal2: 47 numaralı hikaye için güvenli, yayınsız V4 video pilotu.

Günlük yayın/ledger dosyalarını değiştirmez. Sadece yeni yerel test klasörüne
MP4, hikaye JSON, SRT ve QA raporu yazar. `--render` olmadan API çağırmaz.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from minomasal_kalite_35_qa_v3 import digest_states, get_topics
from minomasal_v4_baslik import load_config, preflight, text_supports_title
from minomasal_v4_gunluk_stage import install_prompt_guidance
from minomasal_v4_mantik_kontrol import install_quality_guard, audit_story

REPORT = Path('minomasal_v4_47_pilot_rapor.json')
QA_ROOT = Path('minomasal_v4_47_pilot_data')
NUMBER = 47


def must_be_no_publish():
    if os.environ.get('MINOMASAL_YOUTUBE_UPLOAD', 'false').lower() != 'false':
        raise RuntimeError('YAYIN GUARD: MINOMASAL_YOUTUBE_UPLOAD false olmalı')
    if os.environ.get('PUBLISH_ENABLED', 'false').lower() == 'true':
        raise RuntimeError('YAYIN GUARD: PUBLISH_ENABLED true olamaz')
    if os.environ.get('MINOMASAL_30SN_TEST', 'false').lower() != 'false':
        raise RuntimeError('Bu test 30 saniye modu ile çalışamaz')


def ready():
    must_be_no_publish()
    conf = preflight()
    topics = get_topics()
    entry = conf['stories'].get(str(NUMBER))
    if not entry or len(topics) < NUMBER or topics[NUMBER - 1] != entry['topic']:
        raise RuntimeError('47 numaralı hikayenin KONULAR eşleşmesi yanlış')
    for path in ('minomasal_kalite_v2.py', 'minomasal_sami_hizalama_v2.py',
                 'minomasal_v4_mantik_kontrol.py', 'minomasal_karakterler.json',
                 'minomasal_sami_tts_interactions.py'):
        if not Path(path).is_file():
            raise RuntimeError(f'Gerekli dosya yok: {path}')
    chars = json.loads(Path('minomasal_karakterler.json').read_text(encoding='utf-8'))
    keys = chars['story_characters_31_100'].get(str(NUMBER))
    if keys != ['oyuncak_kamyon']:
        raise RuntimeError('Pilot için yalnızca mevcut oyuncak_kamyon karakteri onaylı olmalı')
    return topics, entry


async def create_video(topics, entry):
    import minomasal as mm
    import minomasal_kalite_v2 as quality
    from minomasal_sami_hizalama_v2 import aligned_scene_voices

    # Önce V4 anlatım, sonra kural-tabanlı mantık kontrolü.
    install_prompt_guidance()
    install_quality_guard(quality)
    topic = topics[NUMBER - 1]
    mm.create_story = lambda t, key, model: quality.create_story_v2(t, key, model, mm.KONULAR)
    mm.voices = aligned_scene_voices
    mm.ROOT = QA_ROOT.resolve()
    mm.ROOT.mkdir(exist_ok=True, parents=True)
    video = await mm.produce(topic)  # yalnızca oluşturur; hiçbir upload kodu çağrılmaz
    if not video.is_file() or mm.duration(video) <= 1:
        raise RuntimeError('Video oluşturulamadı veya bozuk')
    story_path = video.parent / 'hikaye.json'
    srt = video.parent / 'altyazi.srt'
    if not story_path.is_file() or not srt.is_file() or not srt.read_text(encoding='utf-8').strip():
        raise RuntimeError('Hikaye JSON veya altyazı eksik')
    story = json.loads(story_path.read_text(encoding='utf-8'))
    count = len(story.get('scenes', []))
    words = sum(len(s.get('narration', '').split()) for s in story['scenes'])
    if count != 10 or not 75 <= words <= 110:
        raise RuntimeError(f'Sahne/kelime kalite hatası: {count} sahne, {words} kelime')
    _, cast, _ = quality.dictionary_entry(topic, list(mm.KONULAR))
    issues = audit_story(story, cast, NUMBER)
    if issues:
        raise RuntimeError('Hikaye mantık hatası: ' + ' | '.join(issues))
    supports_title = text_supports_title(story, entry)
    result = {
        'result': 'video_created_without_publish', 'story_number': NUMBER,
        'topic': topic, 'proposed_title': entry['publish_title'],
        'title_supported_by_story': supports_title,
        'word_count': words, 'scene_count': count,
        'video_seconds': round(mm.duration(video), 2),
        'video': str(video), 'story_json': str(story_path), 'subtitles': str(srt),
        'approved_cast': [c['name'] for _, c in cast],
        'published': False,
        'human_review_required': True,
    }
    if not supports_title:
        print('UYARI: yeni başlık anlatı tarafından doğrulanmadı; V4 yayın başlığını kullanma')
    print('V4_47_PILOT_RENDER_OK: video hazır; sosyal medyada yayın YOK')
    return result


async def main():
    p = argparse.ArgumentParser()
    p.add_argument('--render', action='store_true')
    args = p.parse_args()
    before = digest_states()
    topics, entry = ready()
    result = {'result': 'preflight_passed', 'story_number': NUMBER,
              'topic': entry['topic'], 'published': False,
              'render_requested': args.render}
    try:
        if args.render:
            if not os.environ.get('POLLINATIONS_API_KEY') or not os.environ.get('GEMINI_API_KEY'):
                raise RuntimeError('POLLINATIONS_API_KEY/GEMINI_API_KEY eksik')
            result = await create_video(topics, entry)
        else:
            print('V4_47_PILOT_PREFLIGHT_OK — video üretilmedi, yayın yok')
    except Exception as e:
        result = {'result': 'failed_no_publish', 'story_number': NUMBER,
                  'reason': str(e), 'published': False}
        raise
    finally:
        if digest_states() != before:
            raise RuntimeError('GÜVENLİK: yayın durumu dosyası değişmiş; durduruldu')
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    asyncio.run(main())
