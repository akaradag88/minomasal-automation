"""Manual GitHub Actions only. Verify free access before two image requests.

No video/audio/publisher imports. No token, account ID, API body, or raw error
is logged or saved. The downloaded artifact contains only images and this report.
"""
import argparse
from datetime import datetime,timezone
import io
import json
import math
import os
from pathlib import Path
import re
import time

from PIL import Image
from minomasal_images import (
    CF_MODEL, Cloudflare, ProviderFailure, http, json_response, load_config,
    normalize, sha, verify_cloudflare_free_plan, write_json,
)

ROOT='https://api.cloudflare.com/client/v4'
BRANCH='refs/heads/feat/adim-10-9-free-image-providers'
FREE_NEURONS=10_000
RESERVED_NEURONS=1_000  # Conservative buffer; two single-attempt image POSTs only.
CHARACTER=('Mino is one small orange fox cub, white muzzle, green eyes, round face, '
           'blue dungarees, a plain red scarf. His only toy truck has a red cab, '
           'yellow tipper bed, four black wheels and no writing. Keep exactly this design.')
SCENES=(
    'Mino plays with his red-and-yellow toy truck on a forest path. The entire truck is clearly visible beside his paws.',
    'The same Mino searches for that toy truck in the forest, looking behind a tree. The same truck is partly visible beside the tree.',
)
STYLE='Warm colorful storybook illustration, full body, portrait-friendly centered composition, one fox only, no text.'


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def query_quota(account,token):
    now=datetime.now(timezone.utc)
    start=now.replace(hour=0,minute=0,second=0,microsecond=0).isoformat().replace('+00:00','Z')
    end=now.isoformat().replace('+00:00','Z')
    # Account is validated hex and timestamps are generated locally. No arbitrary
    # queries/URLs/user input, model filter or dimensions that could omit usage.
    query=('query { viewer { accounts(filter: {accountTag: "'+account+'"}) { '
           'aiInferenceAdaptiveGroups(limit: 1, filter: {datetime_geq: "'+start+'", datetime_lt: "'+end+'"}) '
           '{ sum { totalNeurons } } } } }')
    payload=json_response(http('cloudflare','POST',ROOT+'/graphql',
                              headers={'Authorization':'Bearer '+token},json={'query':query}), 'cloudflare')
    if payload.get('errors'):
        raise ProviderFailure('cloudflare','quota_query_denied_or_unsupported')
    try:
        accounts=payload['data']['viewer']['accounts']
        if not isinstance(accounts,list) or len(accounts)!=1:raise ValueError()
        groups=accounts[0]['aiInferenceAdaptiveGroups']
        if not isinstance(groups,list) or len(groups)>1:raise ValueError()
        used=groups[0]['sum']['totalNeurons'] if groups else 0
        if not number(used):raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise ProviderFailure('cloudflare','quota_response_unverified') from None
    return {'utc_day':now.date().isoformat(),'used_neurons_reported':used,
            'free_daily_neurons':FREE_NEURONS,'remaining_neurons_reported':max(0,FREE_NEURONS-used),
            'source':'account_all_models_graphql','analytics_may_lag':True}


