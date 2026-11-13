"""Read-only recovery audit: no media generation, uploads or ledger writes."""
import json,os
from pathlib import Path
import requests
from minomasal_cloudflare_quality_test import run_check
from minomasal_daily_live import choose,KONULAR,LEDGER
from minomasal_ledger import read

SAFE_REASONS={'insufficientPermissions','accessNotConfigured','quotaExceeded','dailyLimitExceeded','forbidden','youtubeSignupRequired','authError'}

def safe_youtube_error(response):
    """Return only known diagnostic codes; never raw upstream text or credentials."""
    try:
        reasons={item.get('reason') for item in response.json().get('error',{}).get('errors',[])}
        return sorted(reasons & SAFE_REASONS) or ['unclassified_response_withheld']
    except (ValueError,TypeError,AttributeError):
        return ['unclassified_response_withheld']

def main():
    out=Path(os.environ.get('MINOMASAL_AUDIT_OUTPUT','asset_test_output/recovery'));out.mkdir(parents=True,exist_ok=False)
    names=('CLOUDFLARE_API_TOKEN','CLOUDFLARE_USAGE_TOKEN','CLOUDFLARE_ACCOUNT_ID','POLLINATIONS_API_KEY',
           'GEMINI_API_KEY','YOUTUBE_CLIENT_ID','YOUTUBE_CLIENT_SECRET','YOUTUBE_REFRESH_TOKEN',
           'INSTAGRAM_ACCESS_TOKEN','INSTAGRAM_USER_ID','MINOMASAL_HOSTING_TOKEN')
    report={'secrets_present':{name:bool(os.environ.get(name)) for name in names},'publishing_allowed':False}
    report['secrets_present']['MINOMASAL_HOSTING_TOKEN']=bool(os.environ.get('MINOMASAL_HOSTING_TOKEN')) or os.environ.get('MINOMASAL_HOSTING_SECRET_PRESENT')=='true'
    report['secrets_present']['POLLINATIONS_API_KEY']=bool(os.environ.get('POLLINATIONS_API_KEY')) or os.environ.get('MINOMASAL_POLLINATIONS_SECRET_PRESENT')=='true'
    ledger=read(LEDGER);number=choose(ledger)
    report['ledger_next']={'number':number,'topic':KONULAR[number-1] if number else None}
    report['recent_ledger']={key:row for key,row in ledger['stories'].items() if int(key)>=43}
    report['cloudflare']=run_check(out/'cloudflare',False)
    try:
        r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ.get('YOUTUBE_CLIENT_ID'),
            'client_secret':os.environ.get('YOUTUBE_CLIENT_SECRET'),'refresh_token':os.environ.get('YOUTUBE_REFRESH_TOKEN'),
            'grant_type':'refresh_token'},timeout=30)
        report['youtube']={'token_http_status':r.status_code}
        if r.status_code==200:
            scopes=set(r.json().get('scope','').split())
            report['youtube']['scope_metadata_returned']=bool(scopes)
            report['youtube']['read_scope_present']=bool(scopes & {'https://www.googleapis.com/auth/youtube.readonly','https://www.googleapis.com/auth/youtube','https://www.googleapis.com/auth/youtube.force-ssl'})
            report['youtube']['upload_scope_present']=bool(scopes & {'https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube','https://www.googleapis.com/auth/youtube.force-ssl'})
        token=r.json().get('access_token') if r.status_code==200 else None
        if token:
            h={'Authorization':'Bearer '+token}
            r=requests.get('https://www.googleapis.com/youtube/v3/channels',params={'part':'contentDetails','mine':'true'},headers=h,timeout=30)
            report['youtube']['channel_http_status']=r.status_code
            if r.status_code!=200: report['youtube']['safe_reasons']=safe_youtube_error(r)
            if r.status_code==200 and r.json().get('items'):
                playlist=r.json()['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                r=requests.get('https://www.googleapis.com/youtube/v3/playlistItems',params={'part':'snippet,contentDetails','playlistId':playlist,'maxResults':50},headers=h,timeout=30)
                report['youtube']['recent_http_status']=r.status_code
                report['youtube']['history_complete']=r.status_code==200 and not r.json().get('nextPageToken')
                if r.status_code==200:report['youtube']['recent']=[{'title':v['snippet']['title'],'video_id':v['contentDetails']['videoId']} for v in r.json().get('items',[])]
    except Exception:report.setdefault('youtube',{})['error']='read_only_audit_failed_raw_details_withheld'
    try:
        r=requests.get('https://graph.facebook.com/v26.0/'+os.environ.get('INSTAGRAM_USER_ID','')+'/media',
            params={'fields':'id,caption,permalink,timestamp','limit':50},headers={'Authorization':'Bearer '+os.environ.get('INSTAGRAM_ACCESS_TOKEN','')},timeout=30)
        report['instagram']={'http_status':r.status_code}
        report['instagram']['history_complete']=r.status_code==200 and not r.json().get('paging',{}).get('next')
        if r.status_code==200:report['instagram']['recent']=[{'id':v['id'],'caption':v.get('caption','')[:180],'permalink':v.get('permalink'),'timestamp':v.get('timestamp')} for v in r.json().get('data',[])]
    except Exception:report.setdefault('instagram',{})['error']='read_only_audit_failed_raw_details_withheld'
    try:
        r=requests.get('https://graph.facebook.com/v26.0/me/permissions',
            headers={'Authorization':'Bearer '+os.environ.get('INSTAGRAM_ACCESS_TOKEN','')},timeout=30)
        allowed={'instagram_basic','instagram_content_publish','pages_show_list','pages_read_engagement',
                 'instagram_business_basic','instagram_business_content_publish'}
        granted={item.get('permission') for item in r.json().get('data',[]) if item.get('status')=='granted'} if r.status_code==200 else set()
        report['instagram_permissions']={'http_status':r.status_code,
            'granted_known_scopes':sorted(granted & allowed),
            'publish_scope_verified':r.status_code==200 and bool(granted & {'instagram_content_publish','instagram_business_content_publish'}),
            'read_scope_verified':r.status_code==200 and bool(granted & {'instagram_basic','instagram_business_basic'}),
            'no_publish_request_sent':True}
    except Exception:report['instagram_permissions']={'error':'permission_metadata_unavailable_details_withheld','publish_scope_verified':False}
    try:
        r=requests.get('https://generativelanguage.googleapis.com/v1beta/models',
            headers={'x-goog-api-key':os.environ.get('GEMINI_API_KEY','')},timeout=30)
        report['speech']={'model_catalog_http_status':r.status_code,'generation_tested':False,'free_generation_verified':False}
        if r.status_code==200:
            report['speech']['configured_model_listed']=any(m.get('name')=='models/gemini-3.8-flash-tts' for m in r.json().get('models',[]))
            report['text']={'catalog_http_status':200,'model':'gemini-3.8-flash','model_listed':any(m.get('name')=='models/gemini-3.8-flash' for m in r.json().get('models',[])),'inference_tested':False}
    except Exception: report['speech']={'error':'metadata_check_failed_raw_details_withheld','generation_tested':False}
    # Metadata success must never be represented as successful synthesis.
    report['speech']['free_account_attested']=os.environ.get('MINOMASAL_GEMINI_FREE_TIER_CONFIRMED')=='true'
    if report['speech']['free_account_attested'] and report['speech'].get('configured_model_listed') is True and os.environ.get('MINOMASAL_TEST_REAL_TTS')=='true':
        try:
            from minomasal_sami_tts_interactions import create_sami_wav
            import wave
            wav=create_sami_wav('Merhaba çocuklar. Tonton bugün sakin kalıp yolunu bulmayı öğreniyor.',out/'turkish-sami-test.wav')
            with wave.open(str(wav)) as sound:
                report['speech'].update(generation_tested=True,wav_valid=True,seconds=round(sound.getnframes()/sound.getframerate(),3),
                    free_generation_verified=True,human_listening_required=True)
        except Exception as error:
            code=getattr(error,'code',None)
            report['speech'].update(generation_tested=True,generation_failed=True,http_status=code if type(code) is int else None,error='tts_request_failed_details_withheld')
    else:
        report['speech']['generation_blocked_reason']='free_account_not_attested_or_test_not_requested'
    from minomasal_recovery_package import build_package
    try:report['review_package']=build_package(out/'review_package')
    except (ValueError,RuntimeError):report['review_package']={'status':'not_current_candidate_or_reconciliation_required'}
    # Independent title/number matching is evidence, not a content fingerprint.
    from minomasal_platform_gate import normalized
    canonical=json.loads(Path('minomasal_v4_47_revize_hikaye.json').read_text())
    aliases=[normalized(KONULAR[46]),normalized(canonical['title'])]
    report['candidate_47_history']={}
    for platform in ('youtube','instagram'):
        history=report.get(platform,{})
        matches=[item for item in history.get('recent',[]) if any(alias in normalized(item.get('title',item.get('caption',''))) for alias in aliases)]
        report['candidate_47_history'][platform]={'history_complete':history.get('history_complete') is True,
            'candidate_title_matches':len(matches),'absence_verified_by_title':history.get('history_complete') is True and not matches,
            'limitation':'renamed_or_unidentifiable_manual_uploads_require_human_reconciliation'}
    report['candidate_47_history']['both_platforms_verified']=all(report['candidate_47_history'][p]['absence_verified_by_title'] for p in ('youtube','instagram'))
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'audit_saved':True,'secrets_present':report['secrets_present'],'youtube_status':report.get('youtube',{}).get('channel_http_status'),
                     'instagram_status':report.get('instagram',{}).get('http_status'),'number':number,'publishing_allowed':False}))

if __name__=='__main__':main()
