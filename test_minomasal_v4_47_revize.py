"""Offline tests: NEVER calls social APIs or paid image API."""
import base64
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import minomasal_v4_47_revize_pilot as pilot


class RevisedPilotTests(unittest.TestCase):
    def test_story_10_scenes_and_natural_name_count(self):
        story, words, mentions = pilot.validate_story()
        self.assertEqual(10, len(story['scenes']))
        self.assertEqual(89, words)
        self.assertEqual(2, mentions)

    def test_no_publish_environment_guard(self):
        with patch.dict(os.environ, {'PUBLISH_ENABLED': 'true'}):
            with self.assertRaises(RuntimeError):
                pilot.no_publish_guard()

    def test_rendering_uses_actual_reference_edit_not_text_only(self):
        im = Image.new('RGB', (96, 144), 'blue')
        raw = io.BytesIO(); im.save(raw, format='PNG')
        raw64 = base64.b64encode(raw.getvalue()).decode()
        calls=[]
        class Result:
            status_code = 200
            def json(self):return {'data':[{'b64_json':raw64}]}
        def fake_post(url, **kwargs):
            self.assertIn('/v1/images/edits', url)
            self.assertIn('image', kwargs['files'])
            self.assertEqual('kontext', kwargs['data']['model'])
            calls.append(kwargs['data']['prompt'])
            return Result()
        story,_,_=pilot.validate_story()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(pilot.requests, 'post', side_effect=fake_post):
                out=pilot.reference_images(story, Path(folder), 'fake-not-a-secret', 'ignored')
            self.assertEqual(10, len(out))
            self.assertTrue(all(p.exists() for p in out))
            with Image.open(out[0]) as img:
                self.assertEqual((1080,1920), img.size)
            sheet=pilot.make_contact_sheet(folder, Path(folder)/'contact.jpg')
            self.assertTrue(sheet.is_file())
        self.assertEqual(10,len(calls))
        self.assertNotEqual(calls[0], calls[1])
        self.assertTrue(all('STRICT identity' in prompt for prompt in calls))

if __name__=='__main__': unittest.main()