def run_check(output, generate=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    account=os.environ.get('CLOUDFLARE_ACCOUNT_ID','').strip()
    token=os.environ.get('CLOUDFLARE_API_TOKEN','').strip()
    report={'model':CF_MODEL,'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'secrets_present':{'account_id':bool(account),'api_token':bool(token)},
            'connection_verified':False,'free_plan_verified':False,'quota_verified':False,
            'paid_usage_allowed':False,'scenes':[], 'quality_decision':'not_reviewed',
            'license':{'model':'Apache-2.0','commercial_model_use_permitted':True,
                       'source':'https://huggingface.co/black-forest-labs/FLUX.1-schnell',
                       'cloudflare_service_terms_also_apply':True}}
    phase='credentials'
    try:
        if not re.fullmatch('[a-fA-F0-9]{32}',account) or not token:
            raise ProviderFailure('cloudflare','credentials_missing_or_invalid')
        headers={'Authorization':'Bearer '+token}
        phase='model_connection'
        models=json_response(http('cloudflare','GET',f'{ROOT}/accounts/{account}/ai/models/search',
                                  headers=headers,params={'search':CF_MODEL}),'cloudflare')
        if models.get('success') is not True or not isinstance(models.get('result'),list):
            raise ProviderFailure('cloudflare','model_access_unverified')
        if not any(isinstance(m,dict) and m.get('name')==CF_MODEL for m in models['result']):
            raise ProviderFailure('cloudflare','requested_model_not_available')
        report['connection_verified']=True
        phase='free_plan'
        subscriptions=json_response(http('cloudflare','GET',f'{ROOT}/accounts/{account}/subscriptions',
                                         headers=headers),'cloudflare')
        report['plan_proof']=verify_cloudflare_free_plan(subscriptions)
        report['free_plan_verified']=True
        phase='quota'
        report['quota']=query_quota(account,token)
        if report['quota']['remaining_neurons_reported']<RESERVED_NEURONS:
            raise ProviderFailure('cloudflare','insufficient_verified_free_quota')
        report['quota_verified']=True
        report['reserved_neurons']=RESERVED_NEURONS
        if not generate:
            report['status']='preflight_passed_generation_not_requested'
        else:
            config=load_config();config['cloudflare_steps']=4;config['http_attempts']=1
            provider=Cloudflare(config);provider.account=account;provider.token=token;provider.model=CF_MODEL
            for i,scene in enumerate(SCENES,1):
                # Re-read the quota and do not cross the UTC reset boundary silently.
                phase=f'quota_before_scene_{i}'
                fresh=query_quota(account,token)
                if (fresh['utc_day']!=report['quota']['utc_day']
                        or fresh['remaining_neurons_reported']<RESERVED_NEURONS):
                    raise ProviderFailure('cloudflare','free_quota_changed')
                phase=f'image_{i}'
                prompt=f'{CHARACTER} Scene: {scene} {STYLE}'
                started=time.monotonic();data=provider.generate(prompt,i)
                vertical=output/f'scene-{i}.vertical.jpg'
                size=normalize(data,vertical)
                with Image.open(io.BytesIO(data)) as image:
                    extension='png' if image.format=='PNG' else 'jpg' if image.format=='JPEG' else None
                if not extension:raise ProviderFailure('cloudflare','unexpected_image_format')
                original=output/f'scene-{i}.original.{extension}';original.write_bytes(data)
                report['scenes'].append({'scene':i,'description':scene,'original':original.name,
                    'vertical':vertical.name,'source_size':size,'output_size':[1080,1920],
                    'seconds':round(time.monotonic()-started,2),'sha256':sha(original)})
            report['character_bible']=CHARACTER
            report['status']='two_images_generated_review_required'
    except ProviderFailure as exc:
        report.update(status='blocked_no_publish',blocked_at=phase,reason=exc.reason,http_status=exc.status)
    except Exception:
        # Never expose upstream bodies, sensitive exception values or local paths.
        report.update(status='blocked_no_publish',blocked_at=phase,reason='unexpected_response_or_runtime_error')
    write_json(output/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--generate-two-scenes',action='store_true')
    args=parser.parse_args()
    if not (os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and os.environ.get('GITHUB_REPOSITORY')=='akaradag88/minomasal-automation'
            and os.environ.get('GITHUB_REF')==BRANCH):
        raise SystemExit('Only the manually dispatched PR #4 branch test may execute this probe.')
    report=run_check('cloudflare_test_output',args.generate_two_scenes)
    text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)
    print(text)
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as dest:
            dest.write('## Cloudflare FLUX — no video or publication\n\n```json\n'+text+'\n```\n')
    return 1 if report['status']=='blocked_no_publish' else 0


if __name__=='__main__':raise SystemExit(main())
