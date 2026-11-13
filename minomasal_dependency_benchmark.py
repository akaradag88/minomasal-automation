"""Manual PR-only, no-publish dependency benchmark. No model instantiation."""
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BRANCH='refs/heads/feat/adim-10-9-free-image-providers'
PHASES=(('system-force',465),('python',585),('verify',110))


def run_benchmark(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'python':sys.version.split()[0],
            'cache_hit':os.environ.get('DEPENDENCY_CACHE_HIT')=='true',
            'pip_install_limit_seconds':480,'phases':[],
            'status':'failed','generation_allowed':False,'publishing_allowed':False}
    try:
        for phase,limit in PHASES:
            started=time.monotonic()
            try:
                result=subprocess.run(['bash','scripts/install-minomasal-dependencies.sh',phase],
                                      check=False,timeout=limit)
                code=result.returncode
            except subprocess.TimeoutExpired:
                code=124
            elapsed=round(time.monotonic()-started,3)
            report['phases'].append({'phase':phase,'seconds':elapsed,'exit_code':code})
            if code!=0:
                report['blocked_at']=phase;report['reason']='phase_failed_or_timed_out'
                break
            if phase=='python':
                # Entire Python phase includes version commands and pip check:
                # under 480s is a conservative upper bound on pip install time.
                report['pip_under_eight_minutes']=elapsed<480
                if elapsed>=480:
                    report['blocked_at']=phase;report['reason']='python_phase_exceeded_eight_minutes'
                    break
        else:
            report['status']='passed'
        report['packages']={}
        for name in ('pip','edge-tts','Pillow','requests','numpy','google-genai',
                     'google-api-python-client','google-auth','google-auth-httplib2','faster-whisper'):
            try:report['packages'][name]=version(name)
            except PackageNotFoundError:report['packages'][name]=None
    except Exception:
        # Exception values can contain local environment or URL details.
        report['reason']='unexpected_benchmark_failure'
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    if not (os.environ.get('GITHUB_ACTIONS')=='true'
            and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
            and os.environ.get('GITHUB_REPOSITORY')=='akaradag88/minomasal-automation'
            and os.environ.get('GITHUB_REF')==BRANCH):
        raise SystemExit('Only the manual PR #4 no-publish test may run the benchmark.')
    report=run_benchmark('dependency_test_output')
    text=json.dumps(report,indent=2);print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
            summary.write('## Dependency benchmark — no generation or publishing\n\n```json\n'+text+'\n```\n')
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
