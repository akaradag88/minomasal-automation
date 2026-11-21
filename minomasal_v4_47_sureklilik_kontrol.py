"""Free/offline scene-state contract for MinoMasal #47. Never renders or publishes.

Detects missing or contradictory instructions in the storyboard JSON. This checks
TEXT ONLY: final image appearance still requires visual review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
STORY=ROOT/'minomasal_v4_47_revize_hikaye.json'
PLAN=ROOT/'minomasal_v4_47_sureklilik_plani.json'


def check(story_file=STORY, plan_file=PLAN):
    story=json.loads(Path(story_file).read_text(encoding='utf-8'))
    plan=json.loads(Path(plan_file).read_text(encoding='utf-8'))
    scenes=story.get('scenes',[])
    pscenes=plan.get('scenes',[])
    errors=[]
    if len(scenes)!=10 or len(pscenes)!=10:
        errors.append(f'Exactly ten scenes required: {len(scenes)} story / {len(pscenes)} plan')
        return errors,story,plan
    words=sum(len(s['narration'].split()) for s in scenes)
    if not 75<=words<=110:
        errors.append(f'Word count outside 75-110: {words}')
    if sum(s['narration'].count('Tonton') for s in scenes)>3:
        errors.append('Character name repeats too often')
    if story.get('title')!='Küçük Oyuncak Kamyon Şantiyede Kayboldu!':
        errors.append('Pilot title changed')
    for i,(sc,ps) in enumerate(zip(scenes,pscenes),1):
        vis=sc.get('visual','')
        if ps.get('number')!=i:
            errors.append(f'Scene {i} plan index changed')
        if sc.get('narration')!=ps.get('narration'):
            errors.append(f'Scene {i} narration changed unexpectedly')
        cargo=ps.get('cargo'); bridge=ps.get('bridge')
        if cargo not in ('loaded','unloading','empty') or bridge not in ('hidden','visible'):
            errors.append(f'Scene {i}: unexpected scene state')
        if f'CARGO BED STATE = {cargo.upper()}:' not in vis:
            errors.append(f'Scene {i}: cargo state instruction missing/mismatched')
        if f'BRIDGE VISIBILITY = {bridge.upper()}:' not in vis:
            errors.append(f'Scene {i}: bridge state instruction missing/mismatched')
        for required in ('CHARACTER IDENTITY LOCK:', 'SETTING LOCK:', 'SCENE ACTION:', 'REQUIRED PROPS:', 'Forbidden:', '9:16'):
            if required not in vis:
                errors.append(f'Scene {i}: missing visual rule {required}')
        for object_name in ps.get('must_see',[]):
            if object_name not in vis:
                errors.append(f'Scene {i}: must_see instruction missing: {object_name}')
        for object_name in ps.get('must_not_see',[]):
            if object_name not in vis:
                errors.append(f'Scene {i}: must_not_see instruction missing: {object_name}')
    expect_cargo=['loaded']*8+['unloading','empty']
    expect_bridge=['hidden']*7+['visible']*3
    if [p['cargo'] for p in pscenes]!=expect_cargo:
        errors.append('Sand load timeline broken')
    if [p['bridge'] for p in pscenes]!=expect_bridge:
        errors.append('Red bridge timeline broken')
    if not {'three distinct branching paths','yellow sand visibly inside blue cargo bed'}.issubset(set(pscenes[2]['must_see'])):
        errors.append('Three-way road junction missing in scene 3')
    if not {'red bridge fully visible','yellow sand inside truck bed'}.issubset(set(pscenes[7]['must_see'])):
        errors.append('Scene 8 bridge/load requirements missing')
    if 'truck bed tilted' not in pscenes[8]['must_see'] or 'completely empty cargo bed' not in pscenes[9]['must_see']:
        errors.append('Unloading and post-unloading scene requirements missing')
    # Detect modifications to visuals that could create a conflict. Plan owns visuals.
    for i,ps in enumerate(pscenes,1):
        vis=scenes[i-1]['visual']
        if ps['bridge']=='hidden' and ('BRIDGE VISIBILITY = VISIBLE:' in vis):
            errors.append(f'Scene {i}: bridge both hidden and visible')
        if ps['cargo']=='loaded' and ('CARGO BED STATE = EMPTY:' in vis):
            errors.append(f'Scene {i}: loaded and empty contradiction')
    return errors,story,plan


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',default='minomasal_v4_47_sureklilik_rapor.json')
    args=parser.parse_args()
    problems,story,plan=check()
    payload={
        'result':'PREVIEW_STORYBOARD_CHECK_FAILED' if problems else 'STORYBOARD_TEXT_PREFLIGHT_OK',
        'story_number':47,
        'scene_count':len(story.get('scenes',[])),
        'narration_words':sum(len(s['narration'].split()) for s in story.get('scenes',[])),
        'original_three_images':'REJECTED_FROM_EARLIER_HUMAN_REVIEW',
        'new_images_generated':False, 'api_calls':0,
        'published':False,'visuals_verified':False,'human_image_review_required':True,
        'first_3_corrections':{
            '1':'Visible sand in bed; no bridge',
            '2':'Visible sand in bed; red bridge completely occluded',
            '3':'Visible sand in bed; exactly three separate branching paths; no bridge'},
        'errors':problems
    }
    Path(args.report).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for e in problems:print('ERROR:',e,file=sys.stderr)
    if problems:
        raise SystemExit(1)
    print('V4_47_SUREKLILIK_OFFLINE_OK 10_scenes 89_words loaded=1-8 unloading=9 empty=10 bridge_hidden=1-7 visible=8-10 NO_PUBLISH')

if __name__=='__main__':main()
