import unittest
from unittest.mock import Mock
from minomasal_recovery_audit import safe_youtube_error

class RecoveryAuditTests(unittest.TestCase):
    def test_only_allowlisted_error_code_escapes(self):
        response=Mock();response.json.return_value={'error':{'message':'secret','errors':[{'reason':'insufficientPermissions'},{'reason':'secret-token-value'}]}}
        self.assertEqual(safe_youtube_error(response),['insufficientPermissions'])
    def test_unknown_error_and_invalid_json_are_withheld(self):
        response=Mock();response.json.return_value={'error':{'errors':[{'reason':'sensitive'}]}}
        self.assertEqual(safe_youtube_error(response),['unclassified_response_withheld'])
        response.json.side_effect=ValueError('secret')
        self.assertEqual(safe_youtube_error(response),['unclassified_response_withheld'])

class SpeechCostGuardTests(unittest.TestCase):
    def test_real_speech_is_not_called_without_free_account_attestation(self):
        import io,json,os,tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        from unittest.mock import patch,Mock
        import minomasal_recovery_audit as audit
        def response(status,data):return Mock(status_code=status,json=lambda:data)
        gets=[response(403,{'error':{'errors':[{'reason':'insufficientPermissions'}]}}),
              response(200,{'data':[]}),response(200,{'data':[]}),
              response(200,{'models':[{'name':'models/gemini-3.8-flash-tts'},{'name':'models/gemini-3.8-flash'}]})]
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MINOMASAL_AUDIT_OUTPUT':str(Path(tmp)/'audit'),'MINOMASAL_GEMINI_FREE_TIER_CONFIRMED':'false','MINOMASAL_TEST_REAL_TTS':'true'}),patch.object(audit,'run_check',return_value={'status':'preflight'}),patch.object(audit.requests,'post',return_value=response(200,{'access_token':'test-only','scope':'https://www.googleapis.com/auth/youtube.upload'})),patch.object(audit.requests,'get',side_effect=gets),patch('minomasal_sami_tts_interactions.create_sami_wav') as speech,redirect_stdout(io.StringIO()):
            audit.main();report=json.loads((Path(tmp)/'audit/report.json').read_text())
            self.assertFalse(report['speech']['generation_tested']);self.assertFalse(report['speech']['free_generation_verified']);speech.assert_not_called()
            self.assertFalse(report['candidate_47_history']['both_platforms_verified'])
