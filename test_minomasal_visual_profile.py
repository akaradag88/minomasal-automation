"""Offline intentions/framing tests; no claim to detect objects, text or identity."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import minomasal_images as images
import minomasal_cloudflare_quality_test as probe
from minomasal_visual_profile import build_prompt,identity_text,profile_digest,review_contract


class VisualProfileTests(unittest.TestCase):
    def setUp(self):self.plan=copy.deepcopy(probe.PLAN)

    def test_two_scenes_use_identical_identity_and_explicit_one_one_inventory(self):
        profile=self.plan['profile'];identity=identity_text(profile)
        for scene in self.plan['scenes']:
            prompt=build_prompt(profile,scene)
            self.assertIn(identity,prompt)
            self.assertIn('1 small fox cub, 1 toy truck',prompt)
            self.assertNotIn('Mino',prompt)  # Do not encourage model to print a name.
            self.assertLessEqual(len(prompt),2048)
            self.assertEqual(scene['inventory'],{'fox':1,'truck':1})

    def test_omitted_duplicate_boolean_and_unknown_inventory_are_rejected(self):
        for inventory in (None,{'fox':1},{'fox':1,'truck':2},{'fox':True,'truck':1},
                          {'fox':1,'truck':1,'extra':1},{'fox':0,'truck':0}):
            with self.subTest(inventory=inventory),self.assertRaises(ValueError):
                build_prompt(self.plan['profile'],{'action':'A forest scene.','inventory':inventory})

    def test_all_physical_traits_are_required(self):
        for entity,field in (('fox','eyes'),('fox','clothing'),('fox','face'),
                             ('fox','proportions'),('fox','accessories'),('truck','parts')):
            plan=copy.deepcopy(self.plan);del plan['profile']['entities'][entity]['traits'][field]
            with self.subTest(entity=entity,field=field),self.assertRaises(ValueError):
                build_prompt(plan['profile'],plan['scenes'][0])

    def test_malformed_profile_types_do_not_escape_validation(self):
        for field,value in (('kind',[]),('max_count',True),('traits',None)):
            plan=copy.deepcopy(self.plan);plan['profile']['entities']['fox'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                build_prompt(plan['profile'],plan['scenes'][0])

    def test_profile_digest_and_prompt_are_stable_under_key_reordering(self):
        original=self.plan['profile'];reordered=json.loads(json.dumps(original,sort_keys=True))
        self.assertEqual(profile_digest(original),profile_digest(reordered))
        self.assertEqual(build_prompt(original,self.plan['scenes'][0]),build_prompt(reordered,self.plan['scenes'][0]))

    def test_oversize_prompt_fails_instead_of_truncating_identity(self):
        self.plan['profile']['composition']='x'*800
        self.plan['profile']['exclusions']='y'*800
        with self.assertRaisesRegex(ValueError,'visual_prompt_exceeds_model_limit'):
            build_prompt(self.plan['profile'],self.plan['scenes'][0])

    def test_semantic_review_is_explicitly_required(self):
        contract=review_contract()
        self.assertFalse(contract['semantic_checks_automated'])
        self.assertFalse(contract['automation_quality_approved'])
        for field in ('actual_entity_counts','character_identity','unwanted_text_logos_watermarks'):
            self.assertIn(field,contract['human_review_required'])
        self.assertEqual(images.load_config()['approved_for_automation'],[])

    def test_invalid_plan_blocks_metadata_and_inference(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(probe,'PLAN',self.plan),patch.object(probe,'http') as http,patch.object(probe.Cloudflare,'generate') as gen:
            self.plan['scenes'][1]['inventory']['truck']=2
            report=probe.run_check(Path(tmp)/'out',True)
            self.assertEqual(report['status'],'blocked_no_publish')
            http.assert_not_called();gen.assert_not_called()

    def test_source_corners_survive_contain_output(self):
        picture=Image.new('RGB',(640,640))
        for color,box in (('red',(0,0,320,320)),('green',(320,0,640,320)),
                          ('blue',(0,320,320,640)),('yellow',(320,320,640,640))):
            picture.paste(color,box)
        data=io.BytesIO();picture.save(data,format='PNG')
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'out.jpg'
            self.assertEqual(images.normalize(data.getvalue(),dest,framing='contain'),[640,640])
            with Image.open(dest) as output:
                self.assertEqual(output.size,(1080,1920))
                for point,expected in (((30,450),(255,0,0)),((1050,450),(0,128,0)),
                                       ((30,1470),(0,0,255)),((1050,1470),(255,255,0)),
                                       ((500,20),(24,45,38))):
                    self.assertLess(max(abs(a-b) for a,b in zip(output.getpixel(point),expected)),10)

    def test_contain_geometry_is_bounded_and_preserves_aspect(self):
        for size in ((1024,1024),(512,2048),(2048,512),(1080,1920)):
            left,top,width,height=images.contain_box(size)
            self.assertGreaterEqual(left,0);self.assertGreaterEqual(top,0)
            self.assertLessEqual(left+width,1080);self.assertLessEqual(top+height,1920)
            self.assertAlmostEqual(width/height,size[0]/size[1],delta=.005)
        self.assertEqual(images.contain_box((1024,1024)),[0,420,1080,1080])

    def test_unknown_framing_rejected_before_file_write(self):
        with self.assertRaises(images.ImageFailure):images.normalize(b'bad',Path('never-created.jpg'),framing='unknown')


if __name__=='__main__':unittest.main()
