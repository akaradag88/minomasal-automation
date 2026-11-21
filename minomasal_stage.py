"""MinoMasal staged production: one video, no social uploads or state writes.

Run only after preflight; manual GitHub Actions workflow produces an artifact.
"""
import argparse
import asyncio
import json
import shutil
from pathlib import Path

from minomasal import KONULAR, ROOT, duration, produce
from minomasal_daily import load, plan


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', default='minomasal_yayin_durumu.json')
    parser.add_argument('--preview', default='minomasal_onizleme_durumu.json')
    parser.add_argument('--output', default='minomasal_staging')
    args = parser.parse_args()
    result = plan(load(args.state), load(args.preview))
    if result.get('action') != 'produce_new':
        raise SystemExit('No new story; no video generated.')
    number, topic = result['number'], result['topic']
    if KONULAR[number - 1] != topic:
        raise SystemExit('Topic mismatch: stopped to prevent incorrect upload.')
    video = await produce(topic)
    if not video.is_file() or duration(video) <= 1:
        raise SystemExit('Invalid video: stopped.')
    story = json.loads((video.parent / 'hikaye.json').read_text(encoding='utf-8'))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, output / 'masal_short.mp4')
    from minomasal_yayin_guvenligi import copy_receipt
    copy_receipt(video, output / 'masal_short.mp4')
    (output / 'metadata.json').write_text(json.dumps({
        'number': number,
        'topic': topic,
        'title': str(story.get('title') or topic).strip() + ' | MinoMasal',
        'video': 'masal_short.mp4',
        'youtube_uploaded': False,
        'instagram_published': False,
        'mode': 'staging_only',
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'STAGING SUCCESS: story #{number}; no social upload attempted.')


if __name__ == '__main__':
    asyncio.run(main())
