"""Read-only Pollinations account check. Never generates content or logs a key.

Only documented GET /account/key and /account/balance endpoints are allowed.
No generation endpoints, redirects, retries, payments, or publishing imports.
"""
import json
import math
import os
from pathlib import Path
import urllib.error
import urllib.request

BASE = 'https://gen.pollinations.ai'
ALLOWED = ('/account/key', '/account/balance')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def account_get(path, key):
    if path not in ALLOWED:
        raise ValueError('Only free read-only account endpoints are allowed.')
    request = urllib.request.Request(BASE + path, method='GET', headers={
        'Authorization': 'Bearer ' + key,
        'Accept': 'application/json',
        'User-Agent': 'MinoMasal-ReadOnly-Account-Check',
    })
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            body=response.read(131073)
            if len(body)>131072:
                return {'http_status':response.status, 'error':'response_too_large'}, None
            try:
                data=json.loads(body)
            except (ValueError, UnicodeError):
                return {'http_status':response.status, 'error':'invalid_json'}, None
            if not isinstance(data,dict):
                return {'http_status':response.status, 'error':'invalid_schema'}, None
            return {'http_status':response.status},data
    except urllib.error.HTTPError as exc:
        # Do not read or print the error body, URL, headers, or exception text.
        return {'http_status':exc.code},None
    except Exception:
        return {'http_status':None, 'error':'connection_failed'},None


def numeric(value):
    return type(value) in (int,float) and math.isfinite(value)


def check(key):
    result={'secret_configured':bool(key), 'authenticated':False,
            'balance_verified':False, 'generation_tested':False}
    if not key:
        result['action']='configure_secret'
        return result
    key_info,key_data=account_get('/account/key',key)
    result['key_check']=key_info
    if key_info.get('http_status') != 200 or not key_data or key_data.get('valid') is False:
        status=key_info.get('http_status')
        result['action']=('account_or_key_budget_exhausted' if status==402 else
                          'invalid_or_expired_key' if status==401 else
                          'check_key_or_connection')
        return result
    result['authenticated']=True
    balance_info,balance_data=account_get('/account/balance',key)
    result['balance_check']=balance_info
    if balance_data and numeric(balance_data.get('balance')):
        result['balance_verified']=True
        result['available_pollen']=balance_data['balance']
        result['action']='account_or_key_budget_exhausted' if balance_data['balance']<=0 else 'positive_balance_generation_not_tested'
    elif balance_info.get('http_status')==402:
        result['action']='account_or_key_budget_exhausted'
    elif balance_info.get('http_status')==403:
        result['action']='balance_read_scope_required'
    else:
        result['action']='balance_unverified'
    return result


def main():
    key=os.environ.get('POLLINATIONS_API_KEY','').strip()
    result=check(key)
    # Fixed keys, booleans, numeric values and fixed labels only.
    report=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    Path('pollinations-account-check.json').write_text(report,encoding='utf-8')
    print(report,end='')
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as output:
            output.write('## Pollinations read-only account check\n\n```json\n'+report+'```\n')
    return 0 if result['authenticated'] and result['balance_verified'] and result.get('available_pollen',0)>0 else 1


if __name__=='__main__':
    raise SystemExit(main())
