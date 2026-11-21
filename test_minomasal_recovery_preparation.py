import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch,Mock
from urllib.parse import parse_qs,urlsplit
import minomasal_recovery_package as packet

spec=importlib.util.spec_from_file_location('oauth_helper',Path('scripts/minomasal_youtube_reauthorize.py'))
oauth=importlib.util.module_from_spec(spec);spec.loader.exec_module(oauth)

class RecoveryPreparationTests(unittest.TestCase):
    def test_existing_tonton_story_packet_is_offline_and_not_approved(self):
        ledger=Path('minomasal_platform_durumu.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'packet';report=packet.build_package(out)
            self.assertEqual(report['narration_words'],89)
            self.assertEqual(report['network_calls'],0)
            self.assertFalse(report['ready_for_publication'])
            self.assertFalse(report['production_receipt'])
            self.assertFalse(report['known_reference_limitations']['usable_as_complete_rgba_production_sprite'])
            story=json.loads((out/'story.json').read_text())
            self.assertEqual(story,json.loads(Path('minomasal_v4_47_revize_hikaye.json').read_text()))
            self.assertIn('Tonton',story['characters'])
            self.assertEqual((out/'reference.png').read_bytes(),Path('tonton_referans.png').read_bytes())
            self.assertFalse(list(out.rglob('*.mp4')))
            with self.assertRaisesRegex(ValueError,'no_overwrite'):packet.build_package(out)
        self.assertEqual(Path('minomasal_platform_durumu.json').read_bytes(),ledger)
    def test_packet_cannot_reuse_an_already_published_story_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ledger=json.loads(Path('minomasal_platform_durumu.json').read_text())
            ledger['stories']['47']=copy.deepcopy(ledger['stories']['44'])
            ledger['stories']['47']['topic']='Kaybolan Oyuncak Kamyon'
            (root/'minomasal_platform_durumu.json').write_text(json.dumps(ledger))
            with self.assertRaisesRegex(ValueError,'not_current_ledger_candidate'):packet.build_package(root/'output',root=root)
            self.assertFalse((root/'output').exists())
    def test_recovery_draft_uses_existing_story_not_fox_trial(self):
        draft=json.loads(Path('docs/recovery/story-47-draft.json').read_text())
        original=json.loads(Path('minomasal_v4_47_revize_hikaye.json').read_text())
        self.assertEqual(draft['narrations'],[s['narration'] for s in original['scenes']])
        self.assertEqual(draft['source_sha256'],packet.digest(Path(draft['source'])))
        self.assertFalse(draft['publication_approved'])
    def test_local_oauth_requests_only_required_scopes_with_state_and_pkce(self):
        url=oauth.authorization_url('local.apps.googleusercontent.com','http://127.0.0.1:8765/','state','verifier')
        query=parse_qs(urlsplit(url).query)
        self.assertEqual(set(query['scope'][0].split()),set(oauth.SCOPES))
        self.assertEqual(query['code_challenge_method'],['S256'])
        self.assertEqual(query['access_type'],['offline'])
        self.assertNotIn('client_secret',query)
        self.assertEqual(urlsplit(url).hostname,'accounts.google.com')
    def test_callback_rejects_wrong_or_duplicate_state_and_denial(self):
        for query in ('code=secret&state=wrong','code=secret','state=correct&state=correct&code=secret','state=correct&error=access_denied','state=correct&code=one&code=two'):
            with self.subTest(query=query),self.assertRaises(oauth.OAuthError) as error:oauth.callback_code(query,'correct')
            self.assertNotIn('secret',str(error.exception))
        self.assertEqual(oauth.callback_code('state=correct&code=test-code','correct'),'test-code')
    def test_missing_read_scope_never_yields_refreshed_credentials(self):
        data={'scope':oauth.SCOPES[0],'refresh_token':'secret','access_token':'sensitive'}
        with self.assertRaises(oauth.OAuthError) as error:oauth.validate_tokens(data)
        self.assertNotIn('sensitive',str(error.exception))
        data['scope']=' '.join(oauth.SCOPES)
        self.assertEqual(oauth.validate_tokens(data),('secret','sensitive'))
    def test_local_secret_is_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'token.private';oauth.write_private(path,'test-only-token')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            with self.assertRaises(FileExistsError):oauth.write_private(path,'replacement')
            self.assertEqual(path.read_text(),'test-only-token\n')
            link=Path(tmp)/'link.private';link.symlink_to(path)
            with self.assertRaises(FileExistsError):oauth.write_private(link,'replacement')
    def test_windows_permission_failure_saves_no_secret(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(oauth,'WINDOWS',True),patch.object(oauth.subprocess,'run',side_effect=OSError('permission error with private details')):
            path=Path(tmp)/'failed.private'
            with self.assertRaises(oauth.OAuthError):oauth.write_private(path,'secret')
            self.assertFalse(path.exists())
    def test_windows_acl_is_set_before_writing_token(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(oauth,'WINDOWS',True):
            path=Path(tmp)/'token.private'
            def call(command,**kwargs):
                self.assertEqual(path.read_bytes(),b'')
                return Mock(stdout='"local-user","S-1-5-21-123"\n')
            with patch.object(oauth.subprocess,'run',side_effect=call) as run:
                oauth.write_private(path,'secret')
            self.assertEqual(run.call_count,2)
            self.assertIn('/inheritance:r',run.call_args.args[0])
            self.assertEqual(path.read_text(),'secret\n')
    def test_invalid_client_details_are_not_exposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'client.json';path.write_text('{"web":{"client_id":"sensitive"}}')
            with self.assertRaises(oauth.OAuthError) as error:oauth.load_client(path)
            self.assertNotIn('sensitive',str(error.exception))
    def test_oauth_never_runs_on_github_runner(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true'}),patch('sys.argv',['oauth','--client-file','unused']),patch.object(oauth,'load_client') as load:
            with self.assertRaises(oauth.OAuthError):oauth.main()
            load.assert_not_called()

if __name__=='__main__':unittest.main()
