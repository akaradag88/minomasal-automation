"""Manual PR-only test demo. Synthetic proxies are NEVER production assets.

Optional explicit inference generates backgrounds only, after the existing free
plan/quota gate. Missing real characters never cause silent regeneration.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

from minomasal_asset_compositor import AssetError,compose_scene,compose_story,digest
from minomasal_asset_test_fixtures import make_fixtures

BRANCH='refs/heads/feat/adim-10-9-free-image-providers'


def run_demo(output,*,generate_backgrounds=False):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','assets_are_synthetic_test_fixtures':True,
            'real_story_character_approved':False,'real_story_character_identity_validated':False,
            'automation_quality_approved':False,'publishing_allowed':False,
            'new_inference_requests':0,'generated_characters':0}
    try:
        path,catalog,scenes=make_fixtures(root/'fixtures')
        # First prove composition locally before any optional quota/API traffic.
        for scene in scenes:compose_scene(path.parent,catalog,scene,test_fixtures=True,preview=True)
        report['baseline_layers_checked']=True
        if generate_backgrounds:
            from minomasal_cloudflare_quality_test import run_check
            cf=run_check(root/'cloudflare',True,backgrounds_only=True)
            report['cloudflare_report']='cloudflare/report.json'
            # This counter is exact on success; use phase to conservatively
            # report issued requests on a failed image call without reissuing it.
            report['new_inference_requests']=len(cf['scenes'])
            if cf.get('blocked_at','').startswith('image_'):
                report['new_inference_requests']=int(cf['blocked_at'].split('_')[-1])
            if cf['status']!='two_images_generated_review_required':
                report['reason']='free_gate_or_background_generation_blocked'
                return report
            for i,item in enumerate(cf['scenes'],1):
                source=root/'cloudflare'/item['original'];dest=root/'fixtures'/f'generated-background-{i}{source.suffix}'
                shutil.copyfile(source,dest)
                catalog['backgrounds'][f'background_{i}']={'path':dest.name,'sha256':digest(dest),
                    'approval':{'status':'pending','scope':'production'},
                    'semantic_review_required':['empty_scene','no_text_logo']}
            path.write_text(json.dumps(catalog,indent=2)+'\n')
        paths,manifest=compose_story(path,scenes,root/'scenes',test_fixtures=True,preview=True)
        identical={}
        for i,profile in enumerate(('character','truck')):
            a,b=(scene['layers'][i] for scene in manifest['scenes'])
            identical[profile]=a['transformed_rgba_sha256']==b['transformed_rgba_sha256']
        if not all(identical.values()):raise AssetError('test_sprite_identity_changed')
        report.update(status='passed_preview_only',mechanical_asset_reuse_verified=identical,
            output_frames=[str(path.relative_to(root)) for path in paths],
            quality_report='scenes/composition.json',
            production_blockers=['no_approved_story_character_assets','manual_background_and_scene_review_required'])
    except AssetError as error:
        report['reason']=str(error)  # Locally defined error identifiers only.
    except Exception:
        report['reason']='unexpected_demo_error_raw_details_withheld'
    finally:
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate-backgrounds',action='store_true');args=parser.parse_args()
    if not (os.environ.get('GITHUB_ACTIONS')=='true'
            and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and os.environ.get('GITHUB_REPOSITORY')=='akaradag88/minomasal-automation'
            and os.environ.get('GITHUB_REF')==BRANCH):
        raise SystemExit('Only the isolated manual PR #4 test may run this demo.')
    report=run_demo('asset_test_output/demo',generate_backgrounds=args.generate_backgrounds)
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='passed_preview_only' else 1


if __name__=='__main__':raise SystemExit(main())
