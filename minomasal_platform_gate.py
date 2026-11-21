"""Read-only platform scope/history checks before any lock write or upload."""
import os
import re
import unicodedata
import requests

class PlatformBlocked(RuntimeError):pass

def normalized(value):
    value=str(value).casefold().replace('ı','i')
    value=''.join(c for c in unicodedata.normalize('NFKD',value) if not unicodedata.combining(c))
    return re.sub(r'\W+',' ',value).strip()

def verify(ledger,number,topic,title,*,transport=requests):
    def request(method,url,**kwargs):
        try:
            response=getattr(transport,method)(url,timeout=30,**kwargs)
            if response.status_code!=200:raise PlatformBlocked(f'platform_read_http_{response.status_code}')
            return response.json()
        except PlatformBlocked:raise
        except Exception:raise PlatformBlocked('platform_read_failed_details_withheld') from None
    token=request('post','https://oauth2.googleapis.com/token',data={
        'client_id':os.environ.get('YOUTUBE_CLIENT_ID'),'client_secret':os.environ.get('YOUTUBE_CLIENT_SECRET'),
        'refresh_token':os.environ.get('YOUTUBE_REFRESH_TOKEN'),'grant_type':'refresh_token'})
    scopes=set(token.get('scope','').split())
    broad={'https://www.googleapis.com/auth/youtube','https://www.googleapis.com/auth/youtube.force-ssl'}
    if not scopes & (broad|{'https://www.googleapis.com/auth/youtube.readonly'}):raise PlatformBlocked('youtube_read_scope_missing')
    if not scopes & (broad|{'https://www.googleapis.com/auth/youtube.upload'}):raise PlatformBlocked('youtube_upload_scope_missing')
    headers={'Authorization':'Bearer '+token.get('access_token','')}
    data=request('get','https://www.googleapis.com/youtube/v3/channels',headers=headers,params={'part':'contentDetails','mine':'true'})
    try:playlist=data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    except (KeyError,IndexError):raise PlatformBlocked('youtube_channel_not_verified') from None
    videos=[];cursor=None
    for page in range(5):
        params={'part':'snippet,contentDetails','playlistId':playlist,'maxResults':50}
        if cursor:params['pageToken']=cursor
        data=request('get','https://www.googleapis.com/youtube/v3/playlistItems',headers=headers,params=params)
        videos.extend({'id':x['contentDetails']['videoId'],'title':x['snippet']['title']} for x in data.get('items',[]))
        cursor=data.get('nextPageToken')
        if not cursor:break
    if cursor:raise PlatformBlocked('youtube_history_incomplete')
    ig_headers={'Authorization':'Bearer '+os.environ.get('INSTAGRAM_ACCESS_TOKEN','')}
    permissions=request('get','https://graph.facebook.com/v26.0/me/permissions',headers=ig_headers)
    granted={x.get('permission') for x in permissions.get('data',[]) if x.get('status')=='granted'}
    if not granted & {'instagram_basic','instagram_business_basic'}:raise PlatformBlocked('instagram_read_scope_missing')
    if not granted & {'instagram_content_publish','instagram_business_content_publish'}:raise PlatformBlocked('instagram_publish_scope_missing')
    media=[];cursor=None
    for page in range(5):
        params={'fields':'id,caption,permalink','limit':50}
        if cursor:params['after']=cursor
        data=request('get','https://graph.facebook.com/v26.0/'+os.environ.get('INSTAGRAM_USER_ID','')+'/media',headers=ig_headers,params=params)
        media.extend({'id':x['id'],'title':x.get('caption','')} for x in data.get('data',[]))
        paging=data.get('paging',{})
        cursor=paging.get('cursors',{}).get('after') if paging.get('next') else None
        if not cursor:break
    if cursor:raise PlatformBlocked('instagram_history_incomplete')
    # A valid token for a different channel is not acceptable.
    for platform,items,id_field in [('youtube',videos,'video_id'),('instagram',media,'media_id')]:
        expected=[row[platform].get(id_field) for key,row in sorted(ledger['stories'].items(),key=lambda kv:int(kv[0]))
                  if row[platform].get('status')=='published'][-2:]
        if not expected or not set(expected)<=set(x['id'] for x in items):raise PlatformBlocked(platform+'_account_does_not_match_recent_ledger')
        aliases={normalized(topic),normalized(title)}
        recorded=ledger['stories'].get(str(number),{}).get(platform,{})
        already_verified_id=recorded.get(id_field) if recorded.get('status')=='published' else None
        for item in items:
            if item['id']==already_verified_id:continue
            text=normalized(item['title'])
            if any(alias and alias in text for alias in aliases) or re.search(rf'(?<!\d)#{number}(?!\d)',item['title']):
                raise PlatformBlocked(platform+'_candidate_already_present_requires_reconciliation')
    return {'youtube_upload_and_read_scopes_verified':True,'instagram_read_and_publish_scopes_verified':True,
        'recent_ledger_accounts_match':True,'youtube_history_items':len(videos),'instagram_history_items':len(media),
        'candidate_title_or_number_found':False,'history_complete_within_scan_limit':True,
        'limitation':'Titles and stored IDs are checked; renamed or otherwise unidentifiable manual uploads still require human review.'}
