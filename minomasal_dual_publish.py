"""MinoMasal manual cross-platform publisher. Fail-closed on ambiguous uploads.

Uses an existing staging artifact (video + metadata); never generates a different story.
Requires explicit PUBLISH_ENABLED=true. Commits state before/after each external call.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
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
    tmp.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8'
    )
    tmp.replace(LEDGER)

    cmd('git', 'add', str(LEDGER))

    if subprocess.run(
        ['git', 'diff', '--cached', '--quiet']
    ).returncode == 0:
        raise RuntimeError('Expected ledger change was not staged')

    cmd('git', 'commit', '-m', message + ' [skip ci]')

    try:
        from minomasal_git_kayit_guvenligi import safe_push_ledger
        safe_push_ledger()
    except subprocess.CalledProcessError:
        raise RuntimeError(
            'GitHub kayıtları değişmiş. Güvenlik nedeniyle yayın durduruldu. '
            'Kayıtları kontrol etmeden yeniden çalıştırmayın.'
        )


def graph(method, path, params):
    params=dict(params)
    token=params.pop('access_token',None)
    data=urllib.parse.urlencode(params).encode()
    url=f'{API}/{path}'
    if method=='GET':url+='?'+data.decode();data=None
    headers={'Authorization':'Bearer '+token} if token else {}
    attempts=3 if method=='GET' else 1
    for attempt in range(attempts):
        req=urllib.request.Request(url,data=data,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in (429,500,502,503,504) and attempt+1<attempts:
                time.sleep(2**attempt);continue
            raise RuntimeError(f'Instagram HTTP {error.code}; details=redacted; no POST replay') from None
        except Exception:
            raise RuntimeError('Instagram request failed; details=redacted; no POST replay') from None


def verify_youtube(video_id):
    import requests
    try:
        response=requests.post('https://oauth2.googleapis.com/token',data={
            'client_id':os.environ['YOUTUBE_CLIENT_ID'],'client_secret':os.environ['YOUTUBE_CLIENT_SECRET'],
            'refresh_token':os.environ['YOUTUBE_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30)
        if response.status_code!=200:raise ValueError()
        access=response.json()['access_token']
        for attempt in range(6):
            result=requests.get('https://www.googleapis.com/youtube/v3/videos',params={'part':'status','id':video_id},
                headers={'Authorization':'Bearer '+access},timeout=30)
            if result.status_code!=200:raise ValueError()
            items=result.json().get('items',[])
            if len(items)==1 and items[0].get('id')==video_id:
                status=items[0].get('status',{})
                if status.get('uploadStatus')=='processed' and status.get('privacyStatus')=='public':
                    return 'https://www.youtube.com/watch?v='+video_id
                if status.get('uploadStatus') in ('failed','rejected','deleted'):raise ValueError()
            if attempt<5:time.sleep(10)
    except Exception:raise RuntimeError('YouTube publication not verified; preserve known ID and reconcile, never reupload blindly.') from None
    raise RuntimeError('YouTube processing not verified within bounded wait; preserve ID.')


def verified_instagram_permalink(confirmed,media_id):
    link=confirmed.get('permalink','')
    parsed=urllib.parse.urlsplit(link)
    if (confirmed.get('id')!=media_id or confirmed.get('media_type')!='VIDEO'
            or confirmed.get('media_product_type')!='REELS' or parsed.scheme!='https'
            or parsed.hostname not in ('www.instagram.com','instagram.com')):
        raise RuntimeError('Instagram Reel not verified; preserve ID and reconcile, never republish blindly.')
    return link


def verified_host_asset(url,video):
    expected=hashlib.sha256(Path(video).read_bytes()).hexdigest();size=Path(video).stat().st_size
    try:
        with urllib.request.urlopen(url,timeout=60) as response:
            total=0;digest=hashlib.sha256()
            while True:
                block=response.read(1024*1024)
                if not block:break
                total+=len(block)
                if total>size:raise ValueError()
                digest.update(block)
        if total!=size or digest.hexdigest()!=expected:raise ValueError()
    except Exception:raise RuntimeError('Existing hosted asset does not verify; no replacement or duplicate release.') from None


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
    from minomasal_yayin_guvenligi import ensure_allowed_topic, validate_receipt
    ensure_allowed_topic(meta['topic'])
    validate_receipt(video)
    from minomasal_daily_live import choose
    row = ledger['stories'].get(str(n))
    if row is None and choose(ledger) != n:
        raise RuntimeError('Hikâye sırası atlanamaz.')
    if row is None:
        row = {'topic': meta['topic'], 'title': meta['title'], 'youtube': {'status': 'pending', 'video_id': None, 'privacy': None}, 'instagram': {'status': 'pending', 'container_id': None, 'media_id': None}, 'video_asset': None, 'narration_sha256':meta.get('narration_sha256')}
    elif row['topic'] != meta['topic']:
        raise RuntimeError('Existing topic mismatch')
    for platform in ('youtube', 'instagram'):
        if row[platform]['status'] not in ('pending', 'published'):
            raise RuntimeError(f'{platform}: {row[platform]["status"]}; manual reconciliation required')
    if all(row[p]['status'] == 'published' for p in ('youtube', 'instagram')):
        print('İki platformda zaten yayımlandı; tekrar yayın yok.')
        return
    if os.environ.get('PUBLISH_ENABLED') != 'true':
        print('DRY RUN PASS: staged video and ledger validated; no upload')
        return
    # Yalnizca LIVE gunluk workflow'da etkin: tam olarak bu run'a ait
    # GitHub kilidi olmadan ilk yayin kaydini veya API upload'unu baslatma.
    if os.environ.get('MINOMASAL_ENFORCE_DAILY_LOCK') != 'true':
        raise RuntimeError('Daily lock is mandatory for any real publication.')
    approved=os.environ.get('MINOMASAL_APPROVED_VIDEO_SHA256','')
    if len(approved)!=64 or hashlib.sha256(video.read_bytes()).hexdigest()!=approved:
        raise RuntimeError('Explicit approval for this exact MP4 is required.')
    from minomasal_engine_qa import check as engine_quality
    quality=json.loads((stage/'quality-report.json').read_text())
    if quality.get('technical_checks_passed') is not True or quality.get('video_sha256')!=approved:
        raise RuntimeError('Engine quality report missing or mismatched.')
    engine_quality(video,stage/'altyazi.srt')
    if os.environ.get('MINOMASAL_ENFORCE_DAILY_LOCK') == 'true':
        from minomasal_gunluk_kilit import verify
        lock_day = os.environ.get('MINOMASAL_LOCK_DAY', '').strip()
        if not lock_day:
            raise RuntimeError('Gunluk kilit tarihi yok; yayin engellendi.')
        verify(n, lock_day)
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
        if not isinstance(video_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id):
            raise RuntimeError('YouTube accepted ID invalid; ambiguous state retained.')
        yt.update(video_id=video_id)
        save(ledger, f'Record YouTube accepted ID {n}; verification pending')
        link=verify_youtube(video_id)
        yt.update(status='published',privacy='public',url=link,verified_at_utc=datetime.now(timezone.utc).isoformat())
        save(ledger, f'Record verified YouTube video {n}')
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
        expected_url=f'https://github.com/{HOST}/releases/download/{tag}/{filename}'
        if (row.get('video_asset') or {}).get('url')!=expected_url:
            raise RuntimeError('Existing release is not bound to the recorded asset; manual reconciliation required.')
        verified_host_asset(expected_url,video)
    if not exists:
        result=subprocess.run(['gh','release','create',tag,filename,'--repo',HOST,'--title',f'MinoMasal story {n}',
            '--notes','Instagram processing asset','--prerelease'],env=env,capture_output=True,check=False)
        if result.returncode:raise RuntimeError('Hosting create failed; reconcile before retrying; details withheld.')
    url = f'https://github.com/{HOST}/releases/download/{tag}/{filename}'
    row['video_asset'] = {'url': url, 'release_tag': tag}
    save(ledger, f'Record hosted asset {n}')
    ig['status'] = 'ambiguous'
    save(ledger, f'Mark Instagram publish attempt for story {n}')
    auth = {'access_token': os.environ['INSTAGRAM_ACCESS_TOKEN']}
    result = graph('POST', f'{os.environ["INSTAGRAM_USER_ID"]}/media', {**auth, 'media_type': 'REELS', 'video_url': url, 'thumb_offset': 2000, 'caption': meta['title'] + '\n#MinoMasal #ÇocukHikayeleri'})
    container = str(result['id'])
    if not re.fullmatch('[0-9]+',container):raise RuntimeError('Instagram container ID invalid; ambiguous state retained.')
    ig['container_id'] = container
    save(ledger, f'Record Instagram container {n}')
    for _ in range(25):
        status = graph('GET', container, {**auth, 'fields': 'id,status_code,status'}).get('status_code')
        if status not in ('IN_PROGRESS','FINISHED','ERROR','EXPIRED','PUBLISHED'):raise RuntimeError('Instagram processing status unknown; details withheld.')
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
    if not re.fullmatch('[0-9]+',str(published.get('id',''))):raise RuntimeError('Instagram media ID invalid; ambiguous state retained.')
    ig['media_id']=str(published['id'])
    save(ledger, f'Record Instagram accepted ID {n}; verification pending')
    confirmed=graph('GET',ig['media_id'],{**auth,'fields':'id,permalink,media_type,media_product_type'})
    link=verified_instagram_permalink(confirmed,ig['media_id'])
    ig.update(status='published',url=link,verified_at_utc=datetime.now(timezone.utc).isoformat())
    save(ledger, f'Record verified Instagram publication {n}')
    print('Instagram published:', published['id'])
    print('SUCCESS: both platforms recorded. Hosting asset retained for safe processing.')


if __name__ == '__main__':
    main()
