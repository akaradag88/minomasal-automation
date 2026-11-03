"""GitHub agina baglanmadan gunluk kilit davranis testleri."""
import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import minomasal_gunluk_kilit as lock


class FakeContentsAPI:
    def __init__(self):
        self.files = {}
        self.tries = []
        self.before_put = None

    def put_json(self, path, value):
        self.files[path] = value

    def request(self, method, path, body=None):
        self.tries.append((method, path))
        if method == 'GET':
            if path == lock.LOCK_DIR:
                items = [{'type': 'file', 'name': p.rsplit('/', 1)[-1], 'path': p} for p in self.files if p.startswith(lock.LOCK_DIR + '/') ]
                if not items:
                    raise lock.GitHubHttpError(404, 'Not Found')
                return 200, items
            if path not in self.files:
                raise lock.GitHubHttpError(404, 'Not Found')
            v = self.files[path]
            return 200, {
                'encoding': 'base64', 'sha': 'sha-' + path,
                'content': base64.b64encode(json.dumps(v).encode()).decode(),
            }
        if method == 'PUT':
            if self.before_put:
                cb, self.before_put = self.before_put, None
                cb(path)
            if path in self.files and 'sha' not in body:
                raise lock.GitHubHttpError(422, 'sha required')
            if path in self.files and body.get('sha') != 'sha-' + path:
                raise lock.GitHubHttpError(409, 'sha conflict')
            data = json.loads(base64.b64decode(body['content']))
            creating = path not in self.files
            self.files[path] = data
            return (201 if creating else 200), {'content': {}}
        raise AssertionError(method)


class DailyLockTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeContentsAPI()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.meta = Path(self.tmp.name) / 'metadata.json'
        self.meta.write_text(json.dumps({'number': 40, 'topic': 'Panda'}), encoding='utf-8')
        self.api.put_json('minomasal_platform_durumu.json', {
            'stories': {'39': {'youtube': {'status': 'published'}, 'instagram': {'status': 'published'}}}
        })
        self.env = patch.dict(os.environ, {
            'GITHUB_REPOSITORY': 'akaradag88/minomasal-automation',
            'MINOMASAL_LOCK_TOKEN': 'fake-test-token',
            'GITHUB_RUN_ID': '7777', 'GITHUB_RUN_ATTEMPT': '1',
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.request_patch = patch.object(lock, '_request', side_effect=self.api.request)
        self.request_patch.start()
        self.addCleanup(self.request_patch.stop)
        self.today_patch = patch.object(lock, 'today', return_value='2026-11-04')
        self.today_patch.start()
        self.addCleanup(self.today_patch.stop)

    def test_no_lock_preflight_then_acquire_and_verify(self):
        self.assertTrue(lock.preflight())
        self.assertTrue(lock.acquire(40, self.meta))
        lock.verify(40, '2026-11-04')
        self.assertFalse(lock.preflight())

    def test_same_day_double_acquire_blocked(self):
        self.assertTrue(lock.acquire(40, self.meta))
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '8888'}):
            self.assertFalse(lock.acquire(40, self.meta))
            with self.assertRaisesRegex(RuntimeError, 'ait degil'):
                lock.verify(40, '2026-11-04')

    def test_number_mismatch_stops(self):
        with self.assertRaisesRegex(RuntimeError, 'eslesmiyor'):
            lock.acquire(41, self.meta)

    def test_remote_ledger_already_contains_story_stops(self):
        self.api.files['minomasal_platform_durumu.json']['stories']['40'] = {}
        with self.assertRaisesRegex(RuntimeError, 'zaten mevcut'):
            lock.acquire(40, self.meta)

    def test_fail_closed_if_unauthorized(self):
        def deny(method, path, body=None):
            raise lock.GitHubHttpError(401, 'Unauthorized')
        with patch.object(lock, '_request', side_effect=deny):
            with self.assertRaises(lock.GitHubHttpError):
                lock.preflight()

    def test_finish_only_after_both_platforms_published(self):
        lock.acquire(40, self.meta)
        with self.assertRaisesRegex(RuntimeError, 'tamam degil'):
            lock.finish(40, '2026-11-04')
        self.assertEqual(self.api.files[lock.path_for('2026-11-04')]['status'], 'reserved')
        self.api.files['minomasal_platform_durumu.json']['stories']['40'] = {
            'youtube': {'status': 'published', 'video_id': 'y123'},
            'instagram': {'status': 'published', 'media_id': 'i123'},
        }
        lock.finish(40, '2026-11-04')
        self.assertEqual(self.api.files[lock.path_for('2026-11-04')]['status'], 'published')
        with self.assertRaisesRegex(RuntimeError, 'zaten tamamlandi'):
            lock.verify(40, '2026-11-04')

    def test_concurrent_create_race_is_safe_skip(self):
        def another_run_wins(path):
            self.api.files[path] = {
                'date': '2026-11-04', 'story_number': 40,
                'run_id': 'OTHER', 'run_attempt': '1', 'status': 'reserved',
            }
        self.api.before_put = another_run_wins
        self.assertFalse(lock.acquire(40, self.meta))

    def test_previous_day_reserved_stops_new_day(self):
        self.api.files[lock.path_for('2026-11-03')] = {
            'status': 'reserved', 'story_number': 39
        }
        self.assertFalse(lock.preflight())
        with self.assertRaisesRegex(RuntimeError, 'onceki kilit'):
            lock.acquire(40, self.meta)

    def test_minimum_start_date_prevents_nov_3_second_publish(self):
        with patch.dict(os.environ, {'MINOMASAL_LOCK_START_DATE': '2026-11-04'}):
            with patch.object(lock, 'today', return_value='2026-11-03'):
                self.assertFalse(lock.preflight())
                with self.assertRaisesRegex(RuntimeError, 'Baslangic tarihi'):
                    lock.acquire(40, self.meta)

    def test_invalid_day_rejected(self):
        with self.assertRaises(RuntimeError):
            lock.path_for('../2026-11-04')

    def test_different_day_has_distinct_lock(self):
        lock.acquire(40, self.meta)
        self.api.files[lock.path_for('2026-11-04')]['status'] = 'published'
        with patch.object(lock, 'today', return_value='2026-11-05'):
            self.assertTrue(lock.preflight())


if __name__ == '__main__':
    unittest.main()
