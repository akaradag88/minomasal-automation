import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import minomasal_tonton_asset_trial as trial
import minomasal_cloudflare_quality_test as probe
from minomasal_visual_profile import build_prompt

class TontonTrialTests(unittest.TestCase):
    def test_prompts_are_tonton_only_and_prompt_schema_stays_bounded(self):
        plan=json.loads(Path('minomasal_tonton_asset_plan.json').read_text())
        self.assertEqual(len(plan['scenes']),2)
        for scene in plan['scenes']:
            prompt=build_prompt(plan['profile'],scene)
            self.assertLessEqual(len(prompt),2048)
            self.assertNotIn('fox',prompt)
            self.assertEqual(scene['inventory'],{'tonton':1})
            self.assertIn('magenta',prompt)
    def test_wrapper_never_claims_reference_editing_or_approval(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(trial,'run_check',return_value={'status':'blocked_no_publish','scenes':[]}) as check:
            report=trial.trial(Path(tmp),True)
            self.assertFalse(report['reference_image_sent'])
            self.assertFalse(report['production_approved'])
            self.assertFalse(report['matches_existing_reference_verified'])
            self.assertIn('plan',check.call_args.kwargs)
    def test_probe_rejects_invalid_custom_plan_before_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(probe,'http') as http:
            report=probe.run_check(Path(tmp)/'out',True,plan={'scenes':[]})
            http.assert_not_called();self.assertEqual(report['status'],'blocked_no_publish')
    def test_trial_cannot_run_outside_manual_pr(self):
        with patch.dict('os.environ',{},clear=True),patch.object(trial,'trial') as call,patch('sys.argv',['trial']):
            with self.assertRaises(SystemExit):trial.main()
            call.assert_not_called()
