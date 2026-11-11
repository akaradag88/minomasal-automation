"""Synthetic geometric proxies ONLY, not approved MinoMasal story characters."""
from datetime import datetime,timezone
import json
from pathlib import Path
from PIL import Image,ImageDraw
from minomasal_asset_compositor import digest
from minomasal_visual_profile import TRAITS


def make_fixtures(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    proxy=Image.new('RGBA',(256,384),(255,255,255,0));draw=ImageDraw.Draw(proxy)
    draw.rectangle((65,135,190,340),fill=(235,120,20,255))
    draw.ellipse((35,20,220,195),fill=(240,130,25,255))
    draw.rectangle((40,150,215,175),fill=(20,90,180,255))
    draw.ellipse((75,85,105,120),fill=(20,160,40,255));draw.ellipse((150,85,180,120),fill=(20,160,40,255))
    proxy.save(root/'character-front.png')
    truck=Image.new('RGBA',(256,160),(255,255,255,0));draw=ImageDraw.Draw(truck)
    draw.rectangle((15,35,235,120),fill=(220,25,20,255))
    draw.rectangle((20,10,80,115),fill=(230,30,20,255))
    draw.ellipse((35,95,90,145),fill=(25,30,35,255));draw.ellipse((165,95,220,145),fill=(25,30,35,255))
    truck.save(root/'truck-front.png')
    for i,color in enumerate(((48,100,70),(70,115,145)),1):
        image=Image.new('RGB',(1080,1920),color);draw=ImageDraw.Draw(image)
        draw.rectangle((0,1400,1080,1920),fill=(130+i*15,145,95))
        image.save(root/f'background-{i}.png')
    def approved(checks):
        return {'status':'approved','scope':'test-fixture','reviewed_by':'synthetic-test-fixture',
                'reviewed_at':datetime.now(timezone.utc).isoformat(),'checks':dict.fromkeys(checks,True)}
    catalog={'version':1,'profiles':{},'assets':{},'backgrounds':{}}
    for entity,kind,file in (('character','character','character-front.png'),('truck','object','truck-front.png')):
        sha=digest(root/file)
        catalog['profiles'][entity]={'kind':kind,'traits':dict.fromkeys(TRAITS[kind],'synthetic test geometry only'),
            'reference':{'path':file,'sha256':sha,'approval':approved(('identity',))}}
        catalog['assets'][entity+'_front']={'profile':entity,'view':'front','path':file,'sha256':sha,
            'reference_sha256':sha,'mirror_approved':False,
            'approval':approved(('identity','single_entity','edges','no_text_logo'))}
    for i in (1,2):
        catalog['backgrounds'][f'background_{i}']={'path':f'background-{i}.png','sha256':digest(root/f'background-{i}.png'),
            'approval':approved(('empty_scene','no_text_logo'))}
    scenes=[]
    for i in (1,2):
        scenes.append({'background':f'background_{i}','inventory':{'character':1,'truck':1},'layers':[
            {'profile':'character','asset':'character_front','view':'front','x':160 if i==1 else 560,
             'y':950,'height':480,'flip_x':False},
            {'profile':'truck','asset':'truck_front','view':'front','x':600 if i==1 else 140,
             'y':1280,'height':180,'flip_x':False}]})
    path=root/'catalog.json';path.write_text(json.dumps(catalog,indent=2)+'\n')
    (root/'scenes.json').write_text(json.dumps(scenes,indent=2)+'\n')
    return path,catalog,scenes
