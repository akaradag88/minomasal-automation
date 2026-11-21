"""No network: account checker never sends generation requests or prints secrets."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch

import minomasal_pollinations_check as audit


class AccountCheckTests(unittest.TestCase):
    def test_missing_secret_makes_no_requests(self):
        with patch.object(audit,'account_get') as get:
            self.assertFalse(audit.check('')['secret_configured']); get.assert_not_called()

    def test_positive_balance_only_reads_account_endpoints(self):
        with patch.object(audit,'account_get',side_effect=[({'http_status':200},{'valid':True,'key':'TOP_SECRET'}),({'http_status':200},{'balance':1.5,'sensitive':'TOP_SECRET'})]) as get:
            result=audit.check('TOP_SECRET')
        self.assertEqual([c.args[0] for c in get.call_args_list],list(audit.ALLOWED))
        self.assertEqual(result['available_pollen'],1.5)
        self.assertTrue(result['authenticated']); self.assertNotIn('TOP_SECRET',json.dumps(result))

    def test_zero_balance_is_blocker(self):
        with patch.object(audit,'account_get',side_effect=[({'http_status':200},{'valid':True}),({'http_status':200},{'balance':0})]):
            self.assertEqual(audit.check('secret')['action'],'account_or_key_budget_exhausted')

    def test_402_and_401_do_not_retry(self):
        for status,action in [(402,'account_or_key_budget_exhausted'),(401,'invalid_or_expired_key')]:
            with patch.object(audit,'account_get',return_value=({'http_status':status},None)) as get:
                self.assertEqual(audit.check('secret')['action'],action); get.assert_called_once()

    def test_permission_denied_does_not_claim_balance(self):
        with patch.object(audit,'account_get',side_effect=[({'http_status':200},{'valid':True}),({'http_status':403},None)]):
            result=audit.check('secret')
        self.assertTrue(result['authenticated']); self.assertFalse(result['balance_verified'])

    def test_malformed_balance_is_not_accepted(self):
        for value in (True,'1',float('nan'),None):
            with patch.object(audit,'account_get',side_effect=[({'http_status':200},{'valid':True}),({'http_status':200},{'balance':value})]):
                self.assertFalse(audit.check('secret')['balance_verified'])

    def test_generation_endpoint_refused(self):
        with patch.object(audit.urllib.request,'build_opener') as build:
            with self.assertRaises(ValueError):audit.account_get('/image/cat','secret')
            build.assert_not_called()

    def test_key_in_header_only_and_redirects_blocked(self):
        response=Mock(status=200);response.read.return_value=b'{"valid":true}'
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch.object(audit.urllib.request,'build_opener',return_value=opener):
            status,data=audit.account_get('/account/key','TOP_SECRET')
        req=opener.open.call_args.args[0]
        self.assertEqual(req.full_url,'https://gen.pollinations.ai/account/key')
        self.assertEqual(req.get_method(),'GET');self.assertIsNone(req.data)
        self.assertNotIn('TOP_SECRET',req.full_url)
        self.assertEqual(req.get_header('Authorization'),'Bearer TOP_SECRET')
        self.assertIsNone(audit.NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid'))

    def test_connection_exception_does_not_leak(self):
        opener=Mock();opener.open.side_effect=RuntimeError('TOP_SECRET')
        with patch.object(audit.urllib.request,'build_opener',return_value=opener):
            result,data=audit.account_get('/account/key','TOP_SECRET')
        self.assertNotIn('TOP_SECRET',json.dumps(result));self.assertIsNone(data)

    def test_stdout_and_summary_sanitized(self):
        result={'secret_configured':True,'authenticated':True,'balance_verified':True,'available_pollen':2}
        with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp), patch.dict(os.environ,{'POLLINATIONS_API_KEY':'TOP_SECRET','GITHUB_STEP_SUMMARY':str(Path(tmp)/'summary')}),patch.object(audit,'check',return_value=result),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(audit.main(),0)
            self.assertNotIn('TOP_SECRET',output.getvalue())
            self.assertNotIn('TOP_SECRET',Path('summary').read_text())


if __name__=='__main__':unittest.main()
