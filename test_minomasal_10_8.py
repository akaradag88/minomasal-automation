"""Offline safety regressions: no production APIs or publication."""
import asyncio
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import minomasal as mm
import minomasal_images as image_pipeline
import os
import minomasal_dual_publish as pub
import minomasal_yayin_guvenligi as safety
from minomasal_daily_live import choose

STORY = {'title': 'Test', 'characters': 'Fox', 'scenes':
         [{'narration': 'Merhaba orman.', 'visual': 'A fox'} for _ in range(6)]}


class SafetyTests(unittest.TestCase):
    def setUp(self):
        # Test transport errors independently from production free-budget policy.
        config=image_pipeline.load_config();config['approved_for_automation']=['pollinations'];config['order']=['pollinations']
        policy=patch.object(image_pipeline,'load_config',return_value=config)
        policy.start();self.addCleanup(policy.stop)
        env=patch.dict(os.environ, {'MINOMASAL_IMAGE_PROVIDERS':'pollinations'})
        env.start(); self.addCleanup(env.stop)
        preflight=patch.object(image_pipeline.Pollinations, 'preflight')
        preflight.start(); self.addCleanup(preflight.stop)

    def test_http_errors(self):
        for status, calls in [(402, 1), (429, 3), (500, 3), (401, 1)]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                with patch.object(mm.requests, 'request', return_value=Mock(status_code=status)) as get, patch.object(mm.time, 'sleep') as sleep:
                    with self.assertRaises(RuntimeError) as err:
                        mm.make_images(STORY, Path(tmp), 'SECRET', 'flux')
                    self.assertNotIn('SECRET', str(err.exception))
                    self.assertEqual(get.call_count, calls)
                    self.assertEqual([c.args[0] for c in sleep.call_args_list], [3, 6] if calls == 3 else [])

    def test_transient_recovery(self):
        from PIL import Image
        data = io.BytesIO(); Image.effect_noise((512,512),80).convert('RGB').save(data, format='PNG')
        with tempfile.TemporaryDirectory() as tmp, patch.object(mm.time, 'sleep'), patch.object(mm.requests, 'request', side_effect=[Mock(status_code=429), Mock(status_code=500)] + [Mock(status_code=200, content=data.getvalue()) for _ in range(6)]):
            self.assertEqual(len(mm.make_images(STORY, Path(tmp), 'secret', 'flux')), 6)

    def test_missing_image_and_audio_stop_before_render(self):
        for images, audios in [([], []), ([Path('missing')] * 6, [])]:
            with patch.object(mm.subprocess, 'run') as run:
                with self.assertRaises(RuntimeError):
                    mm.render(STORY, images, audios, Path('.'))
                run.assert_not_called()

    def test_sequence_and_skip(self):
        ledger = json.loads(Path('minomasal_platform_durumu.json').read_text())
        self.assertEqual(ledger['stories']['45']['status'], 'skipped')
        self.assertEqual(ledger['stories']['46']['status'], 'skipped')
        self.assertEqual(choose(ledger), 47)
        broken = copy.deepcopy(ledger); broken['stories']['44']['youtube']['status'] = 'ambiguous'
        with self.assertRaises(RuntimeError): choose(broken)
        for n in (45, 46):
            with self.assertRaises(RuntimeError): safety.ensure_allowed_topic(mm.KONULAR[n-1])

    def test_publisher_rejects_missing_evidence_and_skipped(self):
        for number in (45, 46, 47):
            with tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                (stage/'metadata.json').write_text(json.dumps({'number':number, 'topic':mm.KONULAR[number-1], 'title':'Test'}))
                (stage/'masal_short.mp4').write_bytes(b'invalid')
                with patch('sys.argv', ['publish', '--number', str(number), '--stage', tmp]), patch.object(pub, 'duration', return_value=2), patch.object(pub, 'upload_youtube') as upload, patch.object(pub, 'graph') as graph:
                    with self.assertRaises((RuntimeError, FileNotFoundError)): pub.main()
                    upload.assert_not_called(); graph.assert_not_called()

    def test_receipt_detects_missing_asset_and_changed_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); video=root/'test.mp4'; video.write_bytes(b'video')
            asset=root/'image.jpg'; asset.write_bytes(b'image')
            safety.receipt_path(video).write_text(json.dumps({'video_sha256':safety.digest(video), 'assets':[{'path':'image.jpg','sha256':safety.digest(asset)}]}))
            asset.unlink()
            with self.assertRaises(FileNotFoundError): safety.validate_receipt(video)
            video.write_bytes(b'changed')
            with self.assertRaises(RuntimeError): safety.validate_receipt(video)

    def test_number_jump_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)
            (stage/'metadata.json').write_text(json.dumps({'number':48,'topic':mm.KONULAR[47],'title':'test'}))
            (stage/'masal_short.mp4').write_bytes(b'video')
            with patch('sys.argv',['pub','--number','48','--stage',tmp]), patch.object(pub,'duration',return_value=2), patch.object(safety,'validate_receipt'), patch.object(pub,'upload_youtube') as upload:
                with self.assertRaisesRegex(RuntimeError, 'sırası'): pub.main()
                upload.assert_not_called()

    def test_broken_scene(self):
        broken=copy.deepcopy(STORY); broken['scenes'][2]['visual']=''
        with self.assertRaises(ValueError): mm.validate(broken)

    def test_successful_receipt_can_move_and_missing_image_blocks_publish(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; source.mkdir(); stage=root/'stage'; stage.mkdir()
            video=source/'masal_short.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=16x16:rate=1','-f','lavfi','-i','anullsrc','-t','2','-c:v','libx264','-c:a','aac',str(video)], check=True)
            image=source/'image.jpg'; Image.new('RGB',(2,2)).save(image)
            audio=source/'audio.wav'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','anullsrc','-t','0.2',str(audio)],check=True)
            (source/'hikaye.json').write_text(json.dumps(STORY))
            safety.write_receipt(video,STORY,[image]*6,[(audio,0.2,[])]*6)
            target=stage/video.name; target.write_bytes(video.read_bytes())
            safety.copy_receipt(video,target); safety.validate_receipt(target)
            receipt=json.loads(safety.receipt_path(target).read_text())
            (stage/receipt['assets'][1]['path']).unlink()
            (stage/'metadata.json').write_text(json.dumps({'number':47,'topic':mm.KONULAR[46],'title':'test'}))
            with patch('sys.argv',['pub','--number','47','--stage',str(stage)]), patch.object(pub,'upload_youtube') as upload:
                with self.assertRaises((RuntimeError,FileNotFoundError)): pub.main()
                upload.assert_not_called()

    def test_invalid_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.mp4'; p.write_bytes(b'broken')
            with self.assertRaises(RuntimeError): safety.validate_video(p)

    def test_duplicate_published_no_external_calls(self):
        ledger=json.loads(Path('minomasal_platform_durumu.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); n=44
            (p/'metadata.json').write_text(json.dumps({'number':n,'topic':mm.KONULAR[n-1],'title':'test'})); (p/'masal_short.mp4').write_bytes(b'video')
            with patch('sys.argv',['pub','--number','44','--stage',tmp]), patch.object(pub,'duration',return_value=2), patch.object(safety,'validate_receipt'), patch.dict('os.environ',{'PUBLISH_ENABLED':'true'}), patch.object(pub,'upload_youtube') as upload, patch.object(pub,'graph') as graph:
                pub.main(); upload.assert_not_called(); graph.assert_not_called()


if __name__ == '__main__': unittest.main()
