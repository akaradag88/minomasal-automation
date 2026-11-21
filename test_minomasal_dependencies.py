"""Offline installer tests: fake APT/pip, real short deadline, no downloads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

import yaml
import minomasal_dependency_benchmark as benchmark

ROOT=Path(__file__).resolve().parent
SCRIPT=ROOT/'scripts/install-minomasal-dependencies.sh'


class DependencyInstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);self.bin=self.folder/'bin';self.bin.mkdir()
        self.trace=self.folder/'commands';self.calls=self.folder/'calls'
        self.env={**os.environ,'PATH':str(self.bin),'TRACE':str(self.trace),'CALLS':str(self.calls)}
        self.executable('timeout', '''#!/bin/bash
printf '%s\\n' "$*" >> "$TRACE"
shift 3
if [[ "${TEST_SHORT_TIMEOUT:-0}" == 1 ]]; then
  exec /usr/bin/timeout --kill-after=1s 0.15s "$@"
fi
exec "$@"
''')
        self.executable('python', '#!'+sys.executable+'\n'+'''
import json,os,sys,time
with open(os.environ['CALLS'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:4]==['-m','pip','install']:
 if os.environ.get('TEST_STALL_INSTALL')=='1':time.sleep(5)
 if os.environ.get('TEST_FAIL_INSTALL')=='1':sys.exit(9)
''')
        self.executable('sudo','#!/bin/sh\nif [ "$1" = -n ]; then shift; fi\nexec "$@"\n')
        (self.bin/'env').symlink_to('/usr/bin/env')
        self.executable('apt-get','#!'+sys.executable+'\n'+'''
import json,os,sys
with open(os.environ['CALLS'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
if os.environ.get('TEST_FAIL_APT')=='1':sys.exit(7)
''')

    def executable(self,name,content):
        path=self.bin/name;path.write_text(content);path.chmod(0o755)

    def run_phase(self,phase,**env):
        return subprocess.run(['/bin/bash',str(SCRIPT),phase],cwd=ROOT,
            env={**self.env,**env},capture_output=True,text=True,timeout=5)

    def recorded(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_successful_offline_install_is_fast_and_uses_one_resolver(self):
        started=time.monotonic();result=self.run_phase('python')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertLess(time.monotonic()-started,5)
        calls=self.recorded();installs=[c for c in calls if c[:3]==['-m','pip','install']]
        self.assertEqual(len(installs),1)
        args=installs[0]
        for option in ('--no-input','--prefer-binary','requirements-minomasal-daily.txt'):
            self.assertIn(option,args)
        self.assertEqual(args[args.index('--timeout')+1],'30')
        self.assertEqual(args[args.index('--retries')+1],'2')
        self.assertIn(['-m','pip','check'],calls)
        self.assertIn('--signal=TERM --kill-after=15s 8m python -m pip install',self.trace.read_text())

    def test_install_failure_stops_before_consistency_check(self):
        result=self.run_phase('python',TEST_FAIL_INSTALL='1')
        self.assertEqual(result.returncode,9)
        self.assertNotIn(['-m','pip','check'],self.recorded())

    def test_stalled_pip_is_killed_without_retry_or_later_commands(self):
        started=time.monotonic()
        result=self.run_phase('python',TEST_STALL_INSTALL='1',TEST_SHORT_TIMEOUT='1')
        self.assertEqual(result.returncode,124,result.stderr)
        self.assertLess(time.monotonic()-started,3)
        calls=self.recorded()
        self.assertEqual(sum(c[:3]==['-m','pip','install'] for c in calls),1)
        self.assertNotIn(['-m','pip','check'],calls)

    def test_apt_update_failure_does_not_continue_to_install(self):
        result=self.run_phase('system',TEST_FAIL_APT='1')
        self.assertEqual(result.returncode,7,result.stderr)
        self.assertEqual(len(self.recorded()),1)
        self.assertIn('update',self.recorded()[0])
        trace=self.trace.read_text()
        for option in ('Acquire::Retries=2','Acquire::http::Timeout=30','Acquire::https::Timeout=30','DPkg::Lock::Timeout=60'):
            self.assertIn(option,trace)

    def test_cache_keys_deadlines_and_publish_guards(self):
        workflow=yaml.load((ROOT/'.github/workflows/minomasal-daily-live.yml').read_text(),Loader=yaml.BaseLoader)
        job=workflow['jobs']['prepare-for-review'];steps=job['steps']
        self.assertEqual(job['timeout-minutes'],'90')
        setup=next(s for s in steps if s.get('uses','').startswith('actions/setup-python@'))
        self.assertEqual(setup['with']['cache'],'pip')
        self.assertEqual(setup['with']['cache-dependency-path'],'requirements-minomasal-engine.lock.txt')
        install=next(s for s in steps if '--require-hashes' in s.get('run',''))
        self.assertIn('8m python -m pip install',install['run'])
        self.assertEqual(install['timeout-minutes'],'10')
        first_generation=next(i for i,s in enumerate(steps) if 'minomasal_publish_engine.py' in s.get('run',''))
        self.assertLess(steps.index(install),first_generation)
        self.assertEqual(job['if'],"github.ref == 'refs/heads/main'")
        self.assertEqual(workflow['concurrency'],{'group':'minomasal-preview-state','cancel-in-progress':'false'})

    def test_existing_daily_dependency_set_is_preserved(self):
        lines=(ROOT/'requirements-minomasal-daily.txt').read_text().splitlines()
        packages=[line for line in lines if line and not line.startswith('#')]
        self.assertEqual(packages,['-r requirements-minomasal.txt','google-api-python-client',
            'google-auth','google-auth-httplib2','faster-whisper>=1.1,<2'])


class DependencyBenchmarkTests(unittest.TestCase):
    def test_success_records_real_phase_timings_without_generation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(benchmark.subprocess,'run',return_value=Mock(returncode=0)) as run,patch.object(benchmark.time,'monotonic',side_effect=[0,2,2,42,42,43]):
            report=benchmark.run_benchmark(Path(tmp)/'output')
            self.assertEqual(report['status'],'passed')
            self.assertEqual([p['seconds'] for p in report['phases']],[2,40,1])
            self.assertTrue(report['pip_under_eight_minutes'])
            self.assertFalse(report['generation_allowed']);self.assertFalse(report['publishing_allowed'])
            self.assertEqual([c.args[0][-1] for c in run.call_args_list],['system-force','python','verify'])

    def test_apt_failure_stops_benchmark_and_saves_report(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(benchmark.subprocess,'run',return_value=Mock(returncode=124)) as run:
            folder=Path(tmp)/'output';report=benchmark.run_benchmark(folder)
            run.assert_called_once();self.assertEqual(report['blocked_at'],'system-force')
            self.assertEqual(json.loads((folder/'report.json').read_text())['status'],'failed')

    def test_slow_python_phase_cannot_be_reported_as_under_budget(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(benchmark.subprocess,'run',return_value=Mock(returncode=0)) as run,patch.object(benchmark.time,'monotonic',side_effect=[0,1,1,482]):
            report=benchmark.run_benchmark(Path(tmp)/'output')
            self.assertFalse(report['pip_under_eight_minutes'])
            self.assertEqual(report['status'],'failed');self.assertEqual(run.call_count,2)

    def test_benchmark_cannot_run_outside_manual_pr_context(self):
        with patch.dict(os.environ,{},clear=True),patch.object(benchmark,'run_benchmark') as run:
            with self.assertRaises(SystemExit):benchmark.main()
            run.assert_not_called()

    def test_isolated_workflow_has_no_secrets_or_publish_steps(self):
        data=yaml.load((ROOT/'.github/workflows/minomasal-dependencies-test.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(set(data['on']),{'workflow_dispatch','workflow_call'})
        self.assertEqual(data['permissions'],{'contents':'read'})
        job=data['jobs']['dependencies'];self.assertIn(benchmark.BRANCH,job['if'])
        self.assertIn('workflow_dispatch',job['if'])
        for step in job['steps']:
            self.assertNotIn('secrets.',json.dumps(step))
            self.assertNotIn('minomasal_dual_publish.py',step.get('run',''))
        self.assertTrue(any(s.get('run')=='python run_readiness_tests.py' for s in job['steps']))
        bridge=yaml.load((ROOT/'.github/workflows/minomasal-pollinations-account-check.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertIn('!inputs.dependency_test',bridge['jobs']['account-check']['if'])
        self.assertIn('!inputs.dependency_test',bridge['jobs']['cloudflare-quality-test']['if'])
        self.assertNotIn('uses',bridge['jobs']['dependency-test'])
        self.assertEqual(bridge['jobs']['dependency-test']['steps'],job['steps'])
        self.assertIn('!inputs.asset_test',bridge['jobs']['cloudflare-quality-test']['if'])


if __name__=='__main__':unittest.main()
