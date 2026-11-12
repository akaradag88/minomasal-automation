import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml
import minomasal_asset_demo as demo
import minomasal_cloudflare_quality_test as probe


class AssetDemoTests(unittest.TestCase):
    def test_offline_demo_reuses_geometry_and_never_calls_image_api(self):
        with tempfile.TemporaryDirectory() as tmp,patch('minomasal_asset_compositor.scan_text',return_value={'status':'test_stub','detections':[]}),patch.object(probe,'run_check') as api:
            root=Path(tmp)/'demo';report=demo.run_demo(root)
            self.assertEqual(report['status'],'passed_preview_only');api.assert_not_called()
            self.assertTrue(all(report['mechanical_asset_reuse_verified'].values()))
            self.assertFalse(report['real_story_character_approved']);self.assertEqual(report['new_inference_requests'],0)
            self.assertTrue((root/'scenes/01.jpg').exists());self.assertTrue((root/'scenes/02.jpg').exists())

    def test_blocked_free_gate_never_composes_as_if_new_backgrounds_existed(self):
        with tempfile.TemporaryDirectory() as tmp,patch('minomasal_asset_compositor.scan_text',return_value={'status':'test_stub','detections':[]}),patch.object(probe,'run_check',return_value={'status':'blocked_no_publish','scenes':[],'blocked_at':'quota'}) as api:
            root=Path(tmp)/'demo';report=demo.run_demo(root,generate_backgrounds=True)
            self.assertEqual(report['status'],'blocked');self.assertEqual(report['new_inference_requests'],0)
            self.assertFalse((root/'scenes').exists());self.assertTrue((root/'report.json').exists())
            self.assertTrue(api.call_args.kwargs['backgrounds_only'])

    def test_demo_cannot_run_outside_manual_pr(self):
        with patch.dict(os.environ,{},clear=True),patch.object(demo,'run_demo') as run,patch('sys.argv',['demo']):
            with self.assertRaises(SystemExit):demo.main()
            run.assert_not_called()

    def test_workflows_use_direct_jobs_and_secrets_only_in_explicit_background_step(self):
        bridge=yaml.load(Path('.github/workflows/minomasal-pollinations-account-check.yml').read_text(),Loader=yaml.BaseLoader)
        dedicated=yaml.load(Path('.github/workflows/minomasal-assets-test.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(set(dedicated['on']),{'workflow_dispatch'})
        self.assertEqual(dedicated['permissions'],{'contents':'read'})
        bridge_steps=bridge['jobs']['asset-test']['steps']
        audit=next(step for step in bridge_steps if step.get('run')=='python minomasal_recovery_audit.py')
        self.assertEqual(audit['if'],'${{ inputs.rescue_audit }}')
        normalized=[]
        for step in bridge_steps:
            if step is audit: continue
            step=dict(step)
            if 'if' in step: step['if']=step['if'].replace(' && !inputs.rescue_audit','')
            normalized.append(step)
        self.assertEqual(normalized,dedicated['jobs']['asset-test']['steps'])
        self.assertFalse(any('uses' in job for job in bridge['jobs'].values()))
        steps=dedicated['jobs']['asset-test']['steps']
        offline=next(i for i,s in enumerate(steps) if s.get('run')=='python run_readiness_tests.py')
        for i,step in enumerate(steps):
            if 'secrets.' in json.dumps(step):
                self.assertEqual(step['if'],'${{ inputs.generate_images }}')
                self.assertGreater(i,offline);self.assertIn('--generate-backgrounds',step['run'])
            self.assertNotIn('minomasal_dual_publish.py',step.get('run',''))


if __name__=='__main__':unittest.main()
