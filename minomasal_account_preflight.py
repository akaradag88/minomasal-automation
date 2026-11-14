"""Account-only diagnostics. No images, video, ledger writes or publication.

Never prints or persists tokens, token hashes, client IDs or raw API errors.
"""
import json
import os
from pathlib import Path
import requests

READ='https://www.googleapis.com/auth/youtube.readonly'
UPLOAD='https://www.googleapis.com/auth/youtube.upload'
BROAD={'https://www.googleapis.com/auth/youtube','https://www.googleapis.com/auth/youtube.force-ssl'}


def expected_videos():
    ledger=json.loads(Path('minomasal_platform_durumu.json').read_text())
    return [row['youtube']['video_id'] for _,row in sorted(ledger['stories'].items(),key=lambda p:int(p[0]))
            if row.get('youtube',{}).get('status')=='published'][-2:]


def youtube(refresh,*,transport=requests):
    report={'refresh_token_present':bool(refresh),'upload_scope_verified':False,'read_scope_verified':False,
        'channel_matches_ledger':False,'upload_test_performed':False,'token_revoked':False}
    if not refresh:
        report['status']='not_configured';return report
    try:
        response=transport.post('https://oauth2.googleapis.com/token',data={
            'client_id':os.environ.get('YOUTUBE_CLIENT_ID'),'client_secret':os.environ.get('YOUTUBE_CLIENT_SECRET'),
            'refresh_token':refresh,'grant_type':'refresh_token'},timeout=30)
        report['refresh_http_status']=response.status_code
        if response.status_code!=200:
            report['status']='refresh_failed_with_existing_client';return report
        data=response.json();scopes=set(data.get('scope','').split())
        report['upload_scope_verified']=bool(scopes & (BROAD|{UPLOAD}))
        report['read_scope_verified']=bool(scopes & (BROAD|{READ}))
        headers={'Authorization':'Bearer '+data['access_token']}
        response=transport.get('https://www.googleapis.com/youtube/v3/channels',
            headers=headers,params={'part':'id','mine':'true'},timeout=30)
        report.update(channel_http_status=response.status_code,endpoint='GET /youtube/v3/channels?part=id&mine=true')
        if response.status_code!=200:
            if response.status_code==403:
                reasons={item.get('reason') for item in response.json().get('error',{}).get('errors',[])}
                report['safe_reason']='insufficientPermissions' if 'insufficientPermissions' in reasons else 'details_withheld'
            report['status']='channel_read_blocked';return report
        channels={item['id'] for item in response.json().get('items',[])}
        expected=expected_videos()
        if not expected:report['status']='ledger_identity_evidence_missing';return report
        response=transport.get('https://www.googleapis.com/youtube/v3/videos',headers=headers,
            params={'part':'snippet','id':','.join(expected)},timeout=30)
        report['identity_http_status']=response.status_code
        if response.status_code!=200:report['status']='channel_identity_unverified';return report
        items=response.json().get('items',[])
        report['channel_matches_ledger']=set(expected)=={item['id'] for item in items} and len(channels)==1 and all(item['snippet']['channelId'] in channels for item in items)
        report['status']='verified' if report['channel_matches_ledger'] and report['upload_scope_verified'] and report['read_scope_verified'] else 'scope_or_channel_mismatch'
    except Exception:report['status']='verification_failed_details_withheld'
    return report


def gemini(output,*,transport=requests):
    report={'key_present':bool(os.environ.get('GEMINI_API_KEY')),'tts_models':[],'selected_model':None,
        'free_account_confirmed':os.environ.get('MINOMASAL_GEMINI_FREE_TIER_CONFIRMED')=='true',
        'remaining_free_quota':None,'quota_api_verified':False,'speech_test_performed':False,
        'commercial_output_terms_source':'https://ai.google.dev/gemini-api/terms',
        'pricing_source':'https://ai.google.dev/gemini-api/docs/pricing#gemini-3.8-flash-tts'}
    if not report['key_present']:report['status']='key_missing';return report
    try:
        cursor=None;models=[]
        for page in range(3):
            params={'pageSize':1000}
            if cursor:params['pageToken']=cursor
            response=transport.get('https://generativelanguage.googleapis.com/v1beta/models',
                headers={'x-goog-api-key':os.environ['GEMINI_API_KEY']},params=params,timeout=30)
            report['models_http_status']=response.status_code
            if response.status_code!=200:report['status']='model_access_failed';return report
            data=response.json();models.extend(data.get('models',[]));cursor=data.get('nextPageToken')
            if not cursor:break
        report['catalog_complete']=not bool(cursor)
        report['tts_models']=sorted(item['name'].removeprefix('models/') for item in models if 'tts' in item.get('name','').lower())
        configured='gemini-3.8-flash-tts'
        if configured not in report['tts_models']:report['status']='configured_model_unavailable';return report
        report['selected_model']=configured;report['voice']='Sami'
        if not report['free_account_confirmed']:
            report['status']='blocked_free_plan_and_quota_require_owner_evidence';return report
        from minomasal_sami_tts_interactions import create_sami_wav
        import wave
        report['speech_test_performed']=True
        path=create_sami_wav('Merhaba çocuklar. Tonton bugün sakin kalıp yolunu bulmayı öğreniyor.',Path(output)/'turkish-sami-test.wav')
        with wave.open(str(path)) as sound:
            seconds=sound.getnframes()/sound.getframerate()
            if not 1<=seconds<=45:raise ValueError()
            report.update(wav_valid=True,seconds=round(seconds,3),human_listening_required=True,status='speech_sample_created_review_required')
    except Exception as error:
        code=getattr(error,'code',None)
        report.update(status='request_failed_details_withheld',http_status=code if type(code) is int else None)
    return report


def main():
    output=Path('account_preflight_output');output.mkdir(exist_ok=False)
    report={'current_youtube':youtube(os.environ.get('YOUTUBE_REFRESH_TOKEN','')),
        'candidate_youtube':youtube(os.environ.get('YOUTUBE_REFRESH_TOKEN_CANDIDATE','')),
        'gemini':gemini(output),'ledger_written':False,'published':False,'secrets_updated':False}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as stream:stream.write('## Account verification only — no publication\n\n```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n')

if __name__=='__main__':main()
