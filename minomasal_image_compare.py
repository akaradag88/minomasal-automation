"""Two-scene image-only comparison. Explicit opt-in and verified free access.

Never imports produce(), voices(), render(), or publishers. Defaults to plan only.
Cloudflare requires credentials AND Workers Free confirmation; OVH sends no key.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time

import minomasal_images as images

CHARACTER='Mino, a small orange fox with a white muzzle and green eyes, wearing blue overalls and a red scarf'
SCENES=(
    'Mino holds a yellow watering can beside a small oak sapling in a sunny forest clearing',
    'Mino carries a small wooden basket across a forest path beside the same oak sapling',
)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--provider',choices=('ovhcloud','cloudflare'),required=True)
    parser.add_argument('--real-free-test',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('image_comparison'))
    args=parser.parse_args()
    if not args.real_free_test:
        print('PLAN ONLY: exactly two character scenes; no API calls. Use --real-free-test only after free policy verification.')
        return
    config=images.load_config();config['scene_count']=2
    provider=images.PROVIDERS[args.provider](config)
    # Refuse re-running a completed comparison by accident. User artifacts remain.
    target=args.output/args.provider
    target.mkdir(parents=True,exist_ok=False)
    result={'provider':args.provider,'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'mode':'free_image_only','scenes':[],'paid_requests_allowed':False}
    try:
        provider.preflight()
        result['free_policy']='anonymous_no_billing_credential' if args.provider=='ovhcloud' else 'operator_confirmed_workers_free_plan'
        result['model']=provider.model
        for i,scene in enumerate(SCENES,1):
            prompt=f'CHARACTER BIBLE (unchanged): {CHARACTER}. SCENE: {scene}. {images.STYLE}'
            started=time.monotonic()
            data=provider.generate(prompt,i)
            path=target/f'{i:02}.jpg'
            source_size=images.normalize(data,path)
            (target/f'{i:02}.source').write_bytes(data)
            result['scenes'].append({'scene':i,'source_size':source_size,'output_size':[1080,1920],
                                    'seconds':round(time.monotonic()-started,2),'sha256':images.sha(path)})
        result['status']='two_images_generated_semantic_review_required'
    except images.ImageFailure as exc:
        result['status']='blocked_no_publish'
        result['error']=str(exc)
    images.write_json(target/'result.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
