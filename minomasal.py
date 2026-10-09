# MinoMasal - GitHub Actions / safe video preview
# Existing publication history is read-only; no social uploads.
import os, json, asyncio, shutil
from pathlib import Path
KANAL_ADI = "MinoMasal"
SES = "tr-TR-EmelNeural"
SES_HIZI = "-3%"
FPS = 24
HIKAYE_MODELI = "openai"
GORSEL_MODELI = "flux"
SEED = 1234
GORSel_KLASORU = ""
MUZIK_KLASORU = Path("music")
MUZIK_SEVIYESI = 0.22
SFX_KLASORU = ""
ROOT = Path("minomasal_data").resolve()
ROOT.mkdir(parents=True, exist_ok=True)
API_KEY = os.environ.get("POLLINATIONS_API_KEY", "")
YAYIN_AKTIF = False
KONULAR = ['Paylaşmayı Öğrenen Sincap', 'Yalan Söyleyen Küçük Tilki', 'Karanlıktan Korkan Tavşan', 'Dişlerini Fırçalamayan Timsah', 'Her Şeye Kızan Minik Aslan', 'Oyuncaklarını Toplamayan Panda', 'Sabırsız Küçük Kaplumbağa', 'Arkadaşını Dinlemeyen Maymun', 'Ellerini Yıkamayı Unutan Ayıcık', 'Kaybetmeyi Sevmeyen Kaplan', 'Sırasını Bekleyemeyen Minik Panda', 'Kaybolan Küçük Penguen', 'Başkalarının Eşyalarını İzinsiz Alan Maymun', 'Yağmurdan Korkan Minik Kedi', 'Her Şeyi Tek Başına Yapmak İsteyen Kunduz', 'Yeni Okuluna Gitmek İstemeyen Tavşan', 'Bulduğu Oyuncağı Sahibine Veren Kirpi', 'Arkadaşına Kötü Söz Söyleyen Papağan', 'Her Şeyi Ekrandan İzlemek İsteyen Ayıcık', 'Küçük Karıncanın Büyük Hayali', 'Ormanı Kirleten Rakun', 'Yemeğini Beğenmeyen Koala', 'Uçmaya Korkan Minik Kuş', 'Özür Dilemeyi Öğrenen Fil', 'Teşekkür Etmeyen Küçük Geyik', 'Uyumak İstemeyen Baykuş', 'Sebze Yemeyen Tavşan', 'Sözünü Tutmayan Kunduz', 'Farklı Görünen Zürafa', 'Yapamam Diyen Küçük Fare']

import asyncio, hashlib, json, math, os, re, subprocess, time, wave
from pathlib import Path
from urllib.parse import quote
import numpy as np
import requests
from PIL import Image, ImageOps
import edge_tts

def run(args):
    p = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if p.returncode: raise RuntimeError(p.stderr[-2200:])
    return p.stdout

def duration(path):
    return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',path]).strip())

def save_json(path, data):
    tmp=Path(str(path)+'.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path)

def validate(story):
    assert isinstance(story,dict) and story.get('title') and story.get('characters'), 'Başlık ve karakter tanımı gerekli.'
    assert 6 <= len(story.get('scenes',[])) <= 15, '6–15 sahne kullanın.'
    for s in story['scenes']:
        assert s.get('narration') and s.get('visual'), 'Her sahnede narration ve visual gerekli.'
        assert len(s['narration'].split())<=35, 'Bir sahnede en fazla 35 kelime kullanın.'
    return story

def create_story(topic, key, model):
    if not key: raise ValueError('Yeni hikâye için Colab Secrets bölümüne POLLINATIONS_API_KEY ekleyin veya JSON hikâye yükleyin.')
    prompt = f"""4–8 yaş çocuklarına Türkçe öğretici hayvan hikâyesi yaz. Konu: {topic}.
Toplam 100–130 kelime, 10 sahne. İlk cümle merak uyandırsın. Olaylar sebep-sonuç sırasıyla ilerlesin.
Tek somut ders, korkutucu içerik yok, tehlikeli davranışa özendirme yok, satın alma/abone ol çağrısı yok.
Son cümlede çocukla ilgili kısa düşünme sorusu sor.
Yalnız JSON döndür: {{"title":"kısa Türkçe başlık","moral":"ders","characters":"tüm karakterlerin İngilizce sabit fiziksel tanımı",
"scenes":[{{"narration":"Türkçe 1–2 kısa cümle","visual":"bu anlatımdaki olayın İngilizce görsel açıklaması","sfx":"none"}}]}}.
Karakter isimlerini ve görünüşlerini bütün sahnelerde koru. Görsel açıklamasında kadraj ve eylem belirt.
"""
    r=requests.post('https://gen.pollinations.ai/v1/chat/completions',headers={'Authorization':'Bearer '+key},
        json={'model':model,'messages':[{'role':'user','content':prompt}],'response_format':{'type':'json_object'}},timeout=150)
    if r.status_code!=200: raise RuntimeError(f'Hikâye servisi HTTP {r.status_code}; anahtar, bakiye ve model adını kontrol edin.')
    text=r.json()['choices'][0]['message']['content']
    text=re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip())
    return validate(json.loads(text))

