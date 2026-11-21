"""MinoMasal2 / Adım 8.8 — #33 yalnızca sorunlu görsel sahnelerin revizyonu.

* Onaylı JSON hikâyesi (hash) değişmez.
* 8.6 başarılı testindeki MP4 sesini ve SRT zamanlamasını kullanır.
* Sadece 4, 5, 6, 8, 10. sahneleri yeni resimlerle değiştirir.
* 1, 2, 3, 7, 9. sahnelerdeki orijinal görüntüler korunur.
* Instagram/YouTube/Facebook'a asla yayın yapmaz; defter dosyası değiştirmez.

Kullanım: python minomasal_33_sahne_revizyonu.py --source original
Opsiyon: --images-dir düzeltilmiş resimler klasörü (04.jpg 05.jpg 06.jpg 08.jpg 10.jpg).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import quote

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests

APPROVED_JSON = Path('minomasal_29ekim_onayli/hikaye_01.json').resolve()
APPROVED_SHA256 = '8b95189bffdf4f0b0f30368b234f62ec5d431bd4686809cb32a61f38713f3d3d'
PORTRAIT = Path('minomasal_33_assets/ataturk_onayli_portre.png').resolve()
OUTPUT = Path('minomasal_33_revize').resolve()
FPS = 24
SIZE = (1080, 1920)
SCENES = (4, 5, 6, 8, 10)
CAST = {
    'squirrel': 'Exactly one small russet squirrel with a fluffy curled tail, a cream-colored chest, bright brown eyes, no scarf and no clothes.',
    'rabbit': 'Exactly one light-brown rabbit with two long white-tipped ears, warm brown eyes, and ONE plain BLUE scarf.',
    'owl': 'Exactly one tawny BROWN OWL with a short beak, rounded feather-covered body, two WINGS, big golden eyes, and one GREEN vest. This is an OWL, not a rabbit.',
}
CAST_BY_SCENE = {
    4: ('owl', 'squirrel', 'rabbit'),
    5: ('owl', 'squirrel', 'rabbit'),
    6: ('owl', 'squirrel', 'rabbit'),
    8: ('owl', 'squirrel', 'rabbit'),
    10: ('squirrel', 'rabbit'),
}
SCENE_ACTION = {
    4: ('A friendly OWL TEACHER is addressing a squirrel and a rabbit in a cozy forest classroom. '
        'The owl is clearly visible and has no long ears. The rabbit has long ears and a blue scarf.'),
    5: ('The BROWN OWL TEACHER teaches a russet squirrel and ONE light-brown rabbit about a historical book in a wooden forest classroom. '
        'An empty clear wall behind them, with space reserved at UPPER LEFT for a framed historical portrait '
        'and at UPPER RIGHT for a Turkish flag that will be added in post production. '
        'DO NOT draw any flag, any emblem, any sign or any human. Focus on the owl explaining and two pupils listening.'),
    6: ('A thoughtful forest classroom discussion. Brown owl teacher speaking; one russet squirrel listening; '
        'ONE light-brown rabbit with a blue scarf listening. Exactly THREE animals.'),
    8: ('The forest school garden being decorated with colorful paper garlands. The brown owl teacher carefully '
        'raises a flag pole as ONE russet squirrel and ONE light-brown rabbit help. '
        'Leave clear space at UPPER RIGHT for one Turkish flag added in post-production. '
        'DO NOT draw any flag, emblem, banner, or extra animal.'),
    10: ('FINAL HERO SHOT: ONE russet squirrel with its large curly squirrel tail and cream chest; '
         'ONE light-brown rabbit wearing a single BLUE scarf. Both cheerful in the decorated forest garden, '
         'looking toward the audience. No other characters in foreground OR background.'),
}


def run(cmd, **kwargs):
    p = subprocess.run([str(x) for x in cmd], capture_output=True, text=True, **kwargs)
    if p.returncode:
        raise RuntimeError(f"Komut başarısız ({p.returncode}): {' '.join(map(str, cmd[:5]))}\n{p.stderr[-2400:]}")
    return p.stdout.strip()


def duration(path):
    return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',path]))


def _ffprobe_json(path):
    return json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',path]))


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_story(source_dir):
    if _sha256(APPROVED_JSON) != APPROVED_SHA256:
        raise RuntimeError('Onaylanmış 33. hikâye değişmiş! Kod durduruldu.')
    approved = json.loads(APPROVED_JSON.read_text(encoding='utf-8'))
    if len(approved.get('scenes', [])) != 10:
        raise RuntimeError('10 sahne bekleniyordu.')
    recorded = json.loads((source_dir / 'hikaye_33_onayli.json').read_text(encoding='utf-8'))
    if recorded != approved:
        raise RuntimeError('Önceki başarılı videonun hikâyesi onaylı hikâye ile uyuşmuyor.')
    if not (source_dir / 'altyazi_33.srt').is_file():
        raise RuntimeError('Eski video artifact içindeki altyazi_33.srt bulunamadı.')
    if not (source_dir / 'masal_33_onizleme.mp4').is_file():
        raise RuntimeError('Eski video artifact içindeki masal_33_onizleme.mp4 bulunamadı.')
    return approved


def detect_scene_edges(video):
    """Eski videodaki kararma/geçiş noktalarını otomatik bulur; sayı yanlışsa durur."""
    sample_fps=12
    raw = subprocess.run([
        'ffmpeg','-v','error','-i',str(video),'-vf',f'fps={sample_fps},scale=24:42',
        '-pix_fmt','rgb24','-f','rawvideo','-'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    stride = 24 * 42 * 3
    if len(raw) < stride*100 or len(raw) % stride:
        raise RuntimeError('Video kareleri okunamadı.')
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1,42,24,3)
    change = np.abs(np.diff(frames.astype(np.float32), axis=0)).mean(axis=(1,2,3))
    length = duration(video)
    candidates = sorted(
        [((i+1)/sample_fps, float(val)) for i,val in enumerate(change)
         if val > 27 and 2.0 < (i+1)/sample_fps < length-2.0],
        key=lambda item: item[0]
    )
    groups=[]
    for point in candidates:
        if not groups or point[0] - groups[-1][-1][0] > 0.85:
            groups.append([point])
        else:
            groups[-1].append(point)
    cuts = sorted(max(group, key=lambda item: item[1])[0] for group in groups)
    if len(cuts) != 9:
        raise RuntimeError(f'Güvenli durdurma: 9 sahne geçişi yerine {len(cuts)} tespit edildi: {cuts}')
    # Quantize to original 24 FPS frame grid, ensuring clips concatenate exactly.
    video_stream = next(s for s in _ffprobe_json(video)['streams'] if s.get('codec_type')=='video')
    n_frames = int(video_stream['nb_frames']) if video_stream.get('nb_frames') else int(round(float(video_stream['duration'])*FPS))
    edges = [0] + [round(x*FPS) for x in cuts] + [n_frames]
    gaps = [(edges[i+1]-edges[i])/FPS for i in range(10)]
    if any(not (3.5 <= gap <= 12.0) for gap in gaps):
        raise RuntimeError(f'Sahne süreleri beklenmedik: {gaps}')
    print('Orijinal sahne aralıkları:', [(round(edges[i]/FPS,2), round(edges[i+1]/FPS,2)) for i in range(10)])
    return edges


def _get_image(prompt, filename, api_key, seed):
    if not api_key:
        raise RuntimeError('Görsel üretimi için POLLINATIONS_API_KEY GitHub Secret eksik.')
    last_exc = None
    for attempt in range(3):
        try:
            r=requests.get(
                'https://gen.pollinations.ai/image/' + quote(prompt,safe=''),
                params={'model':'flux','width':1080,'height':1920,'seed':seed,'nologo':'true'},
                headers={'Authorization':'Bearer '+api_key}, timeout=180,
            )
            r.raise_for_status()
            im=Image.open(io.BytesIO(r.content)).convert('RGB')
            im=ImageOps.fit(im,SIZE,method=Image.Resampling.LANCZOS)
            im.save(filename,quality=95)
            return
        except Exception as ex:
            last_exc = ex
            print(f'Görsel denemesi {attempt+1} hata: {str(ex)[:180]}')
            if attempt < 2: time.sleep(4*(attempt+1))
    raise RuntimeError(f'Görsel oluşturulamadı: {last_exc}')


def make_prompt(scene_num):
    actors = CAST_BY_SCENE[scene_num]
    character_descriptions = ' '.join(CAST[actor] for actor in actors)
    return (
      'Beautiful detailed storybook 3D CGI animation still. '
      + f'EXACTLY {len(actors)} visible animals total, not more. '
      + character_descriptions
      + ' CRITICAL: ' + SCENE_ACTION[scene_num]
      + ' NO humans, NO kids, NO extra animals, NO background bystanders, '
        'NO duplicate rabbits, NO rabbit replacing owl, NO duplicate animal heads, '
        'NO printed words, NO watermarks, NO imaginary flags. '
        'Animals must retain same colors, anatomies, face types and clothing between scenes. '
        'Green enchanted forest school, warm natural lighting, vivid yet tasteful color, '
        'vertical 9:16, characters within central 70 percent with clear silhouettes. '
        'Composition should match the exact scene action.'
    )


def _star_points(cx,cy,ro,ri):
    return [
        (cx + (ro if j%2==0 else ri) * math.cos(-math.pi/2+j*math.pi/5),
         cy + (ro if j%2==0 else ri) * math.sin(-math.pi/2+j*math.pi/5))
        for j in range(10)
    ]


def official_flag_image(width=390):
    """Draw a deterministic red/white crescent and five-pointed star (not model-generated)."""
    h=int(width/1.5)
    ss=3; w=width*ss; H=h*ss
    flag=Image.new('RGBA',(w,H),(227,10,23,255))
    d=ImageDraw.Draw(flag)
    # Construct crescent as difference of two filled discs.
    cx,cy=int(0.52*H),int(0.50*H)
    ro,ri=int(0.25*H),int(0.20*H)
    d.ellipse((cx-ro,cy-ro,cx+ro,cy+ro),fill='white')
    inner_cx = cx+int(0.0725*H)
    d.ellipse((inner_cx-ri,cy-ri,inner_cx+ri,cy+ri),fill=(227,10,23,255))
    sx=int(0.99*H);sy=cy
    d.polygon(_star_points(sx,sy,0.17*H,0.17*H*0.382),fill='white')
    return flag.resize((width,h),Image.Resampling.LANCZOS)


def _paste_panel(canvas, patch, x, y, border=(252,215,144,255), frame=8):
    w,h=patch.size
    # subtle wood frame avoids floating text/logo appearance.
    bg=Image.new('RGBA',(w+2*frame,h+2*frame),border)
    bg.alpha_composite(patch,(frame,frame))
    canvas.alpha_composite(bg,(x-frame,y-frame))


def add_precise_assets(path, scene_num):
    im=Image.open(path).convert('RGBA')
    if scene_num in (5,8):
        flag=official_flag_image(378)
        _paste_panel(im,flag,665,185,frame=7,
                     border=(110,75,37,255) if scene_num==5 else (224,196,130,255))
    if scene_num == 5:
        if not PORTRAIT.is_file():
            raise RuntimeError('Onaylı posterden alınan Atatürk portresi dosyası eksik.')
        port=Image.open(PORTRAIT).convert('RGBA')
        port=ImageOps.fit(port,(228,256),method=Image.Resampling.LANCZOS)
        _paste_panel(im,port,95,175,border=(120,83,43,255),frame=9)
    im.convert('RGB').save(path,quality=95)


def generate_images(story, folder, key, from_folder=None):
    folder.mkdir(parents=True,exist_ok=True)
    out={}
    for n in SCENES:
        target=folder / f'{n:02}.jpg'
        if from_folder:
            src=Path(from_folder) / f'{n:02}.jpg'
            if not src.is_file(): raise RuntimeError(f'İstenen görsel eksik: {src}')
            im=ImageOps.fit(Image.open(src).convert('RGB'),SIZE,method=Image.Resampling.LANCZOS)
            im.save(target,quality=95)
        else:
            print(f'Yalnızca sahne {n}/10 yeni görsel üretiliyor.')
            _get_image(make_prompt(n), target, key, seed=88130+n)
        add_precise_assets(target,n)
        out[n]=target
    return out


def _timestamp(ms):
    h=ms//3600000; m=(ms//60000)%60; s=(ms//1000)%60; t=(ms%1000)//10
    return f'{h}:{m:02}:{s:02}.{t:02}'


def parse_srt(path):
    txt=Path(path).read_text(encoding='utf-8-sig')
    items=[]
    for chunk in re.split(r'\n\s*\n',txt.strip()):
        m=re.search(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})',chunk)
        if not m: continue
        x=[int(z) for z in m.groups()]
        start=((x[0]*60+x[1])*60+x[2])*1000+x[3]
        end=((x[4]*60+x[5])*60+x[6])*1000+x[7]
        tail=chunk[m.end():].strip().replace('\n',' ')
        if end>start and tail:items.append((start,end,tail))
    if len(items)<10: raise RuntimeError('Altyazı dosyasında yeterli zamanlı cue bulunamadı.')
    return items


def local_ass(cues, start_ms, end_ms, output, is_final=False):
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,64,&H00FFFFFF,&H0000FFFF,&H00202020,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,100,160,420,1
Style: Brand,DejaVu Sans,65,&H00B8F4FF,&H0000FFFF,&H00202020,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,8,100,160,210,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows=[]
    for a,b,text in cues:
        aa=max(a,start_ms);bb=min(b,end_ms)
        if bb<=aa:continue
        text=text.replace('\\',' ').replace('{','').replace('}','').replace('\n',' ')
        rows.append(f'Dialogue: 0,{_timestamp(aa-start_ms)},{_timestamp(bb-start_ms)},Caption,,0,0,0,,{text}')
    if not rows:
        raise RuntimeError(f'{start_ms//1000}. saniye sahnesinde hiçbir altyazı bulunmadı.')
    if is_final:
        rows.append('Dialogue: 1,0:00:00.00,0:00:02.00,Brand,,0,0,0,,MinoMasal')
    output.write_text(header+'\n'.join(rows)+'\n',encoding='utf-8')


def make_segments(source_video, source_srt, images, edges, out_dir):
    out_dir.mkdir(parents=True,exist_ok=True)
    cues=parse_srt(source_srt)
    parts=[]
    for i in range(1,11):
        start_f=edges[i-1]; end_f=edges[i]
        start=start_f/FPS; frames=end_f-start_f; dur=frames/FPS
        target=out_dir/f'{i:02}.mp4'
        if i not in SCENES:
            # Source segment already contains correct synchronized captions.
            run(['ffmpeg','-y','-loglevel','error','-ss',f'{start:.6f}',
                 '-i',source_video,'-an','-frames:v',str(frames),
                 '-vf','fps=24,scale=1080:1920,setsar=1',
                 '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
                 '-r',str(FPS),target])
        else:
            ass=out_dir/f'{i:02}.ass'
            local_ass(cues,round(start*1000),round((end_f/FPS)*1000),ass,is_final=(i==10))
            vf=(f"scale=1200:2134:force_original_aspect_ratio=increase,crop=1200:2134,"
                f"zoompan=z='1.02+0.06*on/{max(1,frames-1)}':"
                f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=1080x1920:fps=24,"
                f"fade=t=in:st=0:d=0.18,fade=t=out:st={max(0,dur-0.18):.3f}:d=0.18,"
                f"ass={ass.name}")
            run(['ffmpeg','-y','-loglevel','error','-loop','1','-framerate',str(FPS),'-i',images[i],
                 '-vf',vf,'-frames:v',str(frames),'-an',
                 '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',target],cwd=out_dir)
        actual=duration(target)
        if abs(actual-dur)>0.09:
            raise RuntimeError(f'Sahne {i} süresi değişti: {actual:.3f} yerine {dur:.3f}')
        parts.append(target)
        print(f'Sahne {i}/10: {"DÜZELTİLDİ" if i in SCENES else "ORİJİNAL KORUNDU"}, {dur:.2f}sn')
    listing=out_dir/'concat.txt'
    listing.write_text(''.join(f"file '{x.name}'\n" for x in parts),encoding='utf-8')
    silent=out_dir/'video_sessiz.mp4'
    run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',listing,
         '-c','copy',silent])
    return silent


def make_contact(images,outfile):
    board=Image.new('RGB',(5*240,480),'#f4f4f4')
    dr=ImageDraw.Draw(board)
    for i,n in enumerate(SCENES):
        im=Image.open(images[n]).convert('RGB')
        im.thumbnail((232,420))
        x=240*i+(240-im.width)//2
        board.paste(im,(x,0))
        dr.text((x+12,427),f'SAHNE {n}',fill='#000000')
    board.save(outfile,quality=88)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=Path('original'))
    p.add_argument('--images-dir',type=Path)
    p.add_argument('--only-images',action='store_true')
    args=p.parse_args()
    args.source=args.source.resolve()
    if args.images_dir is not None: args.images_dir=args.images_dir.resolve()
    if os.environ.get('MINOMASAL_YOUTUBE_UPLOAD','false').lower() == 'true':
        raise RuntimeError('Yayın ayarı açık; bu işlem yalnızca yayınsız kullanılabilir.')
    approved=verify_story(args.source)
    before = _sha256(APPROVED_JSON)
    source_video=args.source/'masal_33_onizleme.mp4'
    source_srt=args.source/'altyazi_33.srt'
    if not any(s['narration'].find('Atatürk') >= 0 for s in approved['scenes']):
        raise RuntimeError('Atatürk anlatımı onaylı metinde bulunamadı.')
    OUTPUT.mkdir(exist_ok=True,parents=True)
    images=generate_images(approved, OUTPUT/'duzeltilen_sahneler',os.environ.get('POLLINATIONS_API_KEY',''),args.images_dir)
    make_contact(images,OUTPUT/'5_sahne_kontrol.jpg')
    if args.only_images:
        print('Yalnızca görsel önizleme tamam. Yayın yapılmadı.');return
    edges=detect_scene_edges(source_video)
    silent=make_segments(source_video,source_srt,images,edges,OUTPUT/'gecici_sahneler')
    target=OUTPUT/'masal_33_revize_yayinsiz.mp4'
    run(['ffmpeg','-y','-loglevel','error','-i',silent,'-i',source_video,
         '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','copy',
         '-movflags','+faststart','-shortest',target])
    d0=duration(source_video);d1=duration(target)
    if abs(d0-d1)>0.25:
        raise RuntimeError(f'Süre doğrulaması başarısız: {d0:.2f} vs {d1:.2f}')
    stream=_ffprobe_json(target)['streams']
    if not any(x.get('codec_type')=='audio' for x in stream):
        raise RuntimeError('Final videoda ses bulunamadı.')
    shutil.copy2(APPROVED_JSON,OUTPUT/'hikaye_33_onayli.json')
    shutil.copy2(source_srt,OUTPUT/'altyazi_33_orijinal.srt')
    if _sha256(APPROVED_JSON)!=before:
        raise RuntimeError('Onaylı hikâye dosyası değişti!')
    print(f'BAŞARILI: {target} / {d1:.2f} saniye. HİÇBİR YAYIN YAPILMADI.')

if __name__=='__main__':
    main()
