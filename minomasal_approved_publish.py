"""Validate a reviewed exact artifact; publish only from an explicit manual run.

No generation. The existing ledger/daily lock modules remain authoritative.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import requests
from minomasal_engine_qa import check
from minomasal_yayin_guvenligi import validate_receipt
from minomasal_platform_gate import verify as verify_platforms

REPO='akaradag88/minomasal-automation'

class ApprovalBlocked(RuntimeError):pass

def source_run(run_id,*,transport=requests.get):
    if not re.fullmatch('[0-9]+',str(run_id)):raise ApprovalBlocked('invalid_source_run_id')
    def get(path):
        try:
            r=transport('https://api.github.com/repos/'+REPO+path,
                headers={'Authorization':'Bearer '+os.environ.get('GH_TOKEN',''),'Accept':'application/vnd.github+json'},timeout=30)
            if r.status_code!=200:raise ValueError()
            return r.json()
        except Exception:raise ApprovalBlocked('source_run_api_unverified') from None
    run=get('/actions/runs/'+str(run_id))
    if not (run.get('status')=='completed' and run.get('conclusion')=='success' and run.get('head_branch')=='main'
            and run.get('path')=='.github/workflows/minomasal-daily-live.yml'
            and run.get('event') in ('schedule','workflow_dispatch') and re.fullmatch('[0-9a-f]{40}',run.get('head_sha',''))):
        raise ApprovalBlocked('only_successful_main_preparation_is_publishable')
    comparison=get('/compare/'+run['head_sha']+'...main')
    if comparison.get('status') not in ('identical','ahead'):raise ApprovalBlocked('preparation_commit_not_on_main')
    return run

def validate(stage,number,approved_sha):
    stage=Path(stage)
    if not re.fullmatch('[0-9a-f]{64}',approved_sha):raise ApprovalBlocked('exact_video_hash_approval_required')
    video=stage/'masal_short.mp4'
    if not video.is_file() or hashlib.sha256(video.read_bytes()).hexdigest()!=approved_sha:
        raise ApprovalBlocked('approved_video_hash_mismatch')
    metadata=json.loads((stage/'metadata.json').read_text())
    report=json.loads((stage/'quality-report.json').read_text())
    if metadata.get('number')!=number or report.get('number')!=number or report.get('technical_checks_passed') is not True or report.get('video_sha256')!=approved_sha:
        raise ApprovalBlocked('quality_report_and_identity_required')
    validate_receipt(video)
    receipt=json.loads(video.with_suffix('.production.json').read_text())
    original=json.loads((stage/receipt['assets'][0]['path']).read_text())
    from minomasal_story_sources import fingerprint
    if fingerprint(original)!=metadata.get('narration_sha256'):raise ApprovalBlocked('story_fingerprint_mismatch')
    if number==47 and original!=json.loads(Path('minomasal_v4_47_revize_hikaye.json').read_text()):
        raise ApprovalBlocked('canonical_47_story_required')
    check(video,stage/'altyazi.srt')
    return metadata

def reserve(number,approved_sha,resume=False,metadata_path="staging/metadata.json"):
    import minomasal_gunluk_kilit as lock
    day=lock.today();old,old_sha=lock.get_file(lock.path_for(day))
    if resume:
        if old is None or old.get('status')!='reserved' or old.get('story_number')!=number or old.get('video_sha256')!=approved_sha:
            raise ApprovalBlocked('resume_requires_same_day_reserved_exact_video')
        remote,_=lock.get_file('minomasal_platform_durumu.json')
        row=remote['stories'].get(str(number),{})
        statuses=[row.get(p,{}).get('status') for p in ('youtube','instagram')]
        if statuses.count('published')!=1 or statuses.count('pending')!=1:
            raise ApprovalBlocked('ambiguous_or_complete_publication_requires_reconciliation_not_retry')
        # Explicit manual resume only; retain all old lock fields and prior owner.
        old['resumed_from']={'run_id':old['run_id'],'run_attempt':old['run_attempt']}
        old.update(run_id=os.environ['GITHUB_RUN_ID'],run_attempt=os.environ['GITHUB_RUN_ATTEMPT'])
        code,_=lock._write(lock.path_for(day),old,'Explicitly resume same reviewed MinoMasal video',sha=old_sha)
        if code!=200:raise ApprovalBlocked('resume_lock_compare_and_swap_failed')
    else:
        if old is not None:raise ApprovalBlocked('daily_slot_already_reserved_or_finished')
        if not lock.acquire(number,metadata_path):raise ApprovalBlocked('daily_slot_not_acquired')
        current,current_sha=lock.get_file(lock.path_for(day))
        lock.verify(number,day)
        current['video_sha256']=approved_sha
        code,_=lock._write(lock.path_for(day),current,'Bind reviewed video hash to daily reservation',sha=current_sha)
        if code!=200:raise ApprovalBlocked('daily_hash_binding_failed')
    lock.verify(number,day)
    return day

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',default='prepared/staging');parser.add_argument('--number',type=int,required=True)
    parser.add_argument('--source-run',required=True);parser.add_argument('--approved-sha256',required=True)
    parser.add_argument('--publish',action='store_true');parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    # Verification is read-only; no reservation or ledger modification happens
    # until both specific-file approval and live platform checks succeed.
    source_run(args.source_run)
    meta=validate(args.stage,args.number,args.approved_sha256)
    if not args.publish:
        print('Exact artifact validation passed. NO PUBLICATION, NO RESERVATION.');return
    if not (os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and os.environ.get('GITHUB_REF')=='refs/heads/main'
            and os.environ.get('PUBLISH_ENABLED')=='true'):
        raise ApprovalBlocked('explicit_manual_main_publication_required')
    from minomasal_daily_live import choose
    ledger=json.loads(Path('minomasal_platform_durumu.json').read_text())
    row=ledger['stories'].get(str(args.number))
    if row is None and choose(ledger)!=args.number:raise ApprovalBlocked('ledger_sequence_changed')
    verify_platforms(ledger,args.number,meta['topic'],meta['title'])
    day=reserve(args.number,args.approved_sha256,args.resume,str(Path(args.stage)/"metadata.json"))
    os.environ.update(MINOMASAL_APPROVED_VIDEO_SHA256=args.approved_sha256,MINOMASAL_ENFORCE_DAILY_LOCK='true',MINOMASAL_LOCK_DAY=day)
    import minomasal_dual_publish
    old=sys.argv
    try:
        sys.argv=['publisher','--stage',args.stage,'--number',str(args.number)]
        minomasal_dual_publish.main()
    finally:sys.argv=old
    import minomasal_gunluk_kilit as lock
    lock.finish(args.number,day)

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Approved publication stopped safely; reconcile persisted state before any retry. No raw errors logged.') from None
