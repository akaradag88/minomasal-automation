"""Recovery boundaries: no API calls, rendering, lock writes or uploads."""
import json
from pathlib import Path
import unittest
import yaml
import minomasal_daily_live as daily

class RecoveryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.flow=yaml.load(Path('.github/workflows/minomasal-daily-live.yml').read_text(),Loader=yaml.BaseLoader)
        self.steps=self.flow['jobs']['produce-and-publish']['steps']
    def test_no_generation_or_publication_before_quality_and_human_approval(self):
        guarded=('minomasal_v4_gunluk_stage.py','minomasal_gunluk_kilit.py acquire','minomasal_gunluk_kilit.py verify','minomasal_dual_publish.py','minomasal_gunluk_kilit.py finish')
        for command in guarded:
            step=next(s for s in self.steps if command in s.get('run',''))
            self.assertEqual(step['if'],'${{ false }}',command)
        pub=next(s for s in self.steps if 'minomasal_dual_publish.py' in s.get('run',''))
        self.assertEqual(pub['env']['PUBLISH_ENABLED'],'false')
    def test_installs_are_cached_bounded_and_manifest_keeps_existing_packages(self):
        setup=next(s for s in self.steps if s.get('uses','').startswith('actions/setup-python@'))
        self.assertEqual(setup['with']['cache'],'pip')
        self.assertIn('requirements-minomasal-daily.txt',setup['with']['cache-dependency-path'])
        script=Path('scripts/install-minomasal-dependencies.sh').read_text()
        for requirement in ('8m python -m pip install','--timeout 30 --retries 2','--kill-after=15s','python -m pip check','Acquire::Retries=2'):
            self.assertIn(requirement,script)
        self.assertLessEqual(int(self.flow['jobs']['produce-and-publish']['timeout-minutes']),90)
    def test_legacy_youtube_path_cannot_bypass_review(self):
        legacy=yaml.load(Path('.github/workflows/minomasal-youtube-public-gunluk.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(legacy['jobs']['public-upload']['if'],'${{ false }}')
    def test_draft_cannot_claim_published_or_reserve_47(self):
        draft=json.loads(Path('docs/recovery/story-47-draft.json').read_text())
        ledger=json.loads(Path(daily.LEDGER).read_text())
        self.assertEqual(draft['number'],daily.choose(ledger))
        self.assertFalse(draft['publication_approved'])
        self.assertEqual(draft['status'],'draft_not_production_input')
        count=len(' '.join(draft['narrations']).split())
        self.assertTrue(75<=count<=110,count)
        self.assertEqual(len(draft['narrations']),10)
        for number in ('45','46'): self.assertEqual(ledger['stories'][number]['status'],'skipped')
