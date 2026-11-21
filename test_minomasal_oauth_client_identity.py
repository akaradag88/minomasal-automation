import hashlib
import hmac
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import minomasal_oauth_client_identity as identity

ANALYTICS='100-analytics_test.apps.googleusercontent.com'
COLAB='100-colab_test.apps.googleusercontent.com'

def packet():
    nonce='ab'*32
    proof=lambda value:hmac.new(bytes.fromhex(nonce),identity.DOMAIN+value.encode(),hashlib.sha256).hexdigest()
    return {'version':1,'nonce':nonce,'analytics':proof(ANALYTICS),'colab':proof(COLAB)}

class ClientIdentityTests(unittest.TestCase):
    def test_each_label_requires_exact_configured_id_and_google_refresh_success(self):
        for client,label in [(ANALYTICS,'MinoMasal Analytics Client'),(COLAB,'MinoMasal Colab Client')]:
            api=Mock(return_value=Mock(status_code=200,json=lambda:{'access_token':'access-test-sensitive'}))
            with patch.dict(os.environ,{'YOUTUBE_CLIENT_ID':client,'YOUTUBE_CLIENT_SECRET':'secret-test-sensitive','YOUTUBE_REFRESH_TOKEN':'refresh-test-sensitive'}):
                result=identity.compare(packet(),transport=api)
            self.assertEqual(result['confirmed_choice'],label);self.assertTrue(result['refresh_pair_verified']);api.assert_called_once()
            text=json.dumps(result)
            for private in (client,'access-test-sensitive','secret-test-sensitive','refresh-test-sensitive',packet()['analytics'],packet()['colab']):
                self.assertNotIn(private,text)
            self.assertFalse(result['secrets_modified']);self.assertFalse(result['token_revoked']);self.assertFalse(result['published'])
    def test_shared_prefix_alone_does_not_match(self):
        api=Mock()
        with patch.dict(os.environ,{'YOUTUBE_CLIENT_ID':'100-third_test.apps.googleusercontent.com'}):
            result=identity.compare(packet(),transport=api)
        self.assertIsNone(result['matched_client']);self.assertIsNone(result['confirmed_choice']);api.assert_not_called()
    def test_id_match_is_not_claimed_as_token_binding_on_google_failure(self):
        api=Mock(return_value=Mock(status_code=400,text='raw-sensitive-details'))
        with patch.dict(os.environ,{'YOUTUBE_CLIENT_ID':COLAB,'YOUTUBE_CLIENT_SECRET':'test-only','YOUTUBE_REFRESH_TOKEN':'test-only'}):
            result=identity.compare(packet(),transport=api)
        self.assertEqual(result['matched_client'],'MinoMasal Colab Client');self.assertIsNone(result['confirmed_choice']);self.assertFalse(result['refresh_pair_verified'])
        self.assertNotIn('raw-sensitive-details',json.dumps(result))
    def test_bad_or_raw_credential_packet_is_rejected_before_api(self):
        for bad in ({'installed':{'client_secret':'never-send'}},{**packet(),'client_id':COLAB},{**packet(),'nonce':'short'}, {**packet(),'version':True}):
            api=Mock()
            with self.assertRaises(ValueError):identity.compare(bad,transport=api)
            api.assert_not_called()
    def test_duplicate_candidate_proofs_are_rejected(self):
        value=packet();value['colab']=value['analytics']
        with self.assertRaises(ValueError):identity.parse_packet(value)
    def test_refresh_errors_do_not_leak_tokens_or_retry(self):
        api=Mock(side_effect=RuntimeError('sensitive-auth-details'))
        with patch.dict(os.environ,{'YOUTUBE_CLIENT_ID':COLAB,'YOUTUBE_CLIENT_SECRET':'test-only','YOUTUBE_REFRESH_TOKEN':'test-only'}):
            result=identity.compare(packet(),transport=api)
        api.assert_called_once();self.assertNotIn('sensitive-auth-details',json.dumps(result));self.assertIsNone(result['confirmed_choice'])
    def test_local_page_is_standalone_and_network_disabled(self):
        page=Path('tools/minomasal-oauth-client-kontrol.html').read_text()
        self.assertIn("connect-src 'none'",page)
        for api in ('fetch(','XMLHttpRequest','localStorage','sessionStorage','console.log'):
            self.assertNotIn(api,page)
        self.assertNotIn('<script src=',page)

if __name__=='__main__':unittest.main()
