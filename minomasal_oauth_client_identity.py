"""Nonced candidate-ID equality check. Stored credentials never leave Actions.

Local browser sends only one-use proofs of candidate OAuth CLIENT IDENTIFIERS.
No access/refresh token, API key or Client Secret is fingerprinted or exported.
The HMAC of the configured Secret is calculated in memory and NEVER reported.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import requests

DOMAIN=b'minomasal-client-match/v1\0'
NAMES={'analytics':'MinoMasal Analytics Client','colab':'MinoMasal Colab Client'}

def parse_packet(value):
    try:
        if isinstance(value,str):
            if len(value)>1024:raise ValueError()
            value=json.loads(value)
        if not isinstance(value,dict) or set(value)!={'version','nonce','analytics','colab'} or type(value['version']) is not int or value['version']!=1:raise ValueError()
        if any(not isinstance(value[k],str) or not re.fullmatch('[0-9a-f]{64}',value[k]) for k in ('nonce','analytics','colab')):raise ValueError()
        if value['analytics']==value['colab']:raise ValueError()
        return value
    except Exception:raise ValueError('invalid_comparison_packet_no_credentials_processed') from None

def compare(packet,*,transport=requests.post):
    packet=parse_packet(packet)
    report={'request_nonce':packet['nonce'],'matched_client':None,'refresh_pair_verified':False,
            'confirmed_choice':None,'secrets_modified':False,'token_revoked':False,'published':False}
    client=os.environ.get('YOUTUBE_CLIENT_ID','').strip()
    if not client:report['status']='configured_client_id_missing';return report
    proof=hmac.new(bytes.fromhex(packet['nonce']),DOMAIN+client.encode(),hashlib.sha256).hexdigest()
    matches=[name for name in NAMES if hmac.compare_digest(proof,packet[name])]
    if len(matches)!=1:report['status']='neither_candidate_matches_configured_client';return report
    report['matched_client']=NAMES[matches[0]]
    secret=os.environ.get('YOUTUBE_CLIENT_SECRET','');refresh=os.environ.get('YOUTUBE_REFRESH_TOKEN','')
    if not secret or not refresh:report['status']='configured_pair_incomplete';return report
    try:
        response=transport('https://oauth2.googleapis.com/token',data={
            'client_id':client,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=30)
        report['refresh_http_status']=response.status_code
        data=response.json() if response.status_code==200 else {}
        report['refresh_pair_verified']=isinstance(data.get('access_token'),str) and bool(data['access_token'])
        if report['refresh_pair_verified']:
            report.update(status='verified',confirmed_choice=report['matched_client'])
        else:report['status']='client_id_matches_but_refresh_unverified'
    except Exception:report['status']='client_id_matches_but_refresh_check_failed_details_withheld'
    return report

def main():
    if not (os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and os.environ.get('GITHUB_REPOSITORY')=='akaradag88/minomasal-automation'
            and os.environ.get('GITHUB_REF')=='refs/heads/fix/end-to-end-engine-2026-11-13'):
        raise SystemExit('Only the dedicated manual client-match check may run.')
    try:
        event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        report=compare(event['inputs']['client_id_challenge'])
    except Exception:raise SystemExit('Client comparison stopped safely; raw inputs withheld.') from None
    output=Path('oauth_client_match_output');output.mkdir(exist_ok=False)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
