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
           'only a plain blue scarf, no other clothes. His only toy truck has a bright red cab, '
           'bright red tipper bed, four black wheels and no writing. Keep exactly this design.')
SCENES=(
    'Mino plays with his red toy truck on a forest path. The entire truck is clearly visible beside his paws.',
    'The same Mino searches for the toy truck in the forest, looking behind a tree. The unchanged truck is fully visible to the viewer beside a nearby bush while the fox looks elsewhere.',
)
STYLE='Warm colorful storybook illustration, full body, portrait-friendly centered composition, one fox only, no text.'


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def query_quota(account,token):
    from minomasal_cloudflare_usage import query_quota as read_usage
    return read_usage(account,token,transport=http)


def request_context(phase):
    """Only static route templates: never put a real account ID in diagnostics."""
    if phase=='model_connection':
        method,path,permission='GET','/accounts/{account_id}/ai/models/search','Workers AI Read'
    elif phase=='free_plan':
        method,path,permission='GET','/accounts/{account_id}/subscriptions','Billing Read'
    elif phase.startswith('quota'):
        method,path,permission='POST','/graphql','Account Analytics Read'
    elif phase.startswith('image_'):
        method,path,permission='POST','/accounts/{account_id}/ai/run/{model_name}','Workers AI Read'
    else:
        return {}
    return {'request_method':method,'endpoint_template':path,
            'documented_minimum_permission':permission}


def run_check(output, generate=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    account=os.environ.get('CLOUDFLARE_ACCOUNT_ID','').strip()
    token=os.environ.get('CLOUDFLARE_API_TOKEN','').strip()
    usage_token=os.environ.get('CLOUDFLARE_USAGE_TOKEN','').strip()
    report={'model':CF_MODEL,'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'secrets_present':{'account_id':bool(account),'api_token':bool(token),'usage_token':bool(usage_token)},
            'tokens_separated':bool(token and usage_token and token!=usage_token),
            'generation_parameters':{'steps':4,'seed':1234,'model':CF_MODEL,'max_image_requests':2},
            'connection_verified':False,'free_plan_verified':False,'quota_verified':False,
            'paid_usage_allowed':False,'scenes':[], 'quality_decision':'not_reviewed',
            'license':{'model':'Apache-2.0','commercial_model_use_permitted':True,
                       'source':'https://huggingface.co/black-forest-labs/FLUX.1-schnell',
                       'cloudflare_service_terms_also_apply':True}}
    phase='credentials'
    try:
        if not re.fullmatch('[a-fA-F0-9]{32}',account) or not token:
            raise ProviderFailure('cloudflare','credentials_missing_or_invalid')
        if not usage_token:
            raise ProviderFailure('cloudflare','usage_token_missing')
        if usage_token==token:
            raise ProviderFailure('cloudflare','usage_token_must_be_distinct')
        headers={'Authorization':'Bearer '+token}
        usage_headers={'Authorization':'Bearer '+usage_token}
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
                                         headers=usage_headers),'cloudflare')
        report['plan_proof']=verify_cloudflare_free_plan(subscriptions)
        report['free_plan_verified']=True
        phase='quota'
        report['quota']=query_quota(account,usage_token)
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
                fresh=query_quota(account,usage_token)
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
        report.update(request_context(phase))
        if phase=='free_plan' and exc.status==403:
            report['next_action']='check_subscription_read_access_or_dashboard_plan_verification'
        elif phase.startswith('quota'):
            report['next_action']='check_account_analytics_read_and_quota_availability'
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
