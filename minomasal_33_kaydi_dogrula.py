"""Yalnizca GERCEKTEN paylasilmis #33 videolari dogrular ve ledger'i gunceller.

No upload: read-only YouTube/Instagram APIs. Existing GitHub Secrets are used.
Refuses to overwrite conflicting records. Do not use until both posts are public.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs

import requests

LEDGER = Path('minomasal_platform_durumu.json')
TOPIC = 'Minik Sincabın Kırmızı Beyaz Bayrağı'

def yt_id_from(url):
    p = urlparse(url.strip())
    host = p.netloc.lower().removeprefix('www.')
    if p.scheme != 'https' or host not in {'youtube.com','m.youtube.com','youtu.be'}:
        raise ValueError('YouTube adresi HTTPS youtube.com veya youtu.be olmali')
    if host == 'youtu.be':
        candidate = p.path.strip('/').split('/')[0]
    elif p.path.startswith('/shorts/'):
        candidate = p.path.split('/')[2]
    elif p.path == '/watch':
        candidate = parse_qs(p.query).get('v', [''])[0]
    else:
        raise ValueError('Desteklenmeyen YouTube video bağlantısı')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', candidate):
        raise ValueError('YouTube video ID hatali')
    return candidate

def ig_code(url):
    p = urlparse(url.strip())
    host = p.netloc.lower().removeprefix('www.')
    if p.scheme != 'https' or host != 'instagram.com':
        raise ValueError('Instagram adresi HTTPS instagram.com olmali')
    m = re.fullmatch(r'/(?:p|reel|reels)/([A-Za-z0-9_-]+)/?',p.path)
    if not m:
        raise ValueError('Instagram /reel/ veya /p/ adresi bekleniyor')
    return m.group(1)

def assert_recent(stamp, label):
    # The manual #33 Republic Day publication should not be a historic unrelated post.
    if not stamp:
        raise ValueError(f'{label}: yayin zamani gelmedi')
    dt = datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(timezone.utc)
    if dt < datetime(2026,10,27,tzinfo=timezone.utc):
        raise ValueError(f'{label}: eski tarihli gonderi; #33 degil')

def youtube_check(url):
    """Verify public YouTube video and recognizable MinoMasal publisher via oEmbed."""
    video_id = yt_id_from(url)
    response = requests.get(
        'https://www.youtube.com/oembed',
        params={'url': f'https://www.youtube.com/watch?v={video_id}', 'format':'json'},
        timeout=35,
    )
    response.raise_for_status()
    data = response.json()
    title = str(data.get('title', ''))
    author = str(data.get('author_name', ''))
    if 'minomasal' not in author.casefold().replace(' ', ''):
        raise RuntimeError('YouTube gonderisi MinoMasal kanalinda gorunmuyor; kayit degistirilmedi')
    folded = title.casefold()
    if not any(x in folded for x in ('sincab', '29 ekim', 'cumhuriyet')):
        raise RuntimeError('YouTube basligi #33 hikayesi gibi gorunmuyor; kayit degistirilmedi')
    print('YouTube herkese acik video dogrulandi:', video_id, title, 'kanal:', author)
    return video_id

def instagram_check(url):
    code=ig_code(url)
    user=os.environ['INSTAGRAM_USER_ID']
    token=os.environ['INSTAGRAM_ACCESS_TOKEN']
    endpoint=f'https://graph.facebook.com/v26.0/{user}/media'
    params={'fields':'id,permalink,caption,media_type,timestamp','limit':100,'access_token':token}
    # Only inspect a bounded number of recent pages; never print secrets/next URLs.
    for page in range(5):
        response=requests.get(endpoint,params=params,timeout=40)
        response.raise_for_status()
        data=response.json()
        if 'error' in data:
            raise RuntimeError('Instagram Graph API hata verdi: '+str(data['error'].get('message','hata')))
        for media in data.get('data',[]):
            try:
                matched=ig_code(media.get('permalink',''))==code
            except ValueError:
                matched=False
            if not matched:
                continue
            if media.get('media_type') not in ('VIDEO',):
                raise RuntimeError('Instagram gonderisi video degil')
            assert_recent(media.get('timestamp'),'Instagram')
            caption=media.get('caption','').casefold()
            if not any(x in caption for x in ('sincab', 'cumhuriyet', '29 ekim', '29ekim')):
                raise RuntimeError('Instagram aciklamasi #33 gibi gorunmuyor')
            media_id=str(media['id'])
            if not media_id.isdigit():
                raise RuntimeError('Instagram sayisal media_id bulunamadi')
            print('Instagram dogrulandi:',media_id,media.get('permalink',''))
            return media_id
        endpoint=data.get('paging',{}).get('next')
        if not endpoint: break
        if not endpoint.startswith('https://graph.facebook.com/'):
            raise RuntimeError('Beklenmeyen Instagram sayfalama sunucusu')
        params=None
    raise RuntimeError('Instagram #33 gonderisi bagli hesapta bulunamadi')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--youtube-url',required=True)
    p.add_argument('--instagram-url',required=True)
    p.add_argument('--write',action='store_true')
    args=p.parse_args()
    yt=youtube_check(args.youtube_url)
    ig=instagram_check(args.instagram_url)
    if not LEDGER.exists():
        raise RuntimeError('Yayin defteri bulunamadi')
    data=json.loads(LEDGER.read_text(encoding='utf-8'))
    from minomasal_ledger import validate
    validate(data)
    records=data['stories']
    old32=records.get('32',{})
    if any(old32.get(platform,{}).get('status')!='published' for platform in ('youtube','instagram')):
        raise RuntimeError('#32 yayin kaydi tamamlanmamis')
    new={'topic':TOPIC,'title':TOPIC+' | MinoMasal',
         'youtube':{'status':'published','video_id':yt,'privacy':'public'},
         'instagram':{'status':'published','container_id':None,'media_id':ig},
         'video_asset':None}
    old=records.get('33')
    if old is not None:
        if old.get('topic') != TOPIC:
            raise RuntimeError('#33 konusu farkli. Elle kontrol gereklidir')
        for platform,field,wanted in [('youtube','video_id',yt),('instagram','media_id',ig)]:
            existing=old.get(platform,{}).get(field)
            if existing and existing != wanted:
                raise RuntimeError(f'#33 {platform} kaydi baska bir ID iceriyor: manuel kontrol')
        # Preserve any existing audit trail/hosting metadata and IDs.
        new={**old,'topic':TOPIC,
             'youtube':{**old.get('youtube',{}),'status':'published','video_id':yt,'privacy':'public'},
             'instagram':{**old.get('instagram',{}),'status':'published','media_id':ig}}
    records['33']=new
    validate(data)
    print('Yayina uygun #33 kaydi dogrulandi. #34 siradaki aday.')
    if args.write:
        tmp=LEDGER.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        tmp.replace(LEDGER)
        print('Yayin defteri guvenle guncellendi:',LEDGER)
    else:
        print('Sadece kontrol yapildi; dosya degismedi.')

if __name__=='__main__':main()