def make_images(story, folder, key, model, local=''):
    folder.mkdir(exist_ok=True); out=[]
    supplied=sorted(p for p in Path(local).glob('*') if p.suffix.lower() in ['.png','.jpg','.jpeg','.webp']) if local else []
    if local and len(supplied)!=len(story['scenes']): raise ValueError('Yüklenen görsel sayısı sahne sayısına eşit olmalı; 01.jpg, 02.jpg… adlandırın.')
    for i,s in enumerate(story['scenes']):
        path=folder/f'{i+1:02}.jpg'
        if not path.exists():
            if supplied: im=Image.open(supplied[i])
            else:
                if not key: raise ValueError('Görsel üretimi için POLLINATIONS_API_KEY veya yerel görsel klasörü gerekli.')
                prompt=f"{story['characters']}. {s['visual']}. Colorful children's animated storybook illustration, vibrant saturated emerald greens, sky blues and warm coral accents, richly detailed forest environment filling every edge, colorful textured ground and foliage, balanced exposure, no white canvas, no blank white backgrounds, no washed-out colors, no excessive bright haze, consistent character design, vertical composition, full bleed, subjects inside central 70 percent, no lettering, no border."
                for attempt in range(3):
                    try:
                        r=requests.get('https://gen.pollinations.ai/image/'+quote(prompt,safe=''),params={'model':model,'width':1080,'height':1920,'seed':SEED+i,'nologo':'true'},headers={'Authorization':'Bearer '+key},timeout=180)
                        if r.status_code!=200: raise RuntimeError(f'Görsel servisi HTTP {r.status_code}')
                        import io
                        im=Image.open(io.BytesIO(r.content)); im.load(); break
                    except Exception:
                        if attempt==2: raise
                        time.sleep(3*(attempt+1))
            ImageOps.fit(im.convert('RGB'),(1080,1920),method=Image.Resampling.LANCZOS).save(path,quality=95)
        with Image.open(path) as im: im.verify()
        out.append(path); print(f'Görsel {i+1}/{len(story["scenes"])} hazır')
    return out

async def voices(story, folder):
    out=[]
    for i,s in enumerate(story['scenes']):
        audio=folder/f'ses_{i+1:02}.mp3'; meta=folder/f'ses_{i+1:02}.json'
        if not (audio.exists() and meta.exists()):
            words=[]; tmp=Path(str(audio)+'.tmp')
            async def synth():
                com=edge_tts.Communicate(s['narration'],SES,rate=SES_HIZI,boundary='WordBoundary')
                with tmp.open('wb') as f:
                    async for c in com.stream():
                        if c['type']=='audio': f.write(c['data'])
                        elif c['type']=='WordBoundary': words.append({'start':c['offset']/1e7,'end':(c['offset']+c['duration'])/1e7,'text':c['text']})
            await asyncio.wait_for(synth(),timeout=150)
            tmp.replace(audio); save_json(meta,words)
        out.append((audio,duration(audio),json.loads(meta.read_text())))
        print(f'Ses {i+1}/{len(story["scenes"])} hazır')
    return out

