"""45/46 approved MinoMasal story video preview. No publishing, no ledger writes.

Run in GitHub Actions with MINOMASAL_YOUTUBE_UPLOAD=false, PUBLISH_ENABLED=false.
This module never invokes minomasal_dual_publish or writes GitHub state.
"""
import argparse
import asyncio
import json
import os
import shutil
from pathlib import Path


def inspect_source(number: int, topics, approved_special):
    if number not in (45, 46):
        raise ValueError('Only approved special story 45 or 46 is allowed.')
    topic = topics[number - 1]
    story = approved_special(number, topic)  # Same gate as live staging
    if not isinstance(story, dict) or len(story.get('scenes', [])) != 10:
        raise RuntimeError('Approved special story must have 10 scenes.')
    if not all(
        isinstance(s, dict)
        and isinstance(s.get('narration'), str) and s['narration'].strip()
        and isinstance(s.get('visual'), str) and s['visual'].strip()
        for s in story['scenes']
    ):
        raise RuntimeError('Missing narration or visual in a scene.')
    word_count = sum(len(scene['narration'].split()) for scene in story['scenes'])
    if not 75 <= word_count <= 130:
        raise RuntimeError(f'Unusual special story word count: {word_count}')
    return topic, story, word_count


async def run(number: int):
    if os.environ.get('MINOMASAL_YOUTUBE_UPLOAD', 'false').lower() != 'false':
        raise RuntimeError('Publication environment is not disabled.')
    if os.environ.get('PUBLISH_ENABLED', 'false').lower() != 'false':
        raise RuntimeError('Publication environment is not disabled.')

    import minomasal as mm
    from minomasal_gunluk_kalite_stage_v3 import approved_special
    from minomasal_sami_hizalama_v2 import aligned_scene_voices

    topic, story, words = inspect_source(number, mm.KONULAR, approved_special)
    root = Path('minomasal_45_46_preview_work').resolve()
    output = Path('minomasal_45_46_preview_output') / str(number)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'hikaye.json').write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {
        'number': number, 'topic': topic, 'title': story['title'],
        'words': words, 'scenes': len(story['scenes']),
        'published': False, 'status': 'render_started'
    }
    (output / 'rapor.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    if not os.environ.get('POLLINATIONS_API_KEY'):
        raise RuntimeError('POLLINATIONS_API_KEY secret is missing.')
    if not os.environ.get('GEMINI_API_KEY'):
        raise RuntimeError('GEMINI_API_KEY secret is missing.')
    mm.voices = aligned_scene_voices
    mm.ROOT = root
    mm.ROOT.mkdir(parents=True, exist_ok=True)
    if hasattr(mm, 'YAYIN_AKTIF'):
        mm.YAYIN_AKTIF = False

    try:
        video = await mm.produce(topic, supplied_story=story)
        if not video.is_file() or mm.duration(video) <= 1:
            raise RuntimeError('Rendered MP4 is invalid.')
        shutil.copy2(video, output / 'masal_short.mp4')
        subtitle = video.parent / 'altyazi.srt'
        if subtitle.is_file():
            shutil.copy2(subtitle, output / 'altyazi.srt')
        report['status'] = 'preview_ready_no_publish'
        report['duration_seconds'] = round(float(mm.duration(video)), 2)
        print(f'PREVIEW_OK_NO_PUBLISH #{number}: duration={report["duration_seconds"]}s')
    except Exception as ex:
        report['status'] = 'render_failed_no_publish'
        report['error_type'] = type(ex).__name__
        raise
    finally:
        # Collect scene images even when a paid render stops mid-way.
        for src in sorted(root.glob('*/gorseller/*.jpg')):
            dest_dir = output / 'gorseller'
            dest_dir.mkdir(exist_ok=True)
            shutil.copy2(src, dest_dir / src.name)
        (output / 'rapor.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--number', type=int, choices=(45, 46), required=True)
    args = parser.parse_args()
    asyncio.run(run(args.number))


if __name__ == '__main__':
    main()
