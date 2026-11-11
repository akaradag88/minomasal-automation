"""Local approved-asset composition. No image generation or publishing imports.

Count verification covers explicit layers; semantic content inside a sprite or
background still requires a hash-bound manual review. No missing-asset fallback.
"""
from collections import deque
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageOps
from minomasal_visual_profile import TRAITS,text

SIZE=(1080,1920)
SAFE=(54,96,1026,1824)  # Existing renderer zoom <= 1.08 stays inside this margin.
VIEWS={'front','side','back'}


class AssetError(RuntimeError):pass


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_file(root,value):
    if not isinstance(value,str) or not value or '://' in value:raise AssetError('local_asset_path_required')
    path=(root/value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise AssetError('asset_missing_or_path_escape')
    return path


def verified_file(root,record):
    if not isinstance(record,dict):raise AssetError('invalid_asset_record')
    path=local_file(root,record.get('path'))
    expected=record.get('sha256')
    if not isinstance(expected,str) or digest(path)!=expected:raise AssetError('asset_hash_mismatch')
    return path


def approval(record,checks,*,test_fixtures=False,preview=False):
    item=record.get('approval',{})
    if not isinstance(item,dict):raise AssetError('invalid_approval')
    if item.get('scope')=='test-fixture':
        if not test_fixtures:raise AssetError('test_fixture_not_production_approved')
    elif item.get('scope')!='production':
        if preview:return False
        raise AssetError('production_approval_required')
    if item.get('status')!='approved':
        if preview:return False
        raise AssetError('asset_not_approved_no_regeneration')
    if not isinstance(item.get('reviewed_by'),str) or not item['reviewed_by'].strip():
        raise AssetError('manual_reviewer_required')
    try:datetime.fromisoformat(item['reviewed_at'])
    except (KeyError,TypeError,ValueError):raise AssetError('review_date_required') from None
    flags=item.get('checks',{})
    if not isinstance(flags,dict) or any(flags.get(check) is not True for check in checks):
        raise AssetError('manual_visual_checks_required')
    return item.get('scope')=='production'


def read_image(path,*,rgba=False):
    try:
        with Image.open(path) as source:
            if min(source.size)<32 or max(source.size)>4096 or source.width*source.height>16_000_000:
                raise AssetError('invalid_image_resolution')
            if source.format not in ('PNG','JPEG','WEBP'):raise AssetError('unsupported_image_format')
            source.verify()
        with Image.open(path) as source:
            source.load()
            if rgba and (source.format!='PNG' or source.mode!='RGBA'):
                raise AssetError('transparent_rgba_png_required')
            return ImageOps.exif_transpose(source).copy()
    except (OSError,ValueError,Image.DecompressionBombError):
        raise AssetError('corrupt_image') from None


def components(alpha):
    # A geometry/speck heuristic, not a detector of people or objects.
    small=alpha.resize((128,128),Image.Resampling.NEAREST)
    pixels=list(small.getdata());seen=set();areas=[]
    for pos,value in enumerate(pixels):
        if value<32 or pos in seen:continue
        seen.add(pos);queue=deque([pos]);area=0
        while queue:
            here=queue.popleft();area+=1;x,y=here%128,here//128
            for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                other=ny*128+nx
                if 0<=nx<128 and 0<=ny<128 and other not in seen and pixels[other]>=32:
                    seen.add(other);queue.append(other)
        if area>=max(4,128*128*.001):areas.append(area)
    return len(areas)


def inspect_rgba(image):
    if image.mode!='RGBA':raise AssetError('transparent_rgba_png_required')
    alpha=image.getchannel('A');box=alpha.getbbox()
    if box is None or alpha.getextrema()!=(0,255):raise AssetError('missing_or_invalid_transparency')
    if box[0]<2 or box[1]<2 or box[2]>image.width-2 or box[3]>image.height-2:
        raise AssetError('sprite_touches_edge_or_is_cut')
    fraction=sum(i*n for i,n in enumerate(alpha.histogram()))/(255*image.width*image.height)
    if not .005<=fraction<=.9:raise AssetError('invalid_visible_alpha_area')
    semi=white=0
    # RGB hidden under alpha=0 is intentionally ignored.
    for r,g,b,a in image.getdata():
        if 8<a<240:
            semi+=1
            if min(r,g,b)>235:white+=1
    return {'alpha_bbox':list(box),'alpha_fraction':round(fraction,5),
            'significant_alpha_components':components(alpha),
            'white_fringe_suspected':white>=8 and white/max(1,semi)>.35}


def scan_text(image):
    """Optional local OCR. Do not log recognized strings or raw tool errors."""
    executable=shutil.which('tesseract')
    if not executable:return {'status':'unavailable','detections':[],'logo_detection':'manual_required'}
    try:
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.png'
            if image.mode=='RGBA':
                visible=Image.new('RGBA',image.size,(127,127,127,255));visible.alpha_composite(image)
                visible.convert('RGB').save(path)
            else:image.convert('RGB').save(path)
            result=subprocess.run([executable,str(path),'stdout','--psm','11','tsv'],
                capture_output=True,text=True,timeout=20,check=False)
        if result.returncode:return {'status':'failed','detections':[],'logo_detection':'manual_required'}
        boxes=[]
        for line in result.stdout.splitlines()[1:]:
            cells=line.split('\t')
            if len(cells)!=12:continue
            confidence=float(cells[10]);word=cells[11].strip()
            if confidence>=60 and sum(c.isalnum() for c in word)>=2:
                boxes.append({'confidence':round(confidence,1),'box':[int(c) for c in cells[6:10]]})
        return {'status':'completed','detections':boxes,'logo_detection':'manual_required'}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {'status':'failed','detections':[],'logo_detection':'manual_required'}


def require_no_text(image,enabled):
    report=scan_text(image) if enabled else {'status':'not_run','detections':[],'logo_detection':'manual_required'}
    if report['detections']:raise AssetError('unwanted_text_detected')
    return report


def sprite(root,catalog,asset_id,*,test_fixtures,preview,ocr):
    asset=catalog.get('assets',{}).get(asset_id)
    if not isinstance(asset,dict):raise AssetError('approved_asset_missing_no_regeneration')
    if not isinstance(asset.get('profile'),str):raise AssetError('invalid_asset_profile_id')
    profile=catalog.get('profiles',{}).get(asset.get('profile'))
    if not isinstance(profile,dict):raise AssetError('character_profile_missing')
    kind=profile.get('kind');traits=profile.get('traits')
    if (not isinstance(kind,str) or kind not in TRAITS or not isinstance(traits,dict)
            or set(traits)!=set(TRAITS[kind]) or not all(text(value) for value in traits.values())):
        raise AssetError('physical_character_or_object_profile_required')
    reference=profile.get('reference',{})
    read_image(verified_file(root,reference))
    ref_ok=approval(reference,('identity',),test_fixtures=test_fixtures,preview=preview)
    if asset.get('reference_sha256')!=reference['sha256']:raise AssetError('reference_identity_mismatch')
    path=verified_file(root,asset)
    approved=approval(asset,('identity','single_entity','edges','no_text_logo'),test_fixtures=test_fixtures,preview=preview)
    if asset.get('view') not in VIEWS:raise AssetError('approved_view_required')
    image=read_image(path,rgba=True);qc=inspect_rgba(image)
    flags=asset.get('approval',{}).get('checks',{})
    if qc['white_fringe_suspected'] and flags.get('white_fringe_reviewed') is not True:
        raise AssetError('white_fringe_requires_manual_review')
    if qc['significant_alpha_components']>1 and flags.get('disconnected_parts_reviewed') is not True:
        raise AssetError('disconnected_parts_require_manual_review')
    qc['ocr']=require_no_text(image,ocr)
    return asset,image,qc,approved and ref_ok


def mass(alpha):return sum(i*n for i,n in enumerate(alpha.histogram()))


def compose_scene(root,catalog,scene,*,test_fixtures=False,preview=False,ocr=True):
    if not isinstance(scene,dict) or set(scene)!={'background','inventory','layers'}:
        raise AssetError('invalid_scene_plan')
    if not isinstance(scene['background'],str):raise AssetError('invalid_background_id')
    if any(not isinstance(catalog.get(key),dict) for key in ('profiles','assets','backgrounds')):
        raise AssetError('invalid_catalog_maps')
    inventory=scene['inventory'];layers=scene['layers']
    if (not isinstance(inventory,dict) or not inventory or len(inventory)>8
            or any(not isinstance(k,str) for k in inventory)
            or any(type(n) is not int or not 0<=n<=4 for n in inventory.values())
            or not isinstance(layers,list) or not 1<=len(layers)<=8):
        raise AssetError('invalid_scene_inventory')
    bg=catalog.get('backgrounds',{}).get(scene['background'])
    path=verified_file(root,bg)
    bg_ok=approval(bg,('empty_scene','no_text_logo'),test_fixtures=test_fixtures,preview=preview)
    background=read_image(path)
    if min(background.size)<512:raise AssetError('background_resolution_too_small')
    if background.mode=='RGBA' and background.getchannel('A').getextrema()!=(255,255):
        raise AssetError('opaque_background_required')
    bg_ocr=require_no_text(background,ocr)
    canvas=ImageOps.fit(background.convert('RGB'),SIZE,method=Image.Resampling.LANCZOS).convert('RGBA')
    actual={key:0 for key in inventory};items=[];masks=[];all_approved=bg_ok
    for layer in layers:
        if not isinstance(layer,dict) or set(layer)!={'profile','asset','view','x','y','height','flip_x'}:
            raise AssetError('invalid_layer_transform')
        if any(not isinstance(layer[k],str) for k in ('profile','asset','view')):
            raise AssetError('invalid_layer_identifiers')
        entity=layer['profile']
        if entity not in actual:raise AssetError('unexpected_scene_entity')
        actual[entity]+=1
        asset,image,qc,approved=sprite(root,catalog,layer['asset'],test_fixtures=test_fixtures,preview=preview,ocr=ocr)
        if asset['profile']!=entity or asset['view']!=layer['view']:
            raise AssetError('wrong_profile_or_unapproved_view')
        if type(layer['flip_x']) is not bool:raise AssetError('invalid_direction')
        if layer['flip_x']:
            if asset.get('mirror_approved') is not True:raise AssetError('mirroring_not_approved')
            image=ImageOps.mirror(image)
        if any(type(layer[k]) is not int for k in ('x','y','height')) or not 32<=layer['height']<=1728:
            raise AssetError('invalid_layer_geometry')
        scale=layer['height']/image.height
        if scale>3:raise AssetError('sprite_upscale_too_large')
        width=round(image.width*scale);height=layer['height'];x=layer['x'];y=layer['y']
        if width<16:raise AssetError('sprite_too_thin_after_scaling')
        if not (SAFE[0]<=x and SAFE[1]<=y and x+width<=SAFE[2] and y+height<=SAFE[3]):
            raise AssetError('layer_outside_zoom_safe_frame')
        # Premultiplied-alpha interpolation suppresses white/black halos from
        # hidden RGB data. Never stretch x/y independently or trim the sprite.
        transformed=image.convert('RGBa').resize((width,height),Image.Resampling.LANCZOS).convert('RGBA')
        mask=Image.new('L',SIZE,0);mask.paste(transformed.getchannel('A'),(x,y));masks.append(mask)
        canvas.alpha_composite(transformed,(x,y));all_approved=all_approved and approved
        items.append({'profile':entity,'asset':layer['asset'],'view':asset['view'],
            'asset_sha256':asset['sha256'],'reference_sha256':asset['reference_sha256'],
            'transformed_rgba_sha256':hashlib.sha256(transformed.tobytes()).hexdigest(),
            'box':[x,y,width,height],'flip_x':layer['flip_x'],'quality':qc})
    if actual!=inventory:raise AssetError('scene_layer_count_mismatch')
    for i,mask in enumerate(masks):
        visible=mask.copy()
        for occluder in masks[i+1:]:visible=ImageChops.multiply(visible,ImageChops.invert(occluder))
        ratio=mass(visible)/max(1,mass(mask));items[i]['visible_fraction']=round(ratio,4)
        if ratio<.85:raise AssetError('character_or_object_hidden_by_layer')
    final_ocr=require_no_text(canvas,ocr)
    report={'inventory':actual,'layer_counts_verified':True,'background_ocr':bg_ocr,'layers':items,
        'final_ocr':final_ocr,'production_assets_approved':all_approved,
        'semantic_counts_basis':'manual single-entity/empty-background approvals plus explicit layers',
        'manual_scene_review_required':True,'automation_quality_approved':False,
        'test_fixture_only':test_fixtures,'preview':preview,'output_size':list(SIZE)}
    return canvas.convert('RGB'),report


def compose_story(catalog_path,scenes,output,*,test_fixtures=False,preview=False,ocr=True):
    catalog_path=Path(catalog_path);root=catalog_path.parent.resolve()
    try:catalog=json.loads(catalog_path.read_text())
    except (OSError,ValueError):raise AssetError('catalog_missing_or_invalid') from None
    if not isinstance(catalog,dict) or catalog.get('version')!=1:raise AssetError('invalid_catalog_version')
    if not isinstance(scenes,list) or not 1<=len(scenes)<=20:raise AssetError('invalid_scene_count')
    output=Path(output)
    if output.exists():raise AssetError('output_exists_no_overwrite')
    frames=[];reports=[]
    for scene in scenes:
        image,report=compose_scene(root,catalog,scene,test_fixtures=test_fixtures,preview=preview,ocr=ocr)
        buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=95)
        frames.append(buffer.getvalue());reports.append(report)
    # No partial successful batch is exposed on validation failure.
    output.mkdir(parents=True)
    paths=[]
    for i,data in enumerate(frames,1):
        path=output/f'{i:02}.jpg';path.write_bytes(data);paths.append(path)
        reports[i-1]['sha256']=digest(path)
    manifest={'version':1,'scenes':reports,'source_catalog_sha256':digest(catalog_path),
              'automation_quality_approved':False,'manual_scene_review_required':True}
    (output/'composition.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return paths,manifest


def remove_uniform_background(source,destination,key_rgb,tolerance=12):
    """Conservative border-connected chroma key. No general forest segmentation.

    Result is ALWAYS a pending-review candidate, never an approved asset.
    """
    if (not isinstance(key_rgb,(tuple,list)) or len(key_rgb)!=3
            or any(type(v) is not int or not 0<=v<=255 for v in key_rgb)
            or type(tolerance) is not int or not 0<=tolerance<=24):raise AssetError('invalid_chroma_key')
    image=read_image(Path(source)).convert('RGB')
    difference=ImageChops.difference(image,Image.new('RGB',image.size,tuple(key_rgb)))
    r,g,b=difference.split();distance=ImageChops.lighter(ImageChops.lighter(r,g),b)
    eligible=distance.point(lambda value:255 if value<=tolerance else 0)
    border=list(eligible.crop((0,0,image.width,1)).getdata())+list(eligible.crop((0,image.height-1,image.width,image.height)).getdata())
    border+=list(eligible.crop((0,0,1,image.height)).getdata())+list(eligible.crop((image.width-1,0,image.width,image.height)).getdata())
    if sum(v==255 for v in border)/len(border)<.98:
        raise AssetError('nonuniform_background_requires_manual_mask')
    flood=eligible.copy()
    for x in range(image.width):
        for y in (0,image.height-1):
            if flood.getpixel((x,y))==255:ImageDraw.floodfill(flood,(x,y),128)
    for y in range(image.height):
        for x in (0,image.width-1):
            if flood.getpixel((x,y))==255:ImageDraw.floodfill(flood,(x,y),128)
    alpha=flood.point(lambda value:0 if value==128 else 255)
    rgba=image.convert('RGBA');rgba.putalpha(alpha);qc=inspect_rgba(rgba)
    if qc['significant_alpha_components']>1:raise AssetError('removal_fragmented_subject')
    destination=Path(destination)
    if destination.exists():raise AssetError('candidate_exists_no_overwrite')
    rgba.save(destination,format='PNG')
    report={'source_sha256':digest(source),'candidate_sha256':digest(destination),'quality':qc,
        'method':'uniform_border_connected_chroma_key','approval':{'status':'pending'},
        'manual_review_required':['identity','lost_fur_or_parts','white_edges','text_logos','mask_quality']}
    destination.with_suffix('.review.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def validate_local_handoff(folder):
    """A preview/test fixture must never enter the existing local-image route."""
    folder=Path(folder);path=folder/'composition.json'
    if not path.exists():return  # Preserve ordinary existing local-image input.
    try:
        manifest=json.loads(path.read_text());scenes=manifest['scenes'];review=manifest['manual_scene_review']
        if not isinstance(scenes,list) or not scenes:raise ValueError()
        if any(not isinstance(scene,dict) for scene in scenes):raise ValueError()
        if any(scene.get('production_assets_approved') is not True or scene.get('preview') is not False
               or scene.get('test_fixture_only') is not False for scene in scenes):raise ValueError()
        approval({'approval':review},('identity','counts','text_logos','scene_action'))
        hashes=[digest(folder/f'{i:02}.jpg') for i in range(1,len(scenes)+1)]
        if any(read_image(folder/f'{i:02}.jpg').size!=SIZE for i in range(1,len(scenes)+1)):
            raise AssetError('wrong_composition_resolution')
        if hashes!=review['reviewed_output_hashes'] or hashes!=[s['sha256'] for s in scenes]:raise ValueError()
    except (OSError,KeyError,ValueError,TypeError,AssetError):
        raise AssetError('composition_requires_hash_bound_manual_scene_approval') from None


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    compose=commands.add_parser('compose')
    compose.add_argument('--catalog',required=True);compose.add_argument('--scenes',required=True)
    compose.add_argument('--output',required=True);compose.add_argument('--preview',action='store_true')
    remove=commands.add_parser('remove-uniform-background')
    remove.add_argument('--source',required=True);remove.add_argument('--output',required=True)
    remove.add_argument('--key-rgb',required=True,help='Known uniform key, e.g. 0,255,0')
    args=parser.parse_args()
    try:
        if args.command=='compose':
            scenes=json.loads(Path(args.scenes).read_text())
            _,manifest=compose_story(args.catalog,scenes,args.output,preview=args.preview)
            print(json.dumps({'scenes':len(manifest['scenes']),'automation_quality_approved':False,
                              'manual_scene_review_required':True}))
        else:
            key=[int(value) for value in args.key_rgb.split(',')]
            remove_uniform_background(args.source,args.output,key)
            print('Candidate saved; manual mask/identity approval required.')
    except (AssetError,OSError,ValueError):
        raise SystemExit('Asset validation failed; no regeneration or publishing performed.') from None


if __name__=='__main__':main()
