"""Static runtime migration checks. No Actions execution or media generation."""
from pathlib import Path
import unittest
import yaml

CHECKOUT = 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1'
PYTHON = 'actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0'


class RuntimeConfigurationTests(unittest.TestCase):
    def test_workflows_use_supported_explicit_ubuntu_and_node24_actions(self):
        for path in Path('.github/workflows').glob('*.yml'):
            with self.subTest(path=path):
                workflow=yaml.load(path.read_text(), Loader=yaml.BaseLoader)
                for job in workflow['jobs'].values():
                    if 'runs-on' in job: self.assertEqual(job['runs-on'],'ubuntu-24.04')
                    for step in job.get('steps',[]):
                        action=step.get('uses','')
                        if action.startswith('actions/checkout@'): self.assertEqual(action,CHECKOUT)
                        if action.startswith('actions/setup-python@'):
                            self.assertEqual(action,PYTHON)
                            self.assertEqual(step['with']['python-version'],'3.11')

    def test_live_guards_and_existing_platform_settings(self):
        workflow=yaml.load(Path('.github/workflows/minomasal-daily-live.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow['on']),{'workflow_dispatch'})
        self.assertEqual(workflow['concurrency'],{'group':'minomasal-preview-state','cancel-in-progress':'false'})
        job=workflow['jobs']['produce-and-publish']
        self.assertEqual(job['if'],"github.ref == 'refs/heads/main'")
        stage=next(s for s in job['steps'] if s.get('id')=='stage')
        self.assertEqual(stage['if'],"steps.daycheck.outputs.eligible == 'true'")
        self.assertEqual(stage['env']['MINOMASAL_YOUTUBE_UPLOAD'],'false')
        publish=next(s for s in job['steps'] if s.get('name')=='Publish same video to YouTube and Instagram')
        self.assertEqual(publish['if'],"steps.daylock.outputs.acquired == 'true'")
        self.assertEqual(publish['env']['MINOMASAL_ENFORCE_DAILY_LOCK'],'true')
        self.assertEqual(publish['env']['MINOMASAL_YOUTUBE_PRIVACY'],'public')
        self.assertIn('minomasal_dual_publish.py',publish['run'])


if __name__ == '__main__': unittest.main()
