"""Read-only recovery audit: no media generation, uploads or ledger writes."""
import json,os
from pathlib import Path
import requests
from minomasal_cloudflare_quality_test import run_check
from minomasal_daily_live import choose,KONULAR,LEDGER
from minomasal_ledger import read

def main():
    out=Path('asset_test_output/recovery');out.mkdir(parents=True,exist_ok=False)
    names=('CLOUDFLARE_API_TOKEN','CLOUDFLARE_USAGE_TOKEN','CLOUDFLARE_ACCOUNT_ID','POLLINATIONS_API_KEY',
           'GEMINI_API_KEY','YOUTUBE_CLIENT_ID','YOUTUBE_CLIENT_SECRET','YOUTUBE_REFRESH_TOKEN',
           'INSTAGRAM_ACCESS_TOKEN','INSTAGRAM_USER_ID','MINOMASAL_HOSTING_TOKEN')
    report={'secrets_present':{name:bool(os.environ.get(name)) for name in names},'publishing_allowed':False}
    ledger=read(LEDGER);number=choose(ledger)
    report['ledger_next']={'number':number,'topic':KONULAR[number-1] if number else None}
    report['recent_ledger']={key:row for key,row in ledger['stories'].items() if int(key)>=43}
    report['cloudflare']=run_check(out/'cloudflare',False)
    try:
        r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ.get('YOUTUBE_CLIENT_ID'),
            'client_secret':os.environ.get('YOUTUBE_CLIENT_SECRET'),'refresh_token':os.environ.get('YOUTUBE_REFRESH_TOKEN'),
            'grant_type':'refresh_token'},timeout=30)
        report['youtube']={'token_http_status':r.status_code}
        token=r.json().get('access_token') if r.status_code==200 else None
        if token:
            h={'Authorization':'Bearer '+token}
            r=requests.get('https://www.googleapis.com/youtube/v3/channels',params={'part':'contentDetails','mine':'true'},headers=h,timeout=30)
            report['youtube']['channel_http_status']=r.status_code
            if r.status_code==200 and r.json().get('items'):
                playlist=r.json()['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                r=requests.get('https://www.googleapis.com/youtube/v3/playlistItems',params={'part':'snippet,contentDetails','playlistId':playlist,'maxResults':50},headers=h,timeout=30)
                report['youtube']['recent_http_status']=r.status_code
                if r.status_code==200:report['youtube']['recent']=[{'title':v['snippet']['title'],'video_id':v['contentDetails']['videoId']} for v in r.json().get('items',[])]
    except Exception:report.setdefault('youtube',{})['error']='read_only_audit_failed_raw_details_withheld'
    try:
        r=requests.get('https://graph.facebook.com/v26.0/'+os.environ.get('INSTAGRAM_USER_ID','')+'/media',
            params={'fields':'id,caption,permalink,timestamp','limit':50},headers={'Authorization':'Bearer '+os.environ.get('INSTAGRAM_ACCESS_TOKEN','')},timeout=30)
        report['instagram']={'http_status':r.status_code}
        if r.status_code==200:report['instagram']['recent']=[{'id':v['id'],'caption':v.get('caption','')[:180],'permalink':v.get('permalink'),'timestamp':v.get('timestamp')} for v in r.json().get('data',[])]
    except Exception:report.setdefault('instagram',{})['error']='read_only_audit_failed_raw_details_withheld'
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'audit_saved':True,'secrets_present':report['secrets_present'],'youtube_status':report.get('youtube',{}).get('channel_http_status'),
                     'instagram_status':report.get('instagram',{}).get('http_status'),'number':number,'publishing_allowed':False}))

if __name__=='__main__':main()
