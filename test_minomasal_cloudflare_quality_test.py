"""Manual CF probe: no generation unless free plan AND current quota verified."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from PIL import Image
import yaml
import minomasal_cloudflare_quality_test as probe
from minomasal_images import CF_MODEL,ProviderFailure


class CloudflareQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dest=Path(self.tmp.name)/'output'
        self.env=patch.dict(os.environ,{'CLOUDFLARE_ACCOUNT_ID':'a'*32,'CLOUDFLARE_API_TOKEN':'TOP_SECRET','CLOUDFLARE_USAGE_TOKEN':'AUDIT_SECRET'},clear=True)
        self.env.start();self.addCleanup(self.env.stop)
    def response(self,data):return Mock(json=Mock(return_value=data))
    def model(self):return self.response({'success':True,'result':[{'name':CF_MODEL}]})
    def free(self):return self.response({'success':True,'result':[],'result_info':{'total_count':0}})
    def quota(self,used=0):return {'utc_day':'2026-11-11','used_neurons_reported':used,'remaining_neurons_reported':10000-used}

    def test_usage_token_is_required_and_cannot_reuse_inference_token(self):
        for token in ('','TOP_SECRET'):
            with self.subTest(token_present=bool(token)),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CLOUDFLARE_USAGE_TOKEN':token}),patch.object(probe,'http') as http:
                result=probe.run_check(Path(tmp)/'output',True)
                http.assert_not_called();self.assertEqual(result['status'],'blocked_no_publish')

    def test_model_and_audit_calls_use_different_tokens(self):
        with patch.object(probe,'http',side_effect=[self.model(),self.free()]) as http,patch.object(probe,'query_quota',return_value=self.quota()) as quota:
            result=probe.run_check(self.dest)
            self.assertEqual(http.call_args_list[0].kwargs['headers']['Authorization'],'Bearer TOP_SECRET')
            self.assertEqual(http.call_args_list[1].kwargs['headers']['Authorization'],'Bearer AUDIT_SECRET')
            self.assertEqual(quota.call_args.args[1],'AUDIT_SECRET')
            self.assertTrue(result['tokens_separated'])

    def test_inference_400_reports_safe_api_error_and_never_starts_scene_two(self):
        details=[{'code':10000,'message':'Authentication error','message_is_canonical':True,
                  'schema_fields_mentioned':[]}]
        with patch.object(probe,'http',side_effect=[self.model(),self.free()]),patch.object(probe,'query_quota',return_value=self.quota()),patch.object(probe.Cloudflare,'generate',side_effect=ProviderFailure('cloudflare','request_failed',400,api_errors=details)) as gen:
            result=probe.run_check(self.dest,True)
            gen.assert_called_once()
            self.assertEqual(result['api_errors'],details)
            self.assertEqual(result['scenes'],[])
            self.assertEqual(result['blocked_at'],'image_1')
            self.assertEqual(result['generation_parameters']['request_fields'],['prompt'])

    def test_missing_credentials_never_connects(self):
        with patch.dict(os.environ,{'CLOUDFLARE_API_TOKEN':''}),patch.object(probe,'http') as http:
            result=probe.run_check(self.dest,True)
            http.assert_not_called();self.assertFalse(result['connection_verified'])

    def test_unauthorized_stops_before_generation(self):
        with patch.object(probe,'http',side_effect=ProviderFailure('cloudflare','request_failed',403)),patch.object(probe.Cloudflare,'generate') as gen:
            result=probe.run_check(self.dest,True)
            self.assertEqual(result['http_status'],403);gen.assert_not_called()
            self.assertNotIn('TOP_SECRET',json.dumps(result))

    def test_billing_permission_required(self):
        with patch.object(probe,'http',side_effect=[self.model(),ProviderFailure('cloudflare','request_failed',403)]),patch.object(probe.Cloudflare,'generate') as gen:
            result=probe.run_check(self.dest,True)
            self.assertTrue(result['connection_verified']);self.assertEqual(result['blocked_at'],'free_plan')
            self.assertFalse(result['free_plan_verified']);gen.assert_not_called()
            self.assertEqual(result['next_action'],'check_subscription_read_access_or_dashboard_plan_verification')
            self.assertEqual(result['request_method'],'GET')
            self.assertEqual(result['endpoint_template'],'/accounts/{account_id}/subscriptions')
            self.assertEqual(result['documented_minimum_permission'],'Billing Read')
            self.assertNotIn('a'*32,json.dumps(result))

    def test_paid_plan_never_generates(self):
        paid=self.response({'success':True,'result':[{'price':5,'rate_plan':{'public_name':'Workers Paid'}}],'result_info':{'total_count':1}})
        with patch.object(probe,'http',side_effect=[self.model(),paid]),patch.object(probe.Cloudflare,'generate') as gen:
            result=probe.run_check(self.dest,True)
            self.assertEqual(result['reason'],'paid_or_unknown_subscription_blocked');gen.assert_not_called()

    def test_quota_unreadable_never_generates(self):
        with patch.object(probe,'http',side_effect=[self.model(),self.free()]),patch.object(probe,'query_quota',side_effect=ProviderFailure('cloudflare','quota_query_denied_or_unsupported')),patch.object(probe.Cloudflare,'generate') as gen:
            result=probe.run_check(self.dest,True)
            self.assertTrue(result['free_plan_verified']);self.assertFalse(result['quota_verified']);gen.assert_not_called()
            self.assertEqual(result['request_method'],'POST')
            self.assertEqual(result['endpoint_template'],'/graphql')

    def test_insufficient_quota_never_generates(self):
        with patch.object(probe,'http',side_effect=[self.model(),self.free()]),patch.object(probe,'query_quota',return_value=self.quota(9500)),patch.object(probe.Cloudflare,'generate') as gen:
            result=probe.run_check(self.dest,True)
            self.assertEqual(result['reason'],'insufficient_verified_free_quota');gen.assert_not_called()

    def test_check_only_is_default_and_generates_nothing(self):
        with patch.object(probe,'http',side_effect=[self.model(),self.free()]),patch.object(probe,'query_quota',return_value=self.quota()),patch.object(probe.Cloudflare,'generate') as gen:
            result=probe.run_check(self.dest)
            self.assertEqual(result['status'],'preflight_passed_generation_not_requested');gen.assert_not_called()

    def test_two_fixed_character_truck_scenes_and_sanitized_artifacts(self):
        data=io.BytesIO();Image.effect_noise((512,512),70).convert('RGB').save(data,format='PNG')
        with patch.object(probe,'http',side_effect=[self.model(),self.free()]),patch.object(probe,'query_quota',return_value=self.quota()),patch.object(probe.Cloudflare,'generate',return_value=data.getvalue()) as gen:
            result=probe.run_check(self.dest,True)
            self.assertEqual(gen.call_count,2)
            for call in gen.call_args_list:
                self.assertIn(probe.CHARACTER,call.args[0]);self.assertIn('toy truck',call.args[0])
            self.assertEqual(len(result['scenes']),2)
            self.assertEqual(len(list(self.dest.glob('*.original.png'))),2)
            text=(self.dest/'report.json').read_text()
            self.assertNotIn('TOP_SECRET',text);self.assertNotIn('AUDIT_SECRET',text);self.assertNotIn('a'*32,text)

    def test_quota_change_before_second_image_stops(self):
        data=io.BytesIO();Image.effect_noise((512,512),70).convert('RGB').save(data,format='PNG')
        with patch.object(probe,'http',side_effect=[self.model(),self.free()]),patch.object(probe,'query_quota',side_effect=[self.quota(),self.quota(),self.quota(9900)]),patch.object(probe.Cloudflare,'generate',return_value=data.getvalue()) as gen:
            result=probe.run_check(self.dest,True)
            gen.assert_called_once();self.assertEqual(result['reason'],'free_quota_changed')

    def test_unknown_exception_cannot_leak_token(self):
        with patch.object(probe,'http',side_effect=RuntimeError('TOP_SECRET')):
            result=probe.run_check(self.dest,True)
            self.assertNotIn('TOP_SECRET',json.dumps(result));self.assertEqual(result['status'],'blocked_no_publish')

    def test_graphql_uses_all_models_and_validates_numeric_usage(self):
        body={'data':{'viewer':{'accounts':[{'aiInferenceAdaptiveGroups':[{'sum':{'totalNeurons':150}}]}]}}}
        with patch.object(probe,'http',return_value=self.response(body)) as http:
            quota=probe.query_quota('a'*32,'TOP_SECRET')
            self.assertEqual(quota['remaining_neurons_reported'],9850)
            self.assertFalse(quota['authoritative_remaining_quota'])
            query=http.call_args.kwargs['json']['query'];self.assertNotIn('model',query)
        body['data']['viewer']['accounts'][0]['aiInferenceAdaptiveGroups'][0]['sum']['totalNeurons']=True
        with patch.object(probe,'http',return_value=self.response(body)):
            with self.assertRaises(ProviderFailure):probe.query_quota('a'*32,'TOP_SECRET')

    def test_graphql_errors_do_not_mean_zero_usage(self):
        with patch.object(probe,'http',return_value=self.response({'errors':[{'message':'TOP_SECRET'}]})):
            with self.assertRaises(ProviderFailure) as err:probe.query_quota('a'*32,'TOP_SECRET')
            self.assertNotIn('TOP_SECRET',str(err.exception))

    def test_probe_refuses_local_or_automatic_execution(self):
        with patch('sys.argv',['probe','--generate-two-scenes']),patch.object(probe,'run_check') as run:
            with self.assertRaises(SystemExit):probe.main()
            run.assert_not_called()

    def test_workflows_manual_only_and_artifact_allowlist(self):
        for filename in ('minomasal-cloudflare-quality-test.yml','minomasal-pollinations-account-check.yml'):
            workflow=yaml.load((Path('.github/workflows')/filename).read_text(),Loader=yaml.BaseLoader)
            self.assertEqual(set(workflow['on']),{'workflow_dispatch'})
            self.assertEqual(workflow['permissions'],{'contents':'read'})
            job=workflow['jobs']['cloudflare-quality-test']
            self.assertIn('workflow_dispatch',job['if']);self.assertIn(probe.BRANCH,job['if'])
            steps=job['steps'];offline=next(i for i,s in enumerate(steps) if s.get('run')=='python -m unittest -v test_minomasal_cloudflare_quality_test')
            live=next(i for i,s in enumerate(steps) if 'CLOUDFLARE_API_TOKEN' in s.get('env',{}))
            self.assertLess(offline,live)
            artifact=steps[-1]
            self.assertEqual(artifact['if'],'always()');self.assertEqual(artifact['with']['path'],'cloudflare_test_output/')
            self.assertEqual(artifact['with']['include-hidden-files'],'false')