def ass_time(t):
    cs=round(max(0,t)*100); h,cs=divmod(cs,360000); m,cs=divmod(cs,6000); s,cs=divmod(cs,100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'

def srt_time(t):
    ms=round(max(0,t)*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def clean_ass(s): return s.replace('\\',' ').replace('{','').replace('}','').replace('\n',' ')

def subtitle_groups(words,text,dur):
    if not words:
        print('UYARI: kelime zamanları gelmedi; bu sahnede yaklaşık altyazı kullanılıyor.')
        tokens=text.split(); words=[{'text':w,'start':dur*i/len(tokens),'end':dur*(i+1)/len(tokens)} for i,w in enumerate(tokens)]
    groups=[]; group=[]
    for word in words:
        if group and (len(group)>=5 or len(' '.join(x['text'] for x in group+[word]))>32): groups.append(group); group=[]
        group.append(word)
    if group: groups.append(group)
    return [(max(0,g[0]['start']),min(dur,g[-1]['end']), ' '.join(x['text'] for x in g)) for g in groups]

def make_ass(path,cues,title='',brand=''):
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,64,&H00FFFFFF,&H0000FFFF,&H00202020,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,100,160,420,1
Style: Title,DejaVu Sans,65,&H00B8F4FF,&H0000FFFF,&H00202020,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,8,100,160,210,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events=[f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Caption,,0,0,0,,{clean_ass(t)}' for a,b,t in cues if b>a]
    if title: events.append(f'Dialogue: 1,0:00:00.00,0:00:01.80,Title,,0,0,0,,{clean_ass(title)}')
    if brand: events.append(f'Dialogue: 1,0:00:00.00,0:00:02.00,Title,,0,0,0,,{clean_ass(brand)}')
    path.write_text(header+'\n'.join(events),encoding='utf-8')

MUZIK_DOSYALARI = {
    "intro": "intro.mp3",
    "happy": "happy.mp3",
    "mystery": "mystery.mp3",
    "emotional": "emotional.mp3",
    "ending": "ending.mp3",
}


def music_for_scene(scene, index, count):
    """Hikâye konumuna ve sahne anlatımına göre müzik kategorisi seç."""
    if index == 0:
        return "intro"
    if index == count - 1:
        return "ending"
    text = (scene.get("narration", "") + " " + scene.get("visual", "")).lower()
    emotional = ("üzül", "ağla", "pişman", "yalnız", "kırıl", "özür", "kork", "sad", "cry", "sorry", "afraid")
    mysterious = ("gizli", "saklan", "aramaya", "kaybol", "merak", "acaba", "sessizce", "sneak", "mystery", "search")
    if any(word in text for word in emotional):
        return "emotional"
    if any(word in text for word in mysterious):
        return "mystery"
    return "happy"


def make_scene_music(story, lengths, folder):
    """Gerçek MP3'lerden, sahne sürelerine uyan ve yumuşak geçişli müzik hazırla."""
    paths = {kind: MUZIK_KLASORU / name for kind, name in MUZIK_DOSYALARI.items()}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError("Müzik dosyaları eksik: " + ", ".join(missing))
    segments = []
    for i, (scene, length) in enumerate(zip(story["scenes"], lengths)):
        kind = music_for_scene(scene, i, len(lengths))
        target = folder / f"muzik_{i:02}.wav"
        fade = min(0.45, length / 4)
        filter_audio = (
            f"[0:a]aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo,"
            f"atrim=duration={length:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={max(0,length-fade):.4f}:d={fade:.3f}[a]"
        )
        run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", paths[kind],
             "-filter_complex", filter_audio, "-map", "[a]", "-c:a", "pcm_s16le", target])
        segments.append(target)
        print(f"Müzik {i+1}/{len(lengths)}: {kind}")
    listing = folder / "muzik_concat.txt"
    listing.write_text("\n".join("file '" + p.name + "'" for p in segments), encoding="utf-8")
    output = folder / "sinematik_muzik.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing, "-c", "copy", output])
    return output


def render(story,images,audios,folder):
    parts=[]; part_lengths=[]; all_cues=[]; offset=0
    for i,(im,(audio,dur,words),s) in enumerate(zip(images,audios,story['scenes'])):
        cues=subtitle_groups(words,s['narration'],dur)
        all_cues.extend((a+offset,b+offset,t) for a,b,t in cues)
        ass=folder/f'caption_{i:02}.ass'; make_ass(ass,cues,story['title'] if i==0 else '',KANAL_ADI if i==len(images)-1 else '')
        out=folder/f'part_{i:02}.mp4'; frames=math.ceil(dur*FPS)
        zoom=f"1.02+0.06*on/{max(1,frames-1)}"
        # Önce cover; zoompan sabit 1080x1920 çıktı verir. Hafif merkez hareketi.
        vf=f"scale=1200:2134:force_original_aspect_ratio=increase,crop=1200:2134,zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=1080x1920:fps={FPS},fade=t=in:st=0:d=0.18,fade=t=out:st={max(0,dur-0.18)}:d=0.18,ass={ass.name}"
        # SFX yalnız yüklenen dosyalardan; eksik bir efekt sessizce uydurulmaz.
        effect=Path(SFX_KLASORU)/str(s.get('sfx','none')) if SFX_KLASORU else None
        args=['ffmpeg','-y','-loglevel','error','-i',im,'-i',audio]
        if effect and effect.is_file():
            args += ['-i',effect,'-filter_complex','[2:a]volume=0.10[fx];[1:a][fx]amix=inputs=2:duration=first:normalize=0[a]','-map','0:v','-map','[a]']
        else: args+=['-map','0:v','-map','1:a']
        args+=['-vf',vf,'-t',dur,'-r',FPS,'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2',out.name]
        # cwd yalnız işlem için değiştirilir; tam dosya yolları kullanılır.
        p=subprocess.run([str(x) for x in args],cwd=folder,capture_output=True,text=True)
        if p.returncode: raise RuntimeError(p.stderr[-2200:])
        parts.append(out); part_lengths.append(duration(out)); offset+=part_lengths[-1]; print(f'Montaj {i+1}/{len(images)} hazır')
    (folder/'altyazi.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(a)} --> {srt_time(b)}\n{t}' for i,(a,b,t) in enumerate(all_cues)),encoding='utf-8')
    listing=folder/'concat.txt'; listing.write_text('\n'.join("file '"+p.name+"'" for p in parts))
    raw=folder/'sessiz_muzik.mp4'
    run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',listing,'-c','copy',raw])
    total=duration(raw)
    music=make_scene_music(story,part_lengths,folder)
    final=folder/'masal_short.mp4'
    # Konuşma sırasında müzik düşürülür; kısa müzik dosyası döngüye alınır.
    fc=f'[0:a]asplit=2[v][side];[1:a]volume={MUZIK_SEVIYESI},afade=t=out:st={max(0,total-2)}:d=2[m];[m][side]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=300[duck];[v][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]'
    run(['ffmpeg','-y','-loglevel','error','-i',raw,'-stream_loop','-1','-i',music,'-filter_complex',fc,'-map','0:v','-map','[a]','-t',total,'-c:v','copy','-c:a','aac','-movflags','+faststart',final])
    return final

