"""Preparation engine only. Never publishes or reserves a daily slot.

All structural/image approval checks happen before TTS and rendering. Existing
voice, renderer, music and channel settings are retained. No picture fallback.
"""
import argparse
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from minomasal_story_sources import select_story,StoryBlocked
from minomasal_asset_compositor import compose_story,validate_local_handoff,AssetError
from minomasal_engine_qa import check,QualityBlocked

ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def prepare(output,*,root=ROOT,render=False):
    root=Path(root);output=Path(output)
    if output.exists():raise RuntimeError('engine_output_exists_no_overwrite')
    output.mkdir(parents=True)
    report={'schema_version':1,'status':'blocked','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'technical_checks_passed':False,'publication_approved':False,'human_video_approval_required':True,
        'new_image_api_requests':0,'new_speech_requests':0,'ledger_written':False,'daily_slot_reserved':False,'blockers':[]}
    ledger_path=root/'minomasal_platform_durumu.json';before=sha(ledger_path)
    try:
        if any(os.environ.get(k,'false').lower()=='true' for k in ('PUBLISH_ENABLED','MINOMASAL_YOUTUBE_UPLOAD')):
            raise StoryBlocked('preparation_cannot_enable_upload')
        ledger=json.loads(ledger_path.read_text())
        number,topic,story,evidence=select_story(ledger,root)
        report.update(number=number,topic=topic,story=evidence,ledger_sha256=before)
        write(output/'story.json',story)
        catalog=root/'visual_assets/catalog.json';scenes=root/f'visual_assets/story-plans/{number}.json'
        if not scenes.is_file():report['blockers'].append('approved_scene_plan_missing')
        data=json.loads(catalog.read_text())
        if not data.get('assets'):report['blockers'].append('approved_character_assets_missing')
        if not data.get('backgrounds'):report['blockers'].append('approved_scene_backgrounds_missing')
        if os.environ.get('MINOMASAL_GEMINI_FREE_TIER_CONFIRMED')!='true':
            report['blockers'].append('gemini_free_account_not_attested')
        if report['blockers']:return report
        # Compose in a separate temporary directory; a failed review must not
        # leave a staging folder that an older publisher could pick up.
        plans=json.loads(scenes.read_text())
        if len(plans)!=10:raise AssetError('ten_scene_plans_required')
        if number==47:
            for index,scene in enumerate(plans,1):
                inventory=scene.get('inventory',{})
                if inventory.get('tonton')!=1:raise AssetError('canonical_tonton_inventory_required')
                if inventory.get('red_bridge',0)!=(1 if index>=8 else 0):raise AssetError('bridge_visibility_timeline_invalid')
                layer=next((x for x in scene.get('layers',[]) if x.get('profile')=='tonton'),{})
                asset=data.get('assets',{}).get(layer.get('asset'),{})
                expected='loaded' if index<=8 else 'unloading' if index==9 else 'empty'
                if asset.get('cargo_state')!=expected:raise AssetError('approved_cargo_state_asset_required')
            reference=data.get('profiles',{}).get('tonton',{}).get('reference',{})
            if reference.get('sha256')!=sha(root/'tonton_referans.png'):raise AssetError('canonical_tonton_reference_required')
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);frames,manifest=compose_story(catalog,plans,temp/'frames')
            # Scene review is a separate hash-bound human record, never inferred
            # from the fact that the underlying sprites were approved.
            review=root/f'visual_assets/story-plans/{number}.review.json'
            if not review.is_file():raise AssetError('manual_scene_review_missing')
            manifest['manual_scene_review']=json.loads(review.read_text())
            if (manifest['manual_scene_review'].get('story_number')!=number
                    or manifest['manual_scene_review'].get('narration_sha256')!=evidence['narration_sha256']):
                raise AssetError('scene_review_story_binding_missing_or_changed')
            write(temp/'frames/composition.json',manifest)
            validate_local_handoff(temp/'frames')
            if not render:
                report['status']='assets_verified_render_not_requested';return report
            import minomasal as mm
            from minomasal_sami_hizalama_v2 import aligned_scene_voices
            from minomasal_yayin_guvenligi import write_receipt,copy_receipt
            work=temp/'render';work.mkdir()
            write(work/'hikaye.json',story)
            # Copy the complete validated composition unchanged for provenance.
            shutil.copytree(temp/'frames',work/'gorseller')
            images=[work/'gorseller'/f'{i:02}.jpg' for i in range(1,11)]
            report['new_speech_requests']=1
            audios=asyncio.run(aligned_scene_voices(story,work))
            video=mm.render(story,images,audios,work)
            media=check(video,work/'altyazi.srt')
            if sha(ledger_path)!=before:raise StoryBlocked('ledger_changed_during_preparation')
            write_receipt(video,story,images,audios)
            receipt=video.with_suffix('.production.json')
            provenance=json.loads(receipt.read_text())
            provenance['assets'].append({'path':'gorseller/composition.json','sha256':sha(work/'gorseller/composition.json')})
            write(receipt,provenance)
            stage=output/'staging';stage.mkdir()
            shutil.copy2(video,stage/'masal_short.mp4');copy_receipt(video,stage/'masal_short.mp4')
            shutil.copy2(work/'altyazi.srt',stage/'altyazi.srt')
            shutil.copytree(work/'gorseller',stage/'reviewed_frames')
            write(stage/'metadata.json',{'number':number,'topic':topic,'title':story['title']+' | MinoMasal',
                'narration_sha256':evidence['narration_sha256'],'video':'masal_short.mp4','mode':'reviewed_local_composition'})
            report.update(status='video_ready_human_approval_required',technical_checks_passed=True,
                          video_sha256=sha(stage/'masal_short.mp4'),media=media)
            write(stage/'quality-report.json',report)
    except (StoryBlocked,AssetError,QualityBlocked) as error:
        report['blockers'].append(str(error))  # Fixed local diagnostic codes only.
    except Exception:
        report['blockers'].append('unexpected_preparation_error_raw_details_withheld')
    finally:
        if sha(ledger_path)!=before:report.update(status='blocked',technical_checks_passed=False,blockers=report['blockers']+['ledger_changed'])
        write(output/'report.json',report)
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='engine_output');parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    report=prepare(args.output,render=args.render)
    print(json.dumps({k:report[k] for k in ('status','technical_checks_passed','publication_approved','blockers')}))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as stream:stream.write('## MinoMasal preparation — NOT PUBLISHED\n\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return 0 if report['technical_checks_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
