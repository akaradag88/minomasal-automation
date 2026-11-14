import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import minomasal_account_preflight as audit
spec=importlib.util.spec_from_file_location('oauth_account',Path('scripts/minomasal_youtube_reauthorize.py'))
oauth=importlib.util.module_from_spec(spec);spec.loader.exec_module(oauth)

class AccountPreflightTests(unittest.TestCase):
    def response(self,status,data):return Mock(status_code=status,json=lambda:data)
    def test_current_403_endpoint_is_precise_and_details_redacted(self):
        net=Mock();net.post.return_value=self.response(200,{'access_token':'test-secret','scope':audit.UPLOAD})
        net.get.return_value=self.response(403,{'error':{'message':'sensitive-upstream','errors':[{'reason':'insufficientPermissions'}]}})
        result=audit.youtube('test-refresh',transport=net)
        self.assertTrue(result['upload_scope_verified']);self.assertFalse(result['read_scope_verified'])
        self.assertEqual(result['safe_reason'],'insufficientPermissions');self.assertIn('/channels?',result['endpoint'])
        self.assertNotIn('test-secret',json.dumps(result));self.assertNotIn('sensitive-upstream',json.dumps(result))
    def test_new_token_must_match_known_minomasal_channel(self):
        net=Mock();net.post.return_value=self.response(200,{'access_token':'test-secret','scope':audit.UPLOAD+' '+audit.READ})
        ids=audit.expected_videos()
        net.get.side_effect=[self.response(200,{'items':[{'id':'canonical-channel'}]}),self.response(200,{'items':[{'id':video,'snippet':{'channelId':'wrong-channel'}} for video in ids]})]
        result=audit.youtube('candidate-test',transport=net)
        self.assertFalse(result['channel_matches_ledger']);self.assertEqual(result['status'],'scope_or_channel_mismatch')
    def test_verified_candidate_uses_existing_client_and_never_uploads(self):
        net=Mock();net.post.return_value=self.response(200,{'access_token':'test-secret','scope':audit.UPLOAD+' '+audit.READ})
        ids=audit.expected_videos()
        net.get.side_effect=[self.response(200,{'items':[{'id':'canonical-channel'}]}),self.response(200,{'items':[{'id':video,'snippet':{'channelId':'canonical-channel'}} for video in ids]})]
        with patch.dict(os.environ,{'YOUTUBE_CLIENT_ID':'existing-client','YOUTUBE_CLIENT_SECRET':'test-only'}):result=audit.youtube('candidate-test',transport=net)
        self.assertEqual(result['status'],'verified');self.assertFalse(result['upload_test_performed'])
        net.post.assert_called_once();self.assertEqual(net.post.call_args.kwargs['data']['client_id'],'existing-client')
    def test_unconfigured_candidate_makes_no_api_request(self):
        net=Mock();self.assertEqual(audit.youtube('',transport=net)['status'],'not_configured');net.post.assert_not_called();net.get.assert_not_called()
    def test_model_list_is_not_free_quota_proof_and_never_synthesizes(self):
        net=Mock();net.get.return_value=self.response(200,{'models':[{'name':'models/gemini-3.8-flash-tts'},{'name':'models/gemini-3.8-flash-lite-tts'}]})
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GEMINI_API_KEY':'test-only','MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'false'}),patch('minomasal_sami_tts_interactions.create_sami_wav') as voice:
            result=audit.gemini(tmp,transport=net);voice.assert_not_called()
        self.assertEqual(len(result['tts_models']),2);self.assertFalse(result['quota_api_verified']);self.assertIsNone(result['remaining_free_quota']);self.assertFalse(result['speech_test_performed'])
    def test_audio_error_never_leaks_upstream_message(self):
        net=Mock();net.get.return_value=self.response(200,{'models':[{'name':'models/gemini-3.8-flash-tts'}]})
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GEMINI_API_KEY':'test-only','MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'true'}),patch('minomasal_sami_tts_interactions.create_sami_wav',side_effect=RuntimeError('raw-sensitive-token')):
            result=audit.gemini(tmp,transport=net)
        self.assertNotIn('raw-sensitive',json.dumps(result));self.assertEqual(result['status'],'request_failed_details_withheld')
    def test_candidate_write_uses_stdin_and_only_candidate_secret(self):
        with patch.object(oauth.subprocess,'run',return_value=Mock(returncode=0)) as run:oauth.stage_candidate('test-refresh-secret')
        args=run.call_args.args[0];self.assertIn('YOUTUBE_REFRESH_TOKEN_CANDIDATE',args);self.assertNotIn('test-refresh-secret',args)
        self.assertEqual(run.call_args.kwargs['input'],'test-refresh-secret');self.assertTrue(run.call_args.kwargs['capture_output'])
    def test_new_refresh_itself_and_ledger_channel_checked_before_save(self):
        values=[{'access_token':'refreshed-test-access','scope':' '.join(oauth.SCOPES)},
            {'items':[{'id':'mine'}]}, {'items':[{'id':video,'snippet':{'channelId':'mine'}} for video in oauth.expected_video_ids()]}]
        def response(*args,**kwargs):
            stream=io.StringIO(json.dumps(values.pop(0)))
            return stream
        with patch.object(oauth.urllib.request,'urlopen',side_effect=response) as open_request:oauth.verify_new_refresh('existing-client','test-only','new-refresh-test')
        self.assertEqual(open_request.call_count,3)
        self.assertIn(b'grant_type=refresh_token',open_request.call_args_list[0].args[0].data)
    def test_wrong_channel_or_missing_read_cannot_replace_old_token(self):
        data={'access_token':'test-only','scope':oauth.UPLOAD if hasattr(oauth,'UPLOAD') else oauth.SCOPES[0]}
        with patch.object(oauth.urllib.request,'urlopen',return_value=io.StringIO(json.dumps(data))),patch.object(oauth,'write_private') as save,patch.object(oauth,'stage_candidate') as stage:
            with self.assertRaises(oauth.OAuthError):oauth.verify_new_refresh('client','secret','candidate')
            save.assert_not_called();stage.assert_not_called()

if __name__=='__main__':unittest.main()
