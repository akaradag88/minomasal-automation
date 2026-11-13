"""Two free-gated, text-only Tonton asset CANDIDATES. Never reference editing.

No source image is sent. They are not approved for production or publication.
"""
import argparse
import json
import os
from pathlib import Path
from minomasal_cloudflare_quality_test import run_check,BRANCH
from minomasal_asset_compositor import remove_uniform_background,AssetError,scan_text,read_image
from minomasal_images import write_json

ROOT=Path(__file__).resolve().parent

def trial(output,generate=False):
    output=Path(output)
    plan=json.loads((ROOT/'minomasal_tonton_asset_plan.json').read_text())
    result=run_check(output,generate,plan=plan)
    result['mode']='tonton_text_only_asset_candidates'
    result['reference_image_sent']=False
    result['matches_existing_reference_verified']=False
    result['production_approved']=False
    result['source_reference']='tonton_referans.png'
    result['warning']='Text-only approximation; different poses may redesign the character. Human reference comparison is mandatory.'
    result['sprite_candidates']=[]
    for scene in result['scenes']:
        source=output/scene['original'];destination=output/f"candidate-{scene['scene']}.png"
        item={'scene':scene['scene'],'approval':'pending','source':source.name}
        try:
            removal=remove_uniform_background(source,destination,(255,0,255),tolerance=24)
            item.update(png=destination.name,mask_status='pending_visual_review',quality=removal['quality'])
            item['ocr']=scan_text(read_image(destination,rgba=True))
        except AssetError as error:
            # AssetError reasons are static local codes; never upstream bodies.
            item.update(mask_status='blocked_manual_mask_required',reason=str(error))
        result['sprite_candidates'].append(item)
    write_json(output/'report.json',result)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generate-two-scenes',action='store_true')
    args=parser.parse_args()
    if not (os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and os.environ.get('GITHUB_REPOSITORY')=='akaradag88/minomasal-automation' and os.environ.get('GITHUB_REF')==BRANCH):
        raise SystemExit('Only the manually dispatched PR #4 test may run.')
    report=trial('cloudflare_test_output',args.generate_two_scenes)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return int(report['status']=='blocked_no_publish')

if __name__=='__main__':raise SystemExit(main())
