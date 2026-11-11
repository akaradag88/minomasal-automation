"""Free image policy, adapters, whole-batch fallback and image integrity. No API."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import requests
import minomasal_images as images

STORY={'title':'Test','characters':'Mino: small orange fox, green eyes, blue overalls, red scarf.',
       'scenes':[{'narration':'Mino ormanda.', 'visual':f'Mino walks beside tree {i}.'} for i in range(6)]}


def picture():
    out=io.BytesIO();Image.effect_noise((512,512),70).convert('RGB').save(out,format='PNG');return out.getvalue()


def response(status=200,body=None,content=b'data',text=''):
    return Mock(status_code=status,content=content,text=text,json=Mock(return_value=body))


class ImageProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=picture()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'images'
        self.config=images.load_config();self.config['scene_count']=6
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();self.addCleanup(self.env.stop)

    def test_unapproved_quality_blocks_all_production_api_calls(self):
        with patch.object(images.requests,'request') as request:
            with self.assertRaisesRegex(images.ImageFailure,'automation_quality_not_approved'):
                images.make_images(STORY,self.folder,'secret','flux')
            request.assert_not_called()

    def test_unapproved_production_stops_before_voice_or_render(self):
        import asyncio
        import minomasal as mm
        root=Path(self.tmp.name)/'production'
        with patch.object(mm,'ROOT',root),patch.object(mm,'voices') as voice,patch.object(mm,'create_story') as story_api,patch.object(mm,'render') as render,patch.object(images.requests,'request') as request:
            with self.assertRaises(images.ImageFailure):
                asyncio.run(mm.produce(mm.KONULAR[46]))
            voice.assert_not_called();story_api.assert_not_called();render.assert_not_called();request.assert_not_called()
        self.assertFalse(list(root.rglob('tamam.json')))

    def test_positive_free_only_capped_pollinations_policy(self):
        self.config.update(pollinations_enabled=True,pollinations_max_pollen_per_request=0.01)
        with patch.object(images,'http',side_effect=[response(body={'valid':True,'pollenBudget':0.5}),response(body={'balance':0.5,'accountBalance':{'paid':0,'tier':1}})]):
            images.Pollinations(self.config,'secret','flux').preflight()

    def test_comfyui_completed_core_output(self):
        provider=images.ComfyUI(self.config);provider.url='http://127.0.0.1:8188';provider.model='model.safetensors'
        with patch.object(images.requests,'request',side_effect=[
            response(body={'prompt_id':'test-id'}),
            response(body={'test-id':{'status':{'completed':True},'outputs':{'7':{'images':[{'filename':'a.png','subfolder':'','type':'output'}]}}}}),
            response(content=self.data),
        ]) as request:
            self.assertEqual(provider.generate('fox',1),self.data)
            self.assertEqual(request.call_count,3)
            self.assertEqual(request.call_args.kwargs['params']['filename'],'a.png')

    def test_paid_pollinations_disabled_even_with_key(self):
        with patch.object(images.requests,'request') as request:
            with self.assertRaisesRegex(images.ProviderFailure,'disabled'):
                images.Pollinations(self.config,'secret','flux').preflight()
            request.assert_not_called()

    def test_pollinations_free_source_and_key_cap_required(self):
        self.config.update(pollinations_enabled=True,pollinations_max_pollen_per_request=0.01)
        for account,budget in [({'paid':1,'tier':20},1),({'paid':0,'tier':20},None),({'paid':0,'tier':0},1),({'paid':False,'tier':20},1)]:
            with patch.object(images,'http',side_effect=[response(body={'valid':True,'pollenBudget':budget}),response(body={'balance':1,'accountBalance':account})]) as request:
                with self.assertRaises(images.ProviderFailure):images.Pollinations(self.config,'secret','flux').preflight()
                self.assertEqual(request.call_count,2)

    def test_pollinations_budget_permission_failure_blocks_generation(self):
        self.config.update(pollinations_enabled=True,pollinations_max_pollen_per_request=0.01)
        with patch.object(images.requests,'request',side_effect=[response(body={'valid':True,'pollenBudget':1}),response(403)]) as request:
            with self.assertRaises(images.ProviderFailure):images.Pollinations(self.config,'secret','flux').preflight()
            self.assertEqual(request.call_count,2)
            self.assertTrue(all('/image/' not in c.args[1] for c in request.call_args_list))

    def test_documented_single_page_subscriptions_can_omit_optional_metadata(self):
        self.assertEqual(images.verify_cloudflare_free_plan({'success':True,'result':[]}), 'unbilled_account')
        with self.assertRaises(images.ProviderFailure):
            images.verify_cloudflare_free_plan({'success':True,'result':[], 'result_info':{'total_count':5}})

    def test_cloudflare_requires_separate_usage_token(self):
        with patch.dict(os.environ,{'CLOUDFLARE_ACCOUNT_ID':'a'*32,'CLOUDFLARE_API_TOKEN':'secret'}),patch.object(images.requests,'request') as request:
            with self.assertRaisesRegex(images.ProviderFailure,'usage_token_missing'):
                images.Cloudflare(self.config).preflight()
            request.assert_not_called()

    def test_cloudflare_flag_cannot_bypass_paid_or_unverifiable_plan(self):
        for data in ({'success':True,'result':None},
                     {'success':True,'result':[],'result_info':{'total_count':2}},
                     {'success':True,'result':[{'price':5,'rate_plan':{'public_name':'Workers Paid'}}],'result_info':{'total_count':1}}):
            with patch.dict(os.environ,{'CLOUDFLARE_ACCOUNT_ID':'a'*32,'CLOUDFLARE_API_TOKEN':'secret','MINOMASAL_CLOUDFLARE_FREE_PLAN_CONFIRMED':'true','CLOUDFLARE_USAGE_TOKEN':'audit-secret'}),patch.object(images,'http',return_value=response(body=data)):
                with self.assertRaises(images.ProviderFailure):images.Cloudflare(self.config).preflight()

    def test_cloudflare_documented_api_and_base64(self):
        provider=images.Cloudflare(self.config)
        with patch.dict(os.environ,{'CLOUDFLARE_ACCOUNT_ID':'a'*32,'CLOUDFLARE_API_TOKEN':'secret','CLOUDFLARE_USAGE_TOKEN':'audit-secret'}), patch.object(images,'http',return_value=response(body={'success':True,'result':[],'result_info':{'total_count':0}})),patch('minomasal_cloudflare_usage.query_quota',return_value={'remaining_neurons_reported':10000}):
            provider.preflight()
        with patch.object(images.requests,'request',return_value=response(body={'success':True,'result':{'image':base64.b64encode(self.data).decode()}})) as request:
            self.assertEqual(provider.generate('same character in a forest',1),self.data)
            args,kwargs=request.call_args
            self.assertEqual(args[0],'POST');self.assertIn(images.CF_MODEL,args[1])
            self.assertEqual(kwargs['json'],{'prompt':'same character in a forest','steps':4,'seed':1234})
            self.assertFalse(kwargs['allow_redirects']);self.assertNotIn('secret',args[1])

    def test_ovh_checks_live_free_catalog(self):
        provider=images.OVHcloud(self.config)
        for html,allowed in [('<h1>stable-diffusion-xl-base-v10</h1><div>Pricing</div><b>Free</b>',True),('<h1>stable-diffusion-xl-base-v10</h1><div>Pricing</div><b>Paid</b>',False),('<script>stable-diffusion-xl-base-v10 Pricing Free</script>',False),('<head>stable-diffusion-xl-base-v10</head>'+('menu '*1000)+'<h1>stable-diffusion-xl-base-v10</h1><div>Pricing Free</div>',True)]:
            with patch.object(images,'http',return_value=response(text=html)):
                if allowed:provider.preflight()
                else:
                    with self.assertRaises(images.ProviderFailure):provider.preflight()

    def test_ovh_never_sends_a_billing_credential(self):
        provider=images.OVHcloud(self.config,key='POLLINATIONS_SECRET');provider.last_request=None
        with patch.dict(os.environ,{'OVH_AI_ENDPOINTS_ACCESS_TOKEN':'OVH_SECRET'}),patch.object(images.requests,'request',return_value=response(content=self.data)) as request:
            self.assertEqual(provider.generate('fox',1),self.data)
            self.assertNotIn('Authorization',request.call_args.kwargs['headers'])
            self.assertNotIn('OVH_SECRET',str(request.call_args))

    def test_402_and_403_stop_without_retry_or_secret_in_error(self):
        for status in (402,403):
            with patch.object(images.requests,'request',return_value=response(status)) as request,patch.object(images.time,'sleep') as sleep:
                with self.assertRaises(images.ProviderFailure) as err:images.http('ovhcloud','POST',images.OVH_URL,headers={'Authorization':'TOP_SECRET'})
                request.assert_called_once();sleep.assert_not_called()
                self.assertNotIn('TOP_SECRET',str(err.exception))

    def test_429_500_retry_bounded(self):
        for status in (429,500,502,503,504):
            with patch.object(images.requests,'request',return_value=response(status)) as request,patch.object(images.time,'sleep') as sleep:
                with self.assertRaises(images.ProviderFailure):images.http('ovhcloud','POST',images.OVH_URL)
                self.assertEqual(request.call_count,3);self.assertEqual([c.args[0] for c in sleep.call_args_list],[3,6])

    def test_connection_errors_and_redirects_sanitized(self):
        with patch.object(images.requests,'request',side_effect=requests.ConnectionError('TOP_SECRET')):
            with self.assertRaises(images.ProviderFailure) as err:images.http('cloudflare','POST','https://api.cloudflare.com')
            self.assertNotIn('TOP_SECRET',str(err.exception))
        with patch.object(images.requests,'request',return_value=response(302)) as request:
            with self.assertRaises(images.ProviderFailure):images.http('cloudflare','POST','https://api.cloudflare.com')
            self.assertFalse(request.call_args.kwargs['allow_redirects']);request.assert_called_once()

    def test_normalization_rejects_blank_tiny_and_corrupt(self):
        for data in [b'broken',b'',self._solid((2,2)),self._solid((512,512))]:
            with self.assertRaises(images.ImageFailure):images.normalize(data,Path(self.tmp.name)/'out.jpg')

    def _solid(self,size):
        out=io.BytesIO();Image.new('RGB',size,'white').save(out,format='PNG');return out.getvalue()

    def fake(self,name,fail_at=None):
        test=self
        class Fake(images.Provider):
            calls=[]
            def preflight(self):self.model='test-'+name
            def generate(self,prompt,index):
                self.calls.append((prompt,index))
                if index==fail_at:raise images.ProviderFailure(name,'request_failed',403)
                return test.data
        Fake.name=name
        return Fake

    def test_fallback_restarts_entire_story_and_preserves_partial_attempt(self):
        first=self.fake('cloudflare',2);second=self.fake('ovhcloud')
        with patch.object(images,'load_config',return_value={**self.config,'order':['cloudflare','ovhcloud'],'approved_for_automation':['cloudflare','ovhcloud']}), patch.dict(os.environ,{'MINOMASAL_IMAGE_PROVIDERS':'cloudflare,ovhcloud'}),patch.dict(images.PROVIDERS,{'cloudflare':first,'ovhcloud':second}):
            paths=images.make_images(STORY,self.folder,'secret','flux')
        self.assertEqual(len(first.calls),2);self.assertEqual(len(second.calls),6)
        manifest=json.loads((self.folder/'images.json').read_text())
        self.assertEqual(manifest['provider'],'ovhcloud');self.assertEqual(len(paths),6)
        self.assertEqual(len(list((self.folder/'attempts').glob('cloudflare-*/*.jpg'))),1)
        for path in paths:
            with Image.open(path) as image:self.assertEqual(image.size,(1080,1920))
        for prompt,index in second.calls:self.assertIn(STORY['characters'],prompt)

    def test_cache_and_modified_images(self):
        fake=self.fake('ovhcloud')
        with patch.object(images,'load_config',return_value={**self.config,'order':['ovhcloud'],'approved_for_automation':['ovhcloud']}), patch.dict(os.environ,{'MINOMASAL_IMAGE_PROVIDERS':'ovhcloud'}),patch.dict(images.PROVIDERS,{'ovhcloud':fake}):
            paths=images.make_images(STORY,self.folder,'secret','flux')
            images.make_images(STORY,self.folder,'secret','flux')
            self.assertEqual(len(fake.calls),6)
            paths[0].write_bytes(b'changed')
            with self.assertRaises(images.ImageFailure):images.make_images(STORY,self.folder,'secret','flux')
            self.assertEqual(len(fake.calls),6)

    def test_all_candidates_fail_no_complete_manifest(self):
        fake=self.fake('ovhcloud',2)
        with patch.object(images,'load_config',return_value={**self.config,'order':['ovhcloud'],'approved_for_automation':['ovhcloud']}), patch.dict(os.environ,{'MINOMASAL_IMAGE_PROVIDERS':'ovhcloud'}),patch.dict(images.PROVIDERS,{'ovhcloud':fake}):
            with self.assertRaises(images.ImageFailure):images.make_images(STORY,self.folder,'secret','flux')
        self.assertFalse((self.folder/'images.json').exists());self.assertFalse(list(self.folder.glob('*.jpg')))

    def test_local_count_mismatch_and_no_network(self):
        source=Path(self.tmp.name)/'local';source.mkdir();(source/'01.png').write_bytes(self.data)
        with patch.object(images.requests,'request') as request:
            with self.assertRaises(images.ImageFailure):images.make_images(STORY,self.folder,'secret','flux',str(source))
            request.assert_not_called()

    def test_provider_configuration_invalid_and_identity_secret_free(self):
        with patch.dict(os.environ,{'MINOMASAL_IMAGE_PROVIDERS':'https://paid.invalid'}):
            with self.assertRaises(images.ImageFailure):images.load_config()
        with patch.dict(os.environ,{'POLLINATIONS_API_KEY':'TOP_SECRET','CLOUDFLARE_API_TOKEN':'TOP_SECRET'}):
            self.assertNotIn('TOP_SECRET',json.dumps(images.identity()))

    def test_comfyui_rejects_cloud_or_partner_endpoints(self):
        for url in ('https://cloud.comfy.org','http://user:secret@localhost:8188','http://localhost:8188/paid'):
            with patch.dict(os.environ,{'COMFYUI_URL':url}),patch.object(images.requests,'request') as request:
                with self.assertRaises(images.ProviderFailure):images.ComfyUI(self.config).preflight()
                request.assert_not_called()

    def test_comfyui_core_nodes_only_and_portrait_workflow(self):
        provider=images.ComfyUI(self.config);provider.model='sd_xl_base_1.0.safetensors'
        workflow=provider.workflow('same character')
        self.assertEqual({n['class_type'] for n in workflow.values()},{'CheckpointLoaderSimple','CLIPTextEncode','EmptyLatentImage','KSampler','VAEDecode','SaveImage'})
        self.assertEqual(workflow['4']['inputs'],{'width':768,'height':1344,'batch_size':1})
        self.assertEqual(workflow['5']['inputs']['seed'],1234)

    def test_comfyui_submission_ambiguous_does_not_retry(self):
        provider=images.ComfyUI(self.config);provider.url='http://127.0.0.1:8188';provider.model='model.safetensors'
        with patch.object(images.requests,'request',return_value=response(500)) as request:
            with self.assertRaises(images.ProviderFailure):provider.generate('fox',1)
            request.assert_called_once()


if __name__=='__main__':unittest.main()