async def produce(topic, supplied_story=None):
    story=validate(supplied_story) if supplied_story else create_story(topic,API_KEY,HIKAYE_MODELI)
    identity={'story':story,'voice':SES,'rate':SES_HIZI,'image_model':GORSEL_MODELI,'seed':SEED,'local':GORSel_KLASORU,'music_files':{k:hashlib.sha256((MUZIK_KLASORU / v).read_bytes()).hexdigest()[:12] if (MUZIK_KLASORU / v).is_file() else 'missing' for k,v in MUZIK_DOSYALARI.items()},'music_level':MUZIK_SEVIYESI,'sfx':SFX_KLASORU,'fps':FPS,'channel':KANAL_ADI,'engine':4}
    fingerprint=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:12]
    folder=(ROOT/fingerprint).resolve(); folder.mkdir(parents=True,exist_ok=True)
    save_json(folder/'hikaye.json',story)
    complete=folder/'tamam.json'; final=folder/'masal_short.mp4'
    if complete.exists() and final.exists() and duration(final)>1:
        print('Önceden tamamlandı:',final); return final
    images=make_images(story,folder/'gorseller',API_KEY,GORSEL_MODELI,GORSel_KLASORU)
    audios=await voices(story,folder)
    final=render(story,images,audios,folder)
    save_json(complete,{'title':story['title'],'duration':duration(final),'video':str(final)})
    print('Video hazır:',final); return final


async def main():
    if YAYIN_AKTIF:
        raise RuntimeError("Bu test sürümünde yayınlama desteklenmiyor.")
    if not API_KEY:
        raise RuntimeError("POLLINATIONS_API_KEY GitHub Secret eksik.")
    state_file = Path("minomasal_yayin_durumu.json")
    if not state_file.is_file():
        raise RuntimeError("Yayın geçmişi JSON dosyası repoda bulunamadı; tekrar üretim riskinden durduruldu.")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    pending = next(((i, t) for i, t in enumerate(KONULAR, 1) if not state.get(str(i), {}).get("complete")), None)
    if pending is None:
        print("Bekleyen hikâye yok.")
        return
    num, topic = pending
    print(f"Test videosu: {num}. {topic}")
    video = await produce(topic)
    story = json.loads((video.parent / "hikaye.json").read_text(encoding="utf-8"))
    title = str(story.get("title") or topic).strip() + " | MinoMasal"
    shutil.copy2(video, ROOT / "minomasal_test_video.mp4")
    (ROOT / "test_ozeti.json").write_text(json.dumps({"number":num,"topic":topic,"title":title,"video":"minomasal_test_video.mp4","youtube_uploaded":False,"voice":SES,"rate":SES_HIZI},ensure_ascii=False,indent=2),encoding="utf-8")
    print("ÖNİZLEME TAMAMLANDI; YouTube'a yüklenmedi. Dosya:", ROOT / "minomasal_test_video.mp4")

if __name__ == "__main__":
    asyncio.run(main())
