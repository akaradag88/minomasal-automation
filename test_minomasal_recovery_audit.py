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
