import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import requests
import yaml
import minomasal_story_sources as stories
import minomasal_publish_engine as engine
import minomasal_engine_qa as qa
import minomasal_approved_publish as approval
import minomasal_platform_gate as platforms
import minomasal_dual_publish as publisher

CANON=json.loads(Path('minomasal_v4_47_revize_hikaye.json').read_text())
LEDGER=json.loads(Path('minomasal_platform_durumu.json').read_text())

class StorySourceTests(unittest.TestCase):
    def test_47_uses_exact_canonical_story_without_paid_or_gemini_request(self):
        with patch.object(stories,'gemini_story') as gemini,patch.object(stories.requests,'post') as post:
            n,topic,story,evidence=stories.select_story(copy.deepcopy(LEDGER))
            self.assertEqual(n,47);self.assertEqual(story,CANON);self.assertEqual(evidence['word_count'],89)
            self.assertEqual(evidence['provider'],'canonical_local_queue');gemini.assert_not_called();post.assert_not_called()
    def test_unattested_gemini_does_not_make_a_request(self):
        transport=Mock()
        with patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(stories.StoryBlocked,'not_attested'):
            stories.gemini_story('topic',transport=transport)
        transport.assert_not_called()
    def test_400_402_403_are_never_blindly_retried_or_logged(self):
        for code in (400,402,403):
            transport=Mock(return_value=Mock(status_code=code,text='secret-upstream-value'));sleep=Mock()
            with patch.dict(os.environ,{'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'true','GEMINI_API_KEY':'not-a-real-secret'}),self.assertRaises(stories.StoryBlocked) as error:
                stories.gemini_story('Kaybolan Oyuncak Kamyon',transport=transport,sleep=sleep)
            self.assertNotIn('secret-upstream-value',str(error.exception));transport.assert_called_once();sleep.assert_not_called()
    def test_429_and_503_have_bounded_increasing_retry(self):
        responses=[Mock(status_code=429),Mock(status_code=503),Mock(status_code=200,json=lambda:{'candidates':[{'content':{'parts':[{'text':json.dumps(CANON)}]}}]})]
        sleep=Mock();transport=Mock(side_effect=responses)
        with patch.dict(os.environ,{'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'true','GEMINI_API_KEY':'test-only'}):
            self.assertEqual(stories.gemini_story('Kaybolan Oyuncak Kamyon',transport=transport,sleep=sleep),CANON)
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[1,2]);self.assertEqual(transport.call_count,3)
    def test_network_timeout_does_not_replay_inference(self):
        transport=Mock(side_effect=requests.Timeout('sensitive URL'))
        with patch.dict(os.environ,{'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'true','GEMINI_API_KEY':'test-only'}),self.assertRaisesRegex(stories.StoryBlocked,'no_replay'):
            stories.gemini_story('Kaybolan Oyuncak Kamyon',transport=transport)
        transport.assert_called_once()
    def test_approved_queue_hash_cannot_be_silently_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'story_queue').mkdir();shutil.copy('story_queue/catalog.json',root/'story_queue/catalog.json')
            (root/'minomasal_v4_47_revize_hikaye.json').write_text('{}')
            with self.assertRaisesRegex(stories.StoryBlocked,'changed_since_approval'):stories.local_story(47,'Kaybolan Oyuncak Kamyon',root)
    def test_repeated_or_too_short_story_rejected_locally(self):
        bad=copy.deepcopy(CANON);bad['scenes'][1]['narration']=bad['scenes'][0]['narration']
        with self.assertRaises(stories.StoryBlocked):stories.validate_story(bad,47,'Kaybolan Oyuncak Kamyon')
        bad=copy.deepcopy(CANON)
        for scene in bad['scenes']:scene['narration']='Tonton geldi.'
        with self.assertRaises(stories.StoryBlocked):stories.validate_story(bad,47,'Kaybolan Oyuncak Kamyon')
    def test_duplicate_narration_fingerprint_in_ledger_stops_reuse(self):
        ledger=copy.deepcopy(LEDGER);ledger['stories']['44']['narration_sha256']=stories.fingerprint(CANON)
        with self.assertRaisesRegex(stories.StoryBlocked,'already_in_ledger'):stories.select_story(ledger)
    def test_next_story_falls_back_to_approved_queue_only(self):
        ledger=copy.deepcopy(LEDGER);ledger['stories']['47']=copy.deepcopy(ledger['stories']['44']);ledger['stories']['47']['topic']='Kaybolan Oyuncak Kamyon'
        with patch.object(stories,'gemini_story',side_effect=stories.StoryBlocked('gemini_text_http_429')),patch.object(stories,'local_story',return_value=CANON) as queue:
            n,topic,_,evidence=stories.select_story(ledger)
        self.assertEqual(n,48);self.assertEqual(evidence['provider'],'approved_local_queue');queue.assert_called_once()

class PreparationTests(unittest.TestCase):
    def test_missing_approved_images_stop_before_speech_or_render_and_never_reserve(self):
        before=Path('minomasal_platform_durumu.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),patch.object(engine,'compose_story') as compose,patch.object(requests,'post') as api:
            out=Path(tmp)/'output';result=engine.prepare(out,render=True)
            self.assertFalse(result['technical_checks_passed']);self.assertFalse(result['publication_approved'])
            self.assertIn('approved_character_assets_missing',result['blockers']);self.assertEqual(result['new_speech_requests'],0)
            self.assertFalse((out/'staging').exists());compose.assert_not_called();api.assert_not_called()
            self.assertEqual(json.loads((out/'story.json').read_text()),CANON)
        self.assertEqual(Path('minomasal_platform_durumu.json').read_bytes(),before)
    def test_preparation_rejects_upload_environment(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PUBLISH_ENABLED':'true'}):
            result=engine.prepare(Path(tmp)/'output',render=True)
            self.assertIn('preparation_cannot_enable_upload',result['blockers'])
    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(RuntimeError,'no_overwrite'):engine.prepare(tmp)

class MediaQualityTests(unittest.TestCase):
    def info(self):
        return {'streams':[{'codec_type':'video','width':1080,'height':1920,'codec_name':'h264','pix_fmt':'yuv420p','duration':'3.0','start_time':'0','avg_frame_rate':'30/1'},
            {'codec_type':'audio','codec_name':'aac','sample_rate':'48000','channels':2,'duration':'3.0','start_time':'0'}],'format':{'duration':'3.0'}}
    def test_real_media_probe_requires_full_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            video=Path(tmp)/'fixture.mp4';video.write_bytes(b'unit-fixture-not-real-video')
            with patch.object(qa,'run',side_effect=[SimpleNamespace(returncode=0,stdout=json.dumps(self.info())),SimpleNamespace(returncode=0)]) as run:
                result=qa.probe_video(video)
            self.assertTrue(result['full_decode_passed']);self.assertEqual(run.call_count,2)
    def test_wrong_resolution_audio_duration_or_codec_cannot_pass(self):
        for field,value in [('width',1920),('pix_fmt','yuv444p'),('duration','nan'),('avg_frame_rate','1/0')]:
            info=self.info();info['streams'][0][field]=value
            with tempfile.TemporaryDirectory() as tmp,patch.object(qa,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(info))):
                video=Path(tmp)/'fixture.mp4';video.write_bytes(b'unit-fixture')
                with self.assertRaises(qa.QualityBlocked):qa.probe_video(video)
    def test_decode_error_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(qa,'run',side_effect=[SimpleNamespace(returncode=0,stdout=json.dumps(self.info())),SimpleNamespace(returncode=1)]):
            video=Path(tmp)/'fixture.mp4';video.write_bytes(b'unit-fixture')
            with self.assertRaisesRegex(qa.QualityBlocked,'full_decode'):qa.probe_video(video)
    def test_audio_clipping_silence_and_long_black_gaps_stop(self):
        for stderr in ('mean_volume: -90 dB\nmax_volume: -90 dB','mean_volume: -10 dB\nmax_volume: 0 dB','mean_volume: -20 dB\nmax_volume: -2 dB\nblack_duration:1.2'):
            with patch.object(qa,'run',return_value=SimpleNamespace(returncode=0,stderr=stderr)),self.assertRaises(qa.QualityBlocked):qa.signal_checks('unit-fixture')
    def test_missing_or_out_of_sync_subtitles_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'captions.srt'
            with self.assertRaises(qa.QualityBlocked):qa.validate_subtitles(path,3)
            path.write_text('1\n00:00:00,000 --> 00:00:09,000\nBad\n')
            with self.assertRaises(qa.QualityBlocked):qa.validate_subtitles(path,3)

class PublicationBoundaryTests(unittest.TestCase):
    def test_branch_artifact_or_failed_preparation_is_not_publishable(self):
        for branch,conclusion in [('other-branch','success'),('main','failure')]:
            transport=Mock(return_value=Mock(status_code=200,json=lambda:{'status':'completed','conclusion':conclusion,'head_branch':branch,'path':'.github/workflows/minomasal-daily-live.yml','event':'workflow_dispatch','head_sha':'a'*40}))
            with self.assertRaises(approval.ApprovalBlocked):approval.source_run('123',transport=transport)
            transport.assert_called_once()
    def test_preparation_commit_must_belong_to_main(self):
        run={'status':'completed','conclusion':'success','head_branch':'main','path':'.github/workflows/minomasal-daily-live.yml','event':'schedule','head_sha':'a'*40}
        transport=Mock(side_effect=[Mock(status_code=200,json=lambda:run),Mock(status_code=200,json=lambda:{'status':'diverged'})])
        with self.assertRaises(approval.ApprovalBlocked):approval.source_run('123',transport=transport)
    def test_approval_requires_exact_sha_not_generic_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'masal_short.mp4').write_bytes(b'not-a-real-story')
            for digest in ('','true','a'*64):
                with self.assertRaises(approval.ApprovalBlocked):approval.validate(path,47,digest)
    def test_graph_authorization_is_never_in_url_or_body(self):
        response=Mock();response.__enter__=Mock(return_value=io.StringIO('{"id":"123"}'));response.__exit__=Mock(return_value=False)
        with patch.object(publisher.urllib.request,'urlopen',return_value=response) as request:
            self.assertEqual(publisher.graph('GET','123',{'access_token':'sensitive-test-value','fields':'id'}),{'id':'123'})
        req=request.call_args.args[0]
        self.assertNotIn('sensitive-test-value',req.full_url);self.assertIsNone(req.data)
        self.assertEqual(req.get_header('Authorization'),'Bearer sensitive-test-value')
    def test_failed_graph_post_is_never_automatically_replayed(self):
        error=publisher.urllib.error.HTTPError('https://example.invalid',500,'raw-sensitive-upstream',None,None)
        with patch.object(publisher.urllib.request,'urlopen',side_effect=error) as request,patch.object(publisher.time,'sleep') as sleep:
            with self.assertRaises(RuntimeError) as raised:publisher.graph('POST','123/media',{'access_token':'test-only'})
        self.assertNotIn('raw-sensitive',str(raised.exception));request.assert_called_once();sleep.assert_not_called()
    def test_skipped_daily_lock_cannot_be_resumed(self):
        import minomasal_gunluk_kilit as lock
        with patch.object(lock,'get_file',return_value=({'status':'skipped','story_number':45},'sha')),patch.object(lock,'_write') as write:
            with self.assertRaises(approval.ApprovalBlocked):approval.reserve(47,'a'*64,True)
            write.assert_not_called()
    def test_partial_retry_cannot_resume_ambiguous_upload(self):
        import minomasal_gunluk_kilit as lock
        old={'status':'reserved','story_number':47,'video_sha256':'a'*64,'run_id':'old','run_attempt':'1'}
        remote={'stories':{'47':{'youtube':{'status':'published'},'instagram':{'status':'ambiguous'}}}}
        with patch.object(lock,'get_file',side_effect=[(old,'sha'),(remote,'sha')]),patch.object(lock,'_write') as write:
            with self.assertRaises(approval.ApprovalBlocked):approval.reserve(47,'a'*64,True)
            write.assert_not_called()
    def test_partial_retry_is_same_video_cas_and_keeps_prior_owner(self):
        import minomasal_gunluk_kilit as lock
        old={'status':'reserved','story_number':47,'video_sha256':'a'*64,'run_id':'old','run_attempt':'1'}
        remote={'stories':{'47':{'youtube':{'status':'published'},'instagram':{'status':'pending'}}}}
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'new','GITHUB_RUN_ATTEMPT':'1'}),patch.object(lock,'get_file',side_effect=[(old,'old-sha'),(remote,'ledger-sha')]),patch.object(lock,'_write',return_value=(200,{})) as write,patch.object(lock,'verify'):
            approval.reserve(47,'a'*64,True)
        self.assertEqual(write.call_args.kwargs['sha'],'old-sha');self.assertEqual(old['resumed_from']['run_id'],'old')
        self.assertEqual(old['status'],'reserved');self.assertEqual(old['video_sha256'],'a'*64)
    def test_receipt_path_cannot_escape_staging(self):
        import minomasal_yayin_guvenligi as safety
        with tempfile.TemporaryDirectory() as tmp:
            video=Path(tmp)/'video.mp4';video.write_bytes(b'unit-fixture')
            video.with_suffix('.production.json').write_text(json.dumps({'video_sha256':safety.digest(video),'assets':[{'path':'../private.key','sha256':'a'*64}]}))
            with self.assertRaisesRegex(RuntimeError,'dosya yolu'):safety.validate_receipt(video)

class PlatformGateTests(unittest.TestCase):
    def transport(self,ledger=None):
        ledger=ledger or LEDGER
        token={'scope':'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly','access_token':'test-only'}
        videos=[{'snippet':{'title':ledger['stories'][str(n)]['title']},'contentDetails':{'videoId':ledger['stories'][str(n)]['youtube']['video_id']}} for n in (43,44)]
        media=[{'id':ledger['stories'][str(n)]['instagram']['media_id'],'caption':ledger['stories'][str(n)]['title']} for n in (43,44)]
        values=[{'items':[{'contentDetails':{'relatedPlaylists':{'uploads':'test-playlist'}}}]},{'items':videos},
            {'data':[{'permission':p,'status':'granted'} for p in ('instagram_basic','instagram_content_publish')]},{'data':media}]
        transport=Mock();transport.post.return_value=Mock(status_code=200,json=lambda:token)
        transport.get.side_effect=[Mock(status_code=200,json=lambda value=v:value) for v in values]
        return transport,token,values
    def test_scopes_accounts_and_history_checked_without_upload(self):
        transport,_,_=self.transport()
        result=platforms.verify(LEDGER,47,'Kaybolan Oyuncak Kamyon',CANON['title'],transport=transport)
        self.assertTrue(result['recent_ledger_accounts_match']);transport.post.assert_called_once()
        self.assertIn('oauth2.googleapis.com/token',transport.post.call_args.args[0])
    def test_youtube_upload_only_token_does_not_count_as_read_access(self):
        transport,token,_=self.transport();token['scope']='https://www.googleapis.com/auth/youtube.upload'
        with self.assertRaisesRegex(platforms.PlatformBlocked,'read_scope_missing'):platforms.verify(LEDGER,47,'topic','title',transport=transport)
        transport.get.assert_not_called()
    def test_readable_instagram_is_not_assumed_publishable(self):
        transport,_,values=self.transport();values[2]['data']=[{'permission':'instagram_basic','status':'granted'}]
        with self.assertRaisesRegex(platforms.PlatformBlocked,'publish_scope_missing'):platforms.verify(LEDGER,47,'topic','title',transport=transport)
    def test_external_duplicate_blocks_even_when_ledger_has_no_candidate(self):
        transport,_,values=self.transport();values[1]['items'].append({'snippet':{'title':CANON['title']},'contentDetails':{'videoId':'external-id'}})
        with self.assertRaisesRegex(platforms.PlatformBlocked,'already_present'):platforms.verify(LEDGER,47,'Kaybolan Oyuncak Kamyon',CANON['title'],transport=transport)
    def test_partial_retry_does_not_reject_its_already_verified_platform(self):
        ledger=copy.deepcopy(LEDGER);ledger['stories']['47']={'youtube':{'status':'published','video_id':'verified-id'},'instagram':{'status':'pending'}}
        transport,_,values=self.transport(ledger)
        values[1]['items'].append({'snippet':{'title':CANON['title']},'contentDetails':{'videoId':'verified-id'}})
        result=platforms.verify(ledger,47,'Kaybolan Oyuncak Kamyon',CANON['title'],transport=transport)
        self.assertFalse(result['candidate_title_or_number_found'])

class WorkflowSafetyTests(unittest.TestCase):
    def test_daily_can_only_prepare_and_cannot_write_or_publish(self):
        flow=yaml.load(Path('.github/workflows/minomasal-daily-live.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(flow['permissions'],{'contents':'read'});self.assertEqual(flow['on']['schedule'],[{'cron':'7 16 * * *'}])
        text=json.dumps(flow)
        for forbidden in ('PUBLISH_ENABLED\\": \\"true','minomasal_dual_publish.py','minomasal_gunluk_kilit.py acquire','YOUTUBE_REFRESH_TOKEN','INSTAGRAM_ACCESS_TOKEN'):
            self.assertNotIn(forbidden,text)
    def test_manual_write_job_needs_successful_read_only_validation_and_explicit_approval(self):
        flow=yaml.load(Path('.github/workflows/minomasal-dual-manual.yml').read_text(),Loader=yaml.BaseLoader)
        job=flow['jobs']['publish-exact-video']
        self.assertEqual(job['needs'],'validate-approved-artifact');self.assertIn('inputs.publish_enabled',job['if'])
        self.assertEqual(flow['on']['workflow_dispatch']['inputs']['publish_enabled']['default'],'false')
        self.assertEqual(flow['permissions']['contents'],'read')
    def test_locked_dependencies_have_no_unpinned_entries(self):
        import re
        lines=Path('requirements-minomasal-engine.lock.txt').read_text().splitlines()
        packages=[line for line in lines if line and not line[0].isspace() and not line.startswith('#')]
        self.assertTrue(packages)
        self.assertTrue(all(re.match(r'[a-zA-Z0-9_.-]+==[^ ]+',line) for line in packages))
        self.assertIn('--hash=sha256:',Path('requirements-minomasal-engine.lock.txt').read_text())


class SharedTTSCostTests(unittest.TestCase):
    def test_direct_tts_helper_cannot_bypass_free_account_gate(self):
        import minomasal_sami_tts_interactions as speech
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'false','GEMINI_API_KEY':'test-only'}),patch.object(speech.genai,'Client') as client:
            with self.assertRaisesRegex(RuntimeError,'TTS isteği yapılmadı'):speech.create_sami_wav('Türkçe test.',Path(tmp)/'test.wav')
            client.assert_not_called()
    def test_speech_keeps_sami_and_uses_one_bounded_request(self):
        import wave
        import minomasal_sami_tts_interactions as speech
        data=io.BytesIO()
        with wave.open(data,'wb') as sound:
            sound.setnchannels(1);sound.setsampwidth(2);sound.setframerate(24000);sound.writeframes(b'\x00\x00'*2400)
        client=Mock();client.interactions.create.return_value=SimpleNamespace(output_audio=SimpleNamespace(data=data.getvalue()))
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'true','GEMINI_API_KEY':'test-only'}),patch.object(speech.genai,'Client',return_value=client) as factory:
            speech.create_sami_wav('Türkçe test.',Path(tmp)/'test.wav')
        self.assertEqual(factory.call_args.kwargs['http_options'],{'timeout':90000,'retry_options':{'attempts':1}})
        client.interactions.create.assert_called_once()
        self.assertEqual(client.interactions.create.call_args.kwargs['model'],'gemini-3.8-flash-tts')
        self.assertEqual(client.interactions.create.call_args.kwargs['generation_config']['speech_config'],[{'voice':'Sami'}])

