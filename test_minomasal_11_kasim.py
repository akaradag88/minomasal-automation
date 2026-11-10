"""11 November rollover: in-memory GitHub API, no rendering or publishing."""
import asyncio
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import minomasal as mm
import minomasal_daily_live as daily
import minomasal_gunluk_kilit as lock
from test_minomasal_gunluk_kilit import FakeContentsAPI


class NovemberReadinessTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeContentsAPI()
        for path in Path(lock.LOCK_DIR).glob('*.json'):
            self.api.put_json(str(path), json.loads(path.read_text(encoding='utf-8')))
        self.ledger = json.loads(Path(daily.LEDGER).read_text(encoding='utf-8'))
        self.api.put_json(str(daily.LEDGER), copy.deepcopy(self.ledger))
        self.initial = copy.deepcopy(self.api.files)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.meta = Path(self.tmp.name)/'metadata.json'
        self.meta.write_text(json.dumps({'number':47,'topic':mm.KONULAR[46]}))
        for context in (
            patch.object(lock, '_request', side_effect=self.api.request),
            patch.dict(os.environ, {'GITHUB_RUN_ID':'offline-11', 'GITHUB_RUN_ATTEMPT':'1',
                                    'GITHUB_OUTPUT':str(Path(self.tmp.name)/'output')}, clear=True),
        ):
            context.start(); self.addCleanup(context.stop)

    def test_nov10_skip_is_read_only(self):
        with patch.object(lock, 'today', return_value='2026-11-10'):
            self.assertFalse(lock.preflight())
            self.assertFalse(lock.acquire(47, self.meta))
        self.assertEqual(self.api.files, self.initial)
        self.assertFalse(any(method=='PUT' for method, _ in self.api.tries))

    def test_nov11_allows_47_once_preserving_skipped_records(self):
        self.assertEqual(daily.choose(self.ledger),47)
        with patch.object(lock,'today',return_value='2026-11-11'):
            self.assertTrue(lock.preflight())
            self.assertFalse(any(method=='PUT' for method, _ in self.api.tries))
            self.assertTrue(lock.acquire(47,self.meta))
            lock.verify(47,'2026-11-11')
            self.assertFalse(lock.acquire(47,self.meta))
        for path,value in self.initial.items(): self.assertEqual(self.api.files[path],value)
        self.assertEqual(self.api.files[lock.path_for('2026-11-11')]['status'],'reserved')

    def test_reserved_nov11_blocks_nov12(self):
        with patch.object(lock,'today',return_value='2026-11-11'):
            self.assertTrue(lock.acquire(47,self.meta))
        with patch.object(lock,'today',return_value='2026-11-12'):
            self.assertFalse(lock.preflight())

    def test_skipped_number_cannot_be_reused(self):
        for number in (45,46):
            self.meta.write_text(json.dumps({'number':number,'topic':mm.KONULAR[number-1]}))
            with patch.object(lock,'today',return_value='2026-11-11'):
                with self.assertRaisesRegex(RuntimeError,'zaten mevcut'):
                    lock.acquire(number,self.meta)
        self.assertEqual(self.api.files,self.initial)

    def test_istanbul_midnight_changes_date(self):
        for instant, expected in [('2026-11-10T20:59:59+00:00','2026-11-10'),
                                  ('2026-11-10T21:00:00+00:00','2026-11-11')]:
            with patch.object(lock,'datetime') as clock:
                clock.now.side_effect=lambda tz: datetime.fromisoformat(instant).astimezone(tz)
                self.assertEqual(lock.today(),expected)

    def test_actual_402_stops_produce_before_voice_render_or_complete_marker(self):
        story={'title':'Test','characters':'Fox','scenes':[
            {'narration':'Merhaba orman.','visual':'A fox'} for _ in range(10)]}
        root=Path(self.tmp.name)/'production'
        with patch.object(mm,'ROOT',root), patch.object(mm,'API_KEY','offline-secret'), \
             patch.object(mm.requests,'get',return_value=Mock(status_code=402)) as get, \
             patch.object(mm.time,'sleep') as sleep, patch.object(mm,'voices') as voices, \
             patch.object(mm,'render') as render:
            with self.assertRaisesRegex(RuntimeError,'402.*bakiye/kredi'):
                asyncio.run(mm.produce(mm.KONULAR[46],supplied_story=story))
            get.assert_called_once(); sleep.assert_not_called()
            voices.assert_not_called(); render.assert_not_called()
        self.assertFalse(list(root.rglob('tamam.json')))
        self.assertFalse(list(root.rglob('*.mp4')))

    def test_402_aborts_stage_before_metadata_or_publication(self):
        import minomasal_gunluk_kalite_stage_v3 as stage
        story={'title':'Test','characters':'Fox','scenes':[
            {'narration':'Merhaba orman.','visual':'A fox'} for _ in range(10)]}
        output=Path(os.environ['GITHUB_OUTPUT']); output.write_text('')
        target=Path(self.tmp.name)/'staging'
        with patch.object(mm, 'create_story', mm.create_story), \
             patch.object(mm, 'voices', mm.voices), \
             patch.object(stage, 'create_story_v2',return_value=story), \
             patch.object(mm,'produce',side_effect=RuntimeError('HTTP 402')) as produce, \
             patch.object(daily,'STAGING',target), patch.object(mm,'ROOT',Path(self.tmp.name)/'data'):
            with self.assertRaisesRegex(RuntimeError,'402'): asyncio.run(stage.main())
            produce.assert_awaited_once()
        self.assertFalse((target/'metadata.json').exists())
        self.assertEqual(output.read_text(),'')
        self.assertEqual(self.api.files,self.initial)


if __name__ == '__main__': unittest.main()
