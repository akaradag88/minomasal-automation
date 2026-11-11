import copy
import io
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PIL import Image,ImageDraw,ImageFont
import minomasal_asset_compositor as ac
from minomasal_asset_test_fixtures import make_fixtures


class AssetCompositorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'assets'
        self.path,self.catalog,self.scenes=make_fixtures(self.root)
        self.ocr=patch.object(ac,'scan_text',return_value={'status':'test_stub','detections':[],'logo_detection':'manual_required'})
        self.ocr.start();self.addCleanup(self.ocr.stop)
    def compose(self,scene=None,**kwargs):
        return ac.compose_scene(self.root,self.catalog,scene or self.scenes[0],test_fixtures=True,**kwargs)
    def save_catalog(self):self.path.write_text(json.dumps(self.catalog))
    def reapprove_test_record(self,record):record['approval']['reviewed_record_sha256']=ac.record_fingerprint(record)
    def rebind_test_character(self):
        profile=self.catalog['profiles']['character'];asset=self.catalog['assets']['character_front']
        asset['profile_sha256']=ac.character_profile_fingerprint(profile)
        self.reapprove_test_record(profile['reference']);self.reapprove_test_record(asset)
    def promote_test_records_for_unit_test_only(self):
        for profile in self.catalog['profiles'].values():profile['reference']['approval']['scope']='production'
        for item in [*self.catalog['assets'].values(),*self.catalog['backgrounds'].values()]:item['approval']['scope']='production'
        self.save_catalog()

    def test_same_exact_rgba_asset_is_reused_in_two_scenes(self):
        first,a=self.compose(self.scenes[0]);second,b=self.compose(self.scenes[1])
        self.assertEqual(first.size,(1080,1920));self.assertEqual(second.size,(1080,1920))
        self.assertNotEqual(first.tobytes(),second.tobytes())
        for i in (0,1):
            self.assertEqual(a['layers'][i]['transformed_rgba_sha256'],b['layers'][i]['transformed_rgba_sha256'])
            self.assertEqual(a['layers'][i]['reference_sha256'],b['layers'][i]['reference_sha256'])
        self.assertEqual(a['inventory'],{'character':1,'truck':1})
        self.assertFalse(a['production_assets_approved']);self.assertFalse(a['automation_quality_approved'])

    def test_test_assets_cannot_be_used_as_production_even_in_preview(self):
        for preview in (False,True):
            with self.subTest(preview=preview),self.assertRaisesRegex(ac.AssetError,'test_fixture_not_production_approved'):
                ac.compose_scene(self.root,self.catalog,self.scenes[0],preview=preview)

    def test_missing_asset_does_not_trigger_any_regeneration(self):
        del self.catalog['assets']['character_front']
        with self.assertRaisesRegex(ac.AssetError,'approved_asset_missing_no_regeneration'):self.compose()

    def test_pending_reference_and_asset_require_explicit_preview(self):
        self.promote_test_records_for_unit_test_only()
        self.catalog['profiles']['character']['reference']['approval']['status']='pending'
        with self.assertRaisesRegex(ac.AssetError,'asset_not_approved_no_regeneration'):
            ac.compose_scene(self.root,self.catalog,self.scenes[0])
        _,report=ac.compose_scene(self.root,self.catalog,self.scenes[0],preview=True)
        self.assertFalse(report['production_assets_approved'])

    def test_tampered_asset_and_reference_are_rejected(self):
        self.catalog['assets']['character_front']['sha256']='bad'
        with self.assertRaisesRegex(ac.AssetError,'asset_hash_mismatch'):self.compose()
        self.catalog['assets']['character_front']['sha256']=ac.digest(self.root/'character-front.png')
        self.catalog['assets']['character_front']['reference_sha256']='bad'
        with self.assertRaisesRegex(ac.AssetError,'reference_identity_mismatch'):self.compose()

    def test_paths_cannot_escape_catalog_or_fetch_url(self):
        for path in ('../outside.png','https://example.com/asset.png'):
            self.catalog['assets']['character_front']['path']=path
            with self.subTest(path=path),self.assertRaises(ac.AssetError):self.compose()

    def test_views_and_directions_require_explicit_approved_assets(self):
        self.scenes[0]['layers'][0]['view']='back'
        with self.assertRaisesRegex(ac.AssetError,'wrong_profile_or_unapproved_view'):self.compose()
        self.scenes[0]['layers'][0]['view']='front';self.scenes[0]['layers'][0]['flip_x']=True
        with self.assertRaisesRegex(ac.AssetError,'mirroring_not_approved'):self.compose()
        self.catalog['assets']['character_front']['mirror_approved']=True
        self.reapprove_test_record(self.catalog['assets']['character_front'])
        _,report=self.compose();self.assertTrue(report['layers'][0]['flip_x'])

    def test_missing_extra_and_hidden_layers_are_rejected(self):
        for layers in (self.scenes[0]['layers'][:1],self.scenes[0]['layers']+[self.scenes[0]['layers'][1]]):
            scene=copy.deepcopy(self.scenes[0]);scene['layers']=layers
            with self.subTest(count=len(layers)),self.assertRaises(ac.AssetError):self.compose(scene)
        scene=copy.deepcopy(self.scenes[0]);scene['layers'][1].update(x=160,y=950,height=480)
        with self.assertRaisesRegex(ac.AssetError,'hidden_by_layer'):self.compose(scene)

    def test_invalid_resolution_transparency_and_cut_edges_are_rejected(self):
        path=self.root/'character-front.png'
        for mode,size in (('RGB',(256,384)),('RGBA',(16,16)),('RGBA',(256,384))):
            image=Image.new(mode,size,'orange');image.save(path)
            sha=ac.digest(path);self.catalog['assets']['character_front']['sha256']=sha
            self.catalog['assets']['character_front']['reference_sha256']=sha
            self.catalog['profiles']['character']['reference']['sha256']=sha
            self.rebind_test_character()
            with self.subTest(mode=mode,size=size),self.assertRaises(ac.AssetError):self.compose()

    def test_geometry_requires_finite_ints_and_zoom_safe_bounds(self):
        for values in ({'x':0},{'y':0},{'height':9999},{'x':float('nan')},{'height':True}):
            scene=copy.deepcopy(self.scenes[0]);scene['layers'][0].update(values)
            with self.subTest(values=values),self.assertRaises(ac.AssetError):self.compose(scene)

    def test_white_fringe_and_disconnected_mask_require_manual_review(self):
        image=Image.new('RGBA',(128,128),(255,255,255,0));draw=ImageDraw.Draw(image)
        draw.rectangle((20,20,108,108),fill=(255,255,255,128));draw.rectangle((30,30,98,98),fill=(200,80,10,255))
        self.assertTrue(ac.inspect_rgba(image)['white_fringe_suspected'])
        image.save(self.root/'character-front.png');sha=ac.digest(self.root/'character-front.png')
        self.catalog['profiles']['character']['reference']['sha256']=sha
        self.catalog['assets']['character_front'].update(sha256=sha,reference_sha256=sha)
        self.rebind_test_character()
        with self.assertRaisesRegex(ac.AssetError,'white_fringe_requires_manual_review'):self.compose()

    def test_premultiplied_scaling_does_not_add_hidden_white_rgb_halos(self):
        _,report=self.compose()
        self.assertFalse(report['layers'][0]['quality']['white_fringe_suspected'])
        self.assertEqual(report['layers'][0]['quality']['significant_alpha_components'],1)

    def test_transparent_white_pixels_cannot_bleed_into_scaled_red_sprite(self):
        path=self.root/'character-front.png'
        sprite=Image.new('RGBA',(256,384),(255,255,255,0))
        ImageDraw.Draw(sprite).rectangle((50,50,200,330),fill=(255,0,0,255));sprite.save(path)
        sha=ac.digest(path);self.catalog['assets']['character_front'].update(sha256=sha,reference_sha256=sha)
        self.catalog['profiles']['character']['reference']['sha256']=sha
        self.rebind_test_character()
        bg=self.root/'background-1.png';Image.new('RGB',(1080,1920),'black').save(bg)
        self.catalog['backgrounds']['background_1']['sha256']=ac.digest(bg)
        self.reapprove_test_record(self.catalog['backgrounds']['background_1'])
        scene=copy.deepcopy(self.scenes[0]);scene['layers'][0]['height']=135
        image,report=self.compose(scene)
        x,y,w,h=report['layers'][0]['box'];roi=image.crop((x,y,x+w,y+h))
        self.assertEqual(roi.getextrema()[1][1],0);self.assertEqual(roi.getextrema()[2][1],0)

    def test_missing_manual_no_text_or_identity_check_is_not_approval(self):
        for field in ('identity','single_entity','edges','no_text_logo'):
            self.catalog['assets']['character_front']['approval']['checks'][field]=False
            with self.subTest(field=field),self.assertRaisesRegex(ac.AssetError,'manual_visual_checks_required'):self.compose()
            self.catalog['assets']['character_front']['approval']['checks'][field]=True

    def test_missing_ocr_is_reported_as_uncertain_not_automatic_pass(self):
        with patch.object(ac,'scan_text',return_value={'status':'unavailable','detections':[],'logo_detection':'manual_required'}):
            _,report=self.compose()
            self.assertEqual(report['final_ocr']['status'],'unavailable')
            self.assertTrue(report['manual_scene_review_required']);self.assertFalse(report['automation_quality_approved'])

    def test_ocr_detections_block_composition(self):
        with patch.object(ac,'scan_text',return_value={'status':'completed','detections':[{'confidence':99,'box':[1,2,3,4]}]}):
            with self.assertRaisesRegex(ac.AssetError,'unwanted_text_detected'):self.compose()

    def test_ocr_parser_redacts_words_and_reports_unavailable(self):
        tsv='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t20\t30\t80\t40\t95\tPRIVATE_WORD\n'
        self.ocr.stop()
        with patch.object(ac.shutil,'which',return_value='/fake/tesseract'),patch.object(ac.subprocess,'run',return_value=Mock(returncode=0,stdout=tsv)):
            report=ac.scan_text(Image.new('RGB',(100,100)))
            self.assertEqual(len(report['detections']),1);self.assertNotIn('PRIVATE_WORD',json.dumps(report))
        with patch.object(ac.shutil,'which',return_value=None):
            self.assertEqual(ac.scan_text(Image.new('RGB',(100,100)))['status'],'unavailable')
        self.ocr.start()

    def test_uniform_background_removal_is_pending_not_approved(self):
        source=self.root/'key.png';dest=self.root/'candidate.png'
        image=Image.new('RGB',(128,128),(0,255,0));ImageDraw.Draw(image).ellipse((30,20,100,110),fill='orange');image.save(source)
        report=ac.remove_uniform_background(source,dest,(0,255,0))
        self.assertEqual(report['approval']['status'],'pending')
        with Image.open(dest) as image:self.assertEqual(image.getchannel('A').getextrema(),(0,255))
        with self.assertRaisesRegex(ac.AssetError,'candidate_exists_no_overwrite'):
            ac.remove_uniform_background(source,dest,(0,255,0))

    def test_forest_background_is_not_silently_removed(self):
        with self.assertRaisesRegex(ac.AssetError,'nonuniform_background_requires_manual_mask'):
            ac.remove_uniform_background(self.root/'background-1.png',self.root/'bad.png',(0,255,0))

    def test_whole_batch_validation_happens_before_output(self):
        scenes=copy.deepcopy(self.scenes);scenes[1]['layers'][0]['x']=-1
        output=Path(self.tmp.name)/'frames'
        with self.assertRaises(ac.AssetError):ac.compose_story(self.path,scenes,output,test_fixtures=True)
        self.assertFalse(output.exists())

    def test_fixture_or_unreviewed_composition_cannot_enter_local_image_route(self):
        output=Path(self.tmp.name)/'frames'
        paths,manifest=ac.compose_story(self.path,self.scenes,output,test_fixtures=True)
        self.assertEqual(len(paths),2)
        with self.assertRaisesRegex(ac.AssetError,'hash_bound_manual_scene_approval'):ac.validate_local_handoff(output)
        import minomasal_images as images
        from test_minomasal_images import STORY
        with self.assertRaisesRegex(images.ImageFailure,'manuel sahne onayı'):
            images.make_images(STORY,Path(self.tmp.name)/'images','secret','flux',str(output))

    def test_final_scene_approval_is_hash_bound(self):
        self.promote_test_records_for_unit_test_only();output=Path(self.tmp.name)/'frames'
        _,manifest=ac.compose_story(self.path,self.scenes,output)
        with self.assertRaises(ac.AssetError):ac.validate_local_handoff(output)
        manifest['manual_scene_review']={'status':'approved','scope':'production','reviewed_by':'test-reviewer',
            'reviewed_at':'2026-11-11T23:00:00+03:00','checks':dict.fromkeys(('identity','counts','text_logos','scene_action'),True),
            'reviewed_output_hashes':[scene['sha256'] for scene in manifest['scenes']]}
        (output/'composition.json').write_text(json.dumps(manifest));ac.validate_local_handoff(output)
        (output/'01.jpg').write_bytes(b'changed')
        with self.assertRaises(ac.AssetError):ac.validate_local_handoff(output)

    def test_profile_and_view_metadata_changes_invalidate_approval(self):
        self.catalog['profiles']['character']['traits']['eyes']='different eye design'
        with self.assertRaisesRegex(ac.AssetError,'profile_changed_since_asset_approval'):self.compose()
        self.catalog['profiles']['character']['traits']['eyes']='synthetic test geometry only'
        self.catalog['assets']['character_front']['mirror_approved']=True
        with self.assertRaisesRegex(ac.AssetError,'record_changed_since_manual_approval'):self.compose()

    def test_uncertain_ocr_needs_manual_scene_review_not_automatic_acceptance(self):
        self.promote_test_records_for_unit_test_only()
        with patch.object(ac,'scan_text',return_value={'status':'completed','detections':[],
                'uncertain_detections':[{'confidence':67,'box':[10,20,30,40]}]}):
            output=Path(self.tmp.name)/'uncertain'
            _,manifest=ac.compose_story(self.path,self.scenes,output)
            self.assertTrue(manifest['scenes'][0]['manual_ocr_review_required'])
            with self.assertRaisesRegex(ac.AssetError,'hash_bound_manual_scene_approval'):
                ac.validate_local_handoff(output)


class RealLocalOCRTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('tesseract') and Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').exists(),
                         'Local Tesseract/font unavailable; never claim automatic text verification')
    def test_real_ocr_detects_clear_unwanted_text_without_logging_word(self):
        image=Image.new('RGB',(1000,240),'white')
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',100)
        ImageDraw.Draw(image).text((30,35),'MINOMASAL',font=font,fill='black')
        report=ac.scan_text(image)
        self.assertEqual(report['status'],'completed');self.assertTrue(report['detections'])
        self.assertNotIn('MINOMASAL',json.dumps(report))


if __name__=='__main__':unittest.main()
