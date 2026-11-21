"""MinoMasal publication ledger migration and validation. No network or publishing.

Use this ledger as the source of truth for platform states. Unknown states must
not be treated as unpublished or safe to retry automatically.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

STATE = Path('minomasal_yayin_durumu.json')
PREVIEW = Path('minomasal_onizleme_durumu.json')
LEDGER = Path('minomasal_platform_durumu.json')


def read(path):
    if not path.is_file():
        raise SystemExit(f'Güvenli durdurma: dosya bulunamadı: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise SystemExit(f'Geçersiz JSON: {path}')
    return data


def write_new(path, data):
    # Never overwrite a ledger that may have newer publish events.
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def migrate(state, preview):
    records = {}
    for key in sorted(set(state) | set(preview), key=lambda k: int(k) if k.isdigit() else 10**9):
        if not key.isdigit():
            continue
        row = state.get(key, {})
        pv = preview.get(key, {})
        topic = row.get('topic') or pv.get('topic')
        if not topic:
            continue
        yt = row.get('uploads', {}).get('youtube', {})
        yt_id = row.get('youtube_video_id') or pv.get('youtube_video_id')
        if not yt_id and yt.get('link'):
            from urllib.parse import parse_qs, urlparse
            yt_id = parse_qs(urlparse(yt['link']).query).get('v', [None])[0]
        yt_success = bool(row.get('youtube_uploaded') or pv.get('youtube_uploaded') or yt.get('status') == 'success')
        # Historical 'complete' is not evidence of an actual upload.
        yt_status = 'published' if yt_success and yt_id else ('needs_review' if yt_success else 'unknown')
        records[key] = {
            'topic': topic,
            'title': row.get('title') or pv.get('title') or topic,
            'youtube': {'status': yt_status, 'video_id': yt_id, 'privacy': row.get('privacy_status') or yt.get('privacy')},
            'instagram': {'status': 'unknown', 'container_id': None, 'media_id': None},
            'video_asset': None,
        }
    # Manual IG publication of story #13 was verified in the earlier workflow.
    if '13' in records:
        records['13']['instagram'] = {'status': 'published', 'container_id': '18131376751631544', 'media_id': '18204486874372734'}
    # #14 was processed, but never published by the test workflow.
    if '14' in records:
        records['14']['instagram'] = {'status': 'processed_not_published', 'container_id': '18131591965631544', 'media_id': None}
    return {'schema_version': 1, 'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'stories': records}


def validate(ledger):
    assert ledger.get('schema_version') == 1
    stories = ledger.get('stories', {})
    assert isinstance(stories, dict)
    valid = {'unknown', 'needs_review', 'pending', 'uploading', 'processed_not_published', 'published', 'failed', 'ambiguous', 'skipped'}
    for key, item in stories.items():
        assert key.isdigit(), f'Invalid story number: {key}'
        for platform in ('youtube', 'instagram'):
            obj = item[platform]
            assert obj['status'] in valid, (key, platform, obj)
            if obj['status'] == 'published':
                assert obj['video_id' if platform == 'youtube' else 'media_id'], (key, platform, 'missing ID')
    return {'stories': len(stories), 'youtube_published_or_uploaded': [k for k,v in stories.items() if v['youtube']['status']=='published'], 'instagram_published': [k for k,v in stories.items() if v['instagram']['status']=='published'], 'instagram_needs_review': [k for k,v in stories.items() if v['instagram']['status'] != 'published']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=('init','check'), default='check')
    p.add_argument('--state', type=Path, default=STATE)
    p.add_argument('--preview', type=Path, default=PREVIEW)
    p.add_argument('--ledger', type=Path, default=LEDGER)
    args = p.parse_args()
    if args.mode == 'init':
        if args.ledger.exists():
            raise SystemExit('Yayın defteri zaten var. Üzerine yazılmadı.')
        data = migrate(read(args.state), read(args.preview))
        result = validate(data)
        write_new(args.ledger, data)
    else:
        result = validate(read(args.ledger))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('Yayın yapılmadı. Durumu bilinmeyen gönderiler otomatik tekrar yüklenmemeli.')


if __name__ == '__main__':
    main()
