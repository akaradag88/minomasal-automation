"""Run LOCALLY to add read scope while preserving upload scope. Never uploads.

Client JSON and refreshed token stay on the user's machine. No token is printed.
Requires the existing Google OAuth client, not a replacement application.
"""
import argparse
import csv
import io
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

SCOPES=('https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly')
AUTH='https://accounts.google.com/o/oauth2/v2/auth'
TOKEN='https://oauth2.googleapis.com/token'
WINDOWS=os.name=='nt'

class OAuthError(RuntimeError): pass

def load_client(path):
    try:
        raw=json.loads(Path(path).read_text())
        config=raw.get('installed',raw.get('web',{}))
        client_id=config['client_id'];client_secret=config['client_secret']
        if not isinstance(client_id,str) or not client_id.endswith('.apps.googleusercontent.com') or not isinstance(client_secret,str) or not client_secret:
            raise ValueError()
        return client_id,client_secret
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        raise OAuthError('Invalid local Google OAuth client file; contents withheld.') from None

def authorization_url(client_id,redirect,state,verifier):
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return AUTH+'?'+urllib.parse.urlencode({'client_id':client_id,'redirect_uri':redirect,
        'response_type':'code','scope':' '.join(SCOPES),'state':state,'access_type':'offline',
        'prompt':'consent','include_granted_scopes':'true','code_challenge':challenge,'code_challenge_method':'S256'})

def callback_code(query,expected_state):
    values=urllib.parse.parse_qs(query)
    state=values.get('state',[])
    code=values.get('code',[])
    if len(state)!=1 or not hmac.compare_digest(state[0].encode(),expected_state.encode()):
        raise OAuthError('OAuth state verification failed; credentials withheld.')
    if 'error' in values or len(code)!=1 or not code[0]:
        raise OAuthError('Google consent was not completed; details withheld.')
    return code[0]

def validate_tokens(data):
    if not isinstance(data,dict):raise OAuthError('Invalid token response; details withheld.')
    if not set(SCOPES).issubset(set(str(data.get('scope','')).split())):
        raise OAuthError('Both upload and read permissions are required; no secret saved.')
    if not all(isinstance(data.get(k),str) and data[k] for k in ('access_token','refresh_token')):
        raise OAuthError('Missing refreshed credentials; no secret saved.')
    return data['refresh_token'],data['access_token']

def write_private(path,token):
    # Exclusive creation: no overwrite of an existing file or symlink.
    fd=os.open(Path(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        if WINDOWS:
            # chmod alone does not establish a private Windows ACL. Restrict the
            # newly created EMPTY file before writing any credential bytes.
            who=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,timeout=10,check=True)
            sid=next(csv.reader(io.StringIO(who.stdout)))[1].strip()
            if not re.fullmatch(r'S-\d+(?:-\d+)+',sid):raise OAuthError('Windows identity verification failed.')
            subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r','*'+sid+':(R,W)'],
                capture_output=True,timeout=10,check=True)
        else:os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as out:
            fd=None;out.write(token+'\n')
    except Exception:
        if fd is not None:os.close(fd)
        Path(path).unlink(missing_ok=True)
        raise OAuthError('Private-file permissions could not be verified; no secret saved.') from None

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-file',required=True,help='Existing local Google OAuth client JSON; never paste it in chat.')
    parser.add_argument('--output',default='youtube-refresh-token.private')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS')=='true':raise OAuthError('This interactive helper must run locally, never in Actions.')
    if not 1024<=args.port<=65535:raise OAuthError('Use a local non-privileged port.')
    if Path(args.output).exists() or Path(args.output).is_symlink():raise OAuthError('Output already exists; nothing overwritten.')
    client_id,client_secret=load_client(args.client_file)
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
    redirect=f'http://127.0.0.1:{args.port}/'
    result={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Callback URL contains a secret authorization code.
        def do_GET(self):
            if urllib.parse.urlsplit(self.path).path!='/':
                self.send_error(404);return
            try:result['code']=callback_code(urllib.parse.urlsplit(self.path).query,state)
            except OAuthError:result['error']=True
            self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.end_headers()
            self.wfile.write(b'Consent received. Return to the local terminal. No video was uploaded.')
    with HTTPServer(('127.0.0.1',args.port),Handler) as server:
        server.timeout=1
        if not webbrowser.open(authorization_url(client_id,redirect,state,verifier)):
            raise OAuthError('Browser did not open; run locally on your laptop.')
        print('Complete Google consent in the browser. No upload or payment will occur.')
        deadline=time.monotonic()+300
        while not result and time.monotonic()<deadline:server.handle_request()
    if not result.get('code') or result.get('error'):raise OAuthError('Consent failed or timed out; no secret saved.')
    body=urllib.parse.urlencode({'client_id':client_id,'client_secret':client_secret,'code':result['code'],
        'grant_type':'authorization_code','redirect_uri':redirect,'code_verifier':verifier}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN,data=body),timeout=30) as response:data=json.load(response)
        refresh,access=validate_tokens(data)
        request=urllib.request.Request('https://www.googleapis.com/youtube/v3/channels?part=id&mine=true&maxResults=1',
            headers={'Authorization':'Bearer '+access})
        with urllib.request.urlopen(request,timeout=30) as response:channel=json.load(response)
        if not channel.get('items'):raise OAuthError('No YouTube channel found; no secret saved.')
        write_private(args.output,refresh)
    except OAuthError:raise
    except Exception:raise OAuthError('Token exchange, read verification or private-file save failed; details withheld.') from None
    print('Upload + read permissions and channel read verified. Refresh token saved privately; its value is never printed.')
    print('Update ONLY YOUTUBE_REFRESH_TOKEN in GitHub Actions Secrets from the private file, then remove that local file securely.')

if __name__=='__main__':
    try:main()
    except (OAuthError,OSError):raise SystemExit('Reauthorization stopped safely. No credentials printed or videos uploaded.') from None