class FullActionPinningTests(unittest.TestCase):
    def test_every_remote_action_is_pinned(self):
        from minomasal_engine_inventory import inspect
        for workflow in inspect()['workflows']:
            for job in workflow['jobs']:
                self.assertEqual(job['unpinned_actions'],[],workflow['path'])


class AdditionalSafetyTests(unittest.TestCase):
    def test_importing_live_voice_smokes_never_requests_audio(self):
        import importlib.util
        with patch('google.genai.Client') as client:
            for filename in ('test_gemini_sami.py','test_sami_integration.py'):
                spec=importlib.util.spec_from_file_location('safe_import_'+filename[:-3],filename)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            client.assert_not_called()
    def test_legacy_voice_route_does_not_bypass_free_gate(self):
        import asyncio
        import minomasal as mm
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'false'}),patch('google.genai.Client') as client:
            with self.assertRaisesRegex(RuntimeError,'yeni ses isteği yapılmadı'):
                asyncio.run(mm.voices({'scenes':[{'narration':'Türkçe test.'}]},Path(tmp)))
            client.assert_not_called()


class SceneNarrationBindingTests(unittest.TestCase):
    def test_reviewed_images_cannot_be_reused_with_different_narration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir()
            for name in ('minomasal_platform_durumu.json','minomasal_v4_47_revize_hikaye.json','tonton_referans.png'):
                shutil.copy(name,root/name)
            shutil.copytree('story_queue',root/'story_queue')
            visual=root/'visual_assets';visual.mkdir();plans=visual/'story-plans';plans.mkdir()
            assets={state:{'cargo_state':state} for state in ('loaded','unloading','empty')}
            catalog={'assets':assets,'backgrounds':{'test-background':{}},'profiles':{'tonton':{'reference':{'sha256':engine.sha(root/'tonton_referans.png')}}}}
            (visual/'catalog.json').write_text(json.dumps(catalog))
            scenes=[{'inventory':{'tonton':1,'red_bridge':1 if i>=8 else 0},'layers':[{'profile':'tonton','asset':'loaded' if i<=8 else 'unloading' if i==9 else 'empty'}]} for i in range(1,11)]
            (plans/'47.json').write_text(json.dumps(scenes));(plans/'47.review.json').write_text(json.dumps({'story_number':47,'narration_sha256':'different-story'}))
            def compose(catalog,plans,output):
                output.mkdir();return [],{'scenes':[]}
            with patch.dict(os.environ,{'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'true','PUBLISH_ENABLED':'false','MINOMASAL_YOUTUBE_UPLOAD':'false'}),patch.object(engine,'compose_story',side_effect=compose),patch.object(engine,'validate_local_handoff') as handoff,patch.object(requests,'post') as inference:
                report=engine.prepare(Path(tmp)/'output',root=root,render=True)
                self.assertIn('scene_review_story_binding_missing_or_changed',report['blockers'])
                handoff.assert_not_called();inference.assert_not_called()
                self.assertFalse((Path(tmp)/'output/staging').exists())


class InstagramReelVerificationTests(unittest.TestCase):
    def test_normal_video_or_wrong_link_cannot_be_recorded_as_verified_reel(self):
        for product,link in [('FEED','https://www.instagram.com/p/test/'),('REELS','https://example.invalid/reel/test/')]:
            item={'id':'123','media_type':'VIDEO','media_product_type':product,'permalink':link}
            with self.assertRaises(RuntimeError):publisher.verified_instagram_permalink(item,'123')
    def test_api_verified_reel_permalink_is_retained(self):
        link='https://www.instagram.com/reel/test/'
        self.assertEqual(publisher.verified_instagram_permalink({'id':'123','media_type':'VIDEO','media_product_type':'REELS','permalink':link},'123'),link)

if __name__=='__main__':unittest.main()
