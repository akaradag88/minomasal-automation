"""MinoMasal manual cross-platform publisher. Fail-closed on ambiguous uploads.

Uses an existing staging artifact (video + metadata); never generates a different story.
Requires explicit PUBLISH_ENABLED=true. Commits state before/after each external call.
"""
import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from minomasal import KONULAR, duration, upload_youtube
from minomasal_ledger import validate

LEDGER = Path('minomasal_platform_durumu.json')
HOST = 'akaradag88/minomasal-video-hosting'
API = 'https://graph.facebook.com/v26.0'


def cmd(*args):
    return subprocess.check_output(args, text=True).strip()


def save(ledger, message):
    tmp = LEDGER.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(LEDGER)
    cmd('git', 'add', str(LEDGER))
    if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0:
        raise RuntimeError('Expected ledger change was not staged')
    cmd('git', 'commit', '-m', message + ' [skip ci]')
    cmd('git', 'push', 'origin', 'HEAD:main')


def graph(method, path, params):
    data = urllib.parse.urlencode(params).encode()
    url = f'{API}/{path}'
    if method == 'GET':
        url += '?' + data.decode()
        data = None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            e = json.load(exc).get('error', {})
            raise RuntimeError(f'Instagram HTTP {exc.code}; code={e.get("code")}; subcode={e.get("error_subcode")}; message={e.get("message")}') from None
        except (ValueError, KeyError):
            raise RuntimeError(f'Instagram HTTP {exc.code}') from None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage', default='staging')
    p.add_argument('--number', type=int, required=True)
    args = p.parse_args()
    stage = Path(args.stage)
    meta = json.loads((stage / 'metadata.json').read_text(encoding='utf-8'))
    video = stage / 'masal_short.mp4'
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    validate(ledger)
    n = args.number
    if not (1 <= n <= len(KONULAR)) or meta['number'] != n or meta['topic'] != KONULAR[n - 1]:
        raise RuntimeError('Story number/topic mismatch. Stop.')
    if not video.is_file() or duration(video) <= 1:
        raise RuntimeError('Staged video missing or invalid')
    row = ledger['stories'].get(str(n))
    if row is None:
        row = {'topic': meta['topic'], 'title': meta['title'], 'youtube': {'status': 'pending', 'video_id': None, 'privacy': None}, 'instagram': {'status': 'pending', 'container_id': None, 'media_id': None}, 'video_asset': None}
    elif row['topic'] != meta['topic']:
        raise RuntimeError('Existing topic mismatch')
    for platform in ('youtube', 'instagram'):
        if row[platform]['status'] not in ('pending', 'published'):
            raise RuntimeError(f'{platform}: {row[platform]["status"]}; manual reconciliation required')
    if os.environ.get('PUBLISH_ENABLED') != 'true':
        print('DRY RUN PASS: staged video and ledger validated; no upload')
        return
    if os.environ.get('MINOMASAL_YOUTUBE_PRIVACY') != 'public':
        raise RuntimeError('YouTube privacy must be explicitly public')
    for name in ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN', 'INSTAGRAM_ACCESS_TOKEN', 'INSTAGRAM_USER_ID', 'MINOMASAL_HOSTING_TOKEN'):
        if not os.environ.get(name):
            raise RuntimeError(f'Missing secret: {name}')
    if str(n) not in ledger['stories']:
        ledger['stories'][str(n)] = row
        save(ledger, f'Initialize MinoMasal story {n}')
    yt = row['youtube']
    if yt['status'] == 'pending':
        yt['status'] = 'ambiguous'  # must be committed BEFORE irreversible API call
        save(ledger, f'Mark YouTube upload attempt for story {n}')
        video_id = upload_youtube(video, meta['title'], meta['topic'])
        yt.update(status='published', video_id=video_id, privacy='public')
        save(ledger, f'Record YouTube video {n}')
        print('YouTube uploaded:', video_id)
    else:
        print('YouTube already recorded; skip')
    ig = row['instagram']
    if ig['status'] == 'published':
        print('Instagram already recorded; skip')
        return
    # Host video in public GitHub Release, preserving it on any error.
    tag = f'minomasal-story-{n}'
    filename = f'minomasal-{n}.mp4'
    hosted = Path(filename)
    if not hosted.exists():
        hosted.write_bytes(video.read_bytes())
    token = os.environ['MINOMASAL_HOSTING_TOKEN']
    env = {**os.environ, 'GH_TOKEN': token}
    exists = subprocess.run(['gh', 'release', 'view', tag, '--repo', HOST], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if exists:
        raise RuntimeError(f'Hosting release {tag} already exists; verify asset manually to avoid mismatched video')
    subprocess.run(['gh', 'release', 'create', tag, filename, '--repo', HOST, '--title', f'MinoMasal story {n}', '--notes', 'Instagram processing asset', '--prerelease'], env=env, check=True)
    url = f'https://github.com/{HOST}/releases/download/{tag}/{filename}'
    row['video_asset'] = {'url': url, 'release_tag': tag}
    save(ledger, f'Record hosted asset {n}')
    ig['status'] = 'ambiguous'
    save(ledger, f'Mark Instagram publish attempt for story {n}')
    auth = {'access_token': os.environ['INSTAGRAM_ACCESS_TOKEN']}
    result = graph('POST', f'{os.environ["INSTAGRAM_USER_ID"]}/media', {**auth, 'media_type': 'REELS', 'video_url': url, 'caption': meta['title'] + '\n#MinoMasal #ÇocukHikayeleri'})
    container = result['id']
    ig['container_id'] = container
    save(ledger, f'Record Instagram container {n}')
    for _ in range(25):
        status = graph('GET', container, {**auth, 'fields': 'id,status_code,status'}).get('status_code')
        print('Instagram processing:', status)
        if status == 'FINISHED':
            break
        if status in ('ERROR', 'EXPIRED'):
            raise RuntimeError(f'Instagram processing failed: {status}')
        time.sleep(30)
    else:
        raise RuntimeError('Instagram processing timed out; manual reconciliation required')
    # State remains ambiguous if API succeeds but subsequent commit fails.
    published = graph('POST', f'{os.environ["INSTAGRAM_USER_ID"]}/media_publish', {**auth, 'creation_id': container})
    ig.update(status='published', media_id=published['id'])
    save(ledger, f'Record Instagram publication {n}')
    print('Instagram published:', published['id'])
    print('SUCCESS: both platforms recorded. Hosting asset retained for safe processing.')


if __name__ == '__main__':
    main()
