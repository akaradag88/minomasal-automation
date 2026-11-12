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
    CF_MODEL, CF_DEFAULT_STEPS, Cloudflare, ProviderFailure, http, json_response, load_config,
    normalize, contain_box, sha, verify_cloudflare_free_plan, write_json,
)
from minomasal_visual_profile import build_prompt, identity_text, profile_digest, review_contract

ROOT='https://api.cloudflare.com/client/v4'
BRANCH='refs/heads/feat/adim-10-9-free-image-providers'
FREE_NEURONS=10_000
RESERVED_NEURONS=1_000  # Conservative buffer; two single-attempt image POSTs only.
PLAN=json.loads(Path(__file__).with_name('minomasal_flux_quality_profile.json').read_text())
CHARACTER=identity_text(PLAN['profile'])
SCENES=tuple(scene['action'] for scene in PLAN['scenes'])
BACKGROUND_SCENES=(
    'An empty woodland path in a sunny forest clearing, low bushes on the right, soft daylight.',
    'A different empty woodland path beside a large tree on the left, low bushes on the right, soft daylight.',
)
BACKGROUND_STYLE=('Flat hand-painted children\'s picture-book background, matte colors, clean rounded outlines. '
                  'Unoccupied scenery only: zero animals, zero people, zero vehicles, zero toys. '
                  'Blank unmarked surfaces, no words, letters, signs, logos or watermarks. '
                  'Keep the central ground clear for later local sprite placement.')


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


def run_check(output, generate=False, *, backgrounds_only=False, plan=None):
    plan=PLAN if plan is None else plan
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    account=os.environ.get('CLOUDFLARE_ACCOUNT_ID','').strip()
    token=os.environ.get('CLOUDFLARE_API_TOKEN','').strip()
    usage_token=os.environ.get('CLOUDFLARE_USAGE_TOKEN','').strip()
    report={'model':CF_MODEL,'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'secrets_present':{'account_id':bool(account),'api_token':bool(token),'usage_token':bool(usage_token)},
            'tokens_separated':bool(token and usage_token and token!=usage_token),
            'generation_parameters':{'request_fields':['prompt'],'steps_sent':False,
                'documented_default_steps':CF_DEFAULT_STEPS,'seed':None,'width_sent':False,'height_sent':False,
                'model':CF_MODEL,'max_image_requests':2},
            'mode':'backgrounds_only' if backgrounds_only else 'character_prompt_trial',
            'connection_verified':False,'free_plan_verified':False,'quota_verified':False,
            'paid_usage_allowed':False,'scenes':[], 'quality_decision':'not_reviewed',
            'license':{'model':'Apache-2.0','commercial_model_use_permitted':True,
                       'source':'https://huggingface.co/black-forest-labs/FLUX.1-schnell',
                       'cloudflare_service_terms_also_apply':True}}
    phase='credentials'
    try:
        # Validate both plans before any metadata or inference request.
        if len(plan['scenes'])!=2:raise ValueError('exactly_two_test_scenes_required')
        descriptions=BACKGROUND_SCENES if backgrounds_only else tuple(scene['action'] for scene in plan['scenes'])
        prompts=[f'{BACKGROUND_STYLE} {scene}' for scene in descriptions] if backgrounds_only else [build_prompt(plan['profile'],scene) for scene in plan['scenes']]
        report['visual_profile_sha256']=None if backgrounds_only else profile_digest(plan['profile'])
        report['quality_review']=review_contract()
        write_json(output/'visual-plan.json',{'mode':'backgrounds_only','prompts':prompts} if backgrounds_only else plan)
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
        # Fixed structural diagnostics only: no subscription names, IDs, raw
        # errors, response keys, credentials or account/billing values.
        info=subscriptions.get('result_info')
        report['subscription_response_shape']={
            'success_is_true':subscriptions.get('success') is True,
            'result_is_list':isinstance(subscriptions.get('result'),list),
            'result_is_object':isinstance(subscriptions.get('result'),dict),
            'result_count':len(subscriptions['result']) if isinstance(subscriptions.get('result'),list) else None,
            'metadata_present':info is not None,
            'metadata_is_object':isinstance(info,dict),
            'total_count_is_integer':isinstance(info,dict) and type(info.get('total_count')) is int,
            'total_count_matches':isinstance(info,dict) and isinstance(subscriptions.get('result'),list)
                and type(info.get('total_count')) is int and info['total_count']==len(subscriptions['result']),
        }
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
            config=load_config();config['http_attempts']=1
            provider=Cloudflare(config);provider.account=account;provider.token=token;provider.model=CF_MODEL
            for i,scene in enumerate(descriptions,1):
                # Re-read the quota and do not cross the UTC reset boundary silently.
                phase=f'quota_before_scene_{i}'
                fresh=query_quota(account,usage_token)
                if (fresh['utc_day']!=report['quota']['utc_day']
                        or fresh['remaining_neurons_reported']<RESERVED_NEURONS):
                    raise ProviderFailure('cloudflare','free_quota_changed')
                phase=f'image_{i}'
                prompt=prompts[i-1]
                (output/f'scene-{i}.prompt.txt').write_text(prompt+'\n')
                started=time.monotonic();data=provider.generate(prompt,i)
                vertical=output/f'scene-{i}.vertical.jpg'
                size=normalize(data,vertical,framing='contain')
                with Image.open(io.BytesIO(data)) as image:
                    extension='png' if image.format=='PNG' else 'jpg' if image.format=='JPEG' else None
                if not extension:raise ProviderFailure('cloudflare','unexpected_image_format')
                original=output/f'scene-{i}.original.{extension}';original.write_bytes(data)
                report['scenes'].append({'scene':i,'description':scene,'original':original.name,
                    'vertical':vertical.name,'source_size':size,'output_size':[1080,1920],
                    'framing':'contain','content_box':contain_box(size),
                    'planned_inventory':{'characters':0,'vehicles':0} if backgrounds_only else plan['scenes'][i-1]['inventory'],
                    'seconds':round(time.monotonic()-started,2),'sha256':sha(original)})
            report['character_bible']=None if backgrounds_only else identity_text(plan['profile'])
            if backgrounds_only:report['background_semantics_approved']=False
            report['status']='two_images_generated_review_required'
    except ProviderFailure as exc:
        report.update(status='blocked_no_publish',blocked_at=phase,reason=exc.reason,http_status=exc.status)
        if exc.api_errors:report['api_errors']=exc.api_errors
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
    parser.add_argument('--backgrounds-only',action='store_true')
    args=parser.parse_args()
    if not (os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and os.environ.get('GITHUB_REPOSITORY')=='akaradag88/minomasal-automation'
            and os.environ.get('GITHUB_REF')==BRANCH):
        raise SystemExit('Only the manually dispatched PR #4 branch test may execute this probe.')
    report=run_check('cloudflare_test_output',args.generate_two_scenes,backgrounds_only=args.backgrounds_only)
    text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)
    print(text)
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as dest:
            dest.write('## Cloudflare FLUX — no video or publication\n\n```json\n'+text+'\n```\n')
    return 1 if report['status']=='blocked_no_publish' else 0


if __name__=='__main__':raise SystemExit(main())
