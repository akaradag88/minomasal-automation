# MinoMasal - GitHub Actions / safe video preview
# Existing publication history is read-only; no social uploads.
import os, json, asyncio, shutil
from pathlib import Path
KANAL_ADI = "MinoMasal"
SES = "Leda"
SES_HIZI = "Promote"
FPS = 24
HIKAYE_MODELI = "gemini"
GORSEL_MODELI = os.environ.get("MINOMASAL_IMAGE_MODEL", "gemini-nano-banana-2.1")
IMAGE_PROVIDER = os.environ.get("MINOMASAL_IMAGE_PROVIDER", "gemini").strip().lower()
SEED = 1234
GORSel_KLASORU = ""
MUZIK_KLASORU = Path("music")
MUZIK_SEVIYESI = 0.12
SFX_KLASORU = ""
ROOT = Path("minomasal_data").resolve()
ROOT.mkdir(parents=True, exist_ok=True)
API_KEY = os.environ.get("GEMINI_API_KEY", "")
YAYIN_AKTIF = os.environ.get("MINOMASAL_YOUTUBE_UPLOAD", "false").lower() == "true"
YOUTUBE_GORUNURLUK = os.environ.get("MINOMASAL_YOUTUBE_PRIVACY", "private").lower()
if YOUTUBE_GORUNURLUK not in ("private", "public", "unlisted"):
    raise ValueError("MINOMASAL_YOUTUBE_PRIVACY private, public veya unlisted olmali.")
KONULAR = ['Paylaşmayı Öğrenen Sincap', 'Yalan Söyleyen Küçük Tilki', 
           'Karanlıktan Korkan Tavşan', 'Dişlerini Fırçalamayan Timsah', 
           'Her Şeye Kızan Minik Aslan', 'Oyuncaklarını Toplamayan Panda', 
           'Sabırsız Küçük Kaplumbağa', 'Arkadaşını Dinlemeyen Maymun', 
           'Ellerini Yıkamayı Unutan Ayıcık', 'Kaybetmeyi Sevmeyen Kaplan', 
           'Sırasını Bekleyemeyen Minik Panda', 'Kaybolan Küçük Penguen', 
           'Başkalarının Eşyalarını İzinsiz Alan Maymun', 'Yağmurdan Korkan Minik Kedi', 
           'Her Şeyi Tek Başına Yapmak İsteyen Kunduz', 'Yeni Okuluna Gitmek İstemeyen Tavşan',
           'Bulduğu Oyuncağı Sahibine Veren Kirpi', 'Arkadaşına Kötü Söz Söyleyen Papağan', 
           'Her Şeyi Ekrandan İzlemek İsteyen Ayıcık', 'Küçük Karıncanın Büyük Hayali', 
           'Ormanı Kirleten Rakun', 'Yemeğini Beğenmeyen Koala', 'Uçmaya Korkan Minik Kuş', 
           'Özür Dilemeyi Öğrenen Fil', 'Teşekkür Etmeyen Küçük Geyik', 
           'Uyumak İstemeyen Baykuş', 'Sebze Yemeyen Tavşan', 'Sözünü Tutmayan Kunduz', 
           'Farklı Görünen Zürafa', 'Yapamam Diyen Küçük Fare', 
    # 31–45: Hayvanların eğitici maceraları
    'Arkadaşını Kıskanan Küçük Kedi',
    'Cesur Olmayı Öğrenen Kirpi',
    'Minik Sincabın Kırmızı Beyaz Bayrağı',
    'Orman Okulunda Cumhuriyet Coşkusu',
    'Arkadaşına Yardım Eden Minik Fil',
    'Sürekli Acele Eden Tavşan',
    'Söz Dinlemeyen Küçük Penguen',
    'Kendini Beğenmeyen Zürafa',
    'Arkadaşını Affeden Minik Aslan',
    'Her Şeye Hayır Diyen Panda',
    'Yuva Yapmayı Öğrenen Serçe',
    'Sorumluluk Alan Küçük Tilki',
    'Yalnız Oynamak İsteyen Koala',
    'Başkalarıyla Alay Eden Maymun',
    "Küçük Baykuş Atatürk'ü Öğreniyor",

    # 46–60: İş makineleri ve araçlar
    "Orman Okulunda Atatürk'ü Anma Günü",
    'Kaybolan Oyuncak Kamyon',
    'İlk Görevine Çıkan İtfaiye Aracı',
    'Sabırsız Küçük Yarış Arabası',
    'Çamura Saplanan Traktör',
    'Arkadaşlarını Kurtaran Çekici',
    'Küçük Beton Mikserinin Büyük Görevi',
    'Yolunu Kaybeden Minik Otobüs',
    'Paylaşmayı Öğrenen Oyuncak Tren',
    'Küçük Vinç ve Yüksek Kule',
    'Temizlik Yapan Çöp Kamyonu',
    'Karanlıktan Korkan Küçük Araba',
    'Yardımsever Ambulansın Macerası',
    'İlk Yolculuğuna Çıkan Elektrikli Otomobil',
    'Köprü Yapan İş Makineleri',

    # 61–80: Arkadaşlık, duygular ve günlük yaşam
    'Yeni Arkadaş Edinen Minik Dinozor',
    'Öfkesini Kontrol Eden Küçük Ejderha',
    'Kaybolan Balonunu Arayan Çocuk',
    'Sıra Beklemeyi Öğrenen Küçük Robot',
    'Herkesi Mutlu Etmeye Çalışan Minik Bulut',
    'İlk Kez Okula Giden Küçük Dinozor',
    'Kardeşini Kıskanan Minik Ayıcık',
    'Kendi Başına Giyinmeyi Öğrenen Tavşan',
    'Oyuncağını Kaybeden Küçük Çocuk',
    'Arkadaşından Özür Dileyen Minik Robot',
    'Korktuğunu Söyleyen Küçük Aslan',
    'Yardım İstemeyi Öğrenen Minik Fil',
    'Herkesin Farklı Olduğunu Öğrenen Dinozor',
    'Sabretmeyi Öğrenen Küçük Roket',
    'Arkadaşını Teselli Eden Minik Panda',
    'Başarısız Olunca Vazgeçmeyen Küçük Araba',
    'Doğruyu Söyleyen Cesur Tavşan',
    'İlk Kez Bisiklete Binen Küçük Ayı',
    'Teşekkür Etmeyi Öğrenen Minik Robot',
    'Arkadaşlarıyla Barışan Küçük Tilki',

    # 81–100: Keşif, doğa ve macera
    'Uzayı Keşfeden Küçük Roket',
    'Denizin Altındaki Meraklı Denizaltı',
    'Ormanı Koruyan Minik Dinozor',
    'Kaybolan Yıldızı Arayan Küçük Astronot',
    'Geri Dönüşümü Öğrenen Küçük Robot',
    'İlk Kar Yağışını Gören Minik Tavşan',
    'Renklerini Kaybeden Gökkuşağı',
    'Çiçekleri Koruyan Küçük Arı',
    'Yağmur Damlasının Büyük Yolculuğu',
    'Güneşi Arayan Küçük Bulut',
    'Denizleri Temizleyen Minik Kaplumbağa',
    'Ay Yolculuğuna Çıkan Küçük Robot',
    'Ormanda Yolunu Bulan Minik Kirpi',
    'Kutup Yıldızını Arayan Penguen',
    'Rüzgârla Yarışan Küçük Uçak',
    'Dünyayı Gezen Meraklı Balon',
    'Tohum Eken Küçük Traktör',
    'Yıldızları Saymayı Öğrenen Minik Baykuş',
    'Gizli Bahçeyi Keşfeden Küçük Sincap',
    'Doğayı Kurtaran Küçük Kahramanlar'
]

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

# ---------------------------------------------------------------------------
# MinoMasal v6: Gemini (hikâye, ses, görsel üretimi ve kontrolü); Cloudflare isteğe bağlı alternatif
# Karakter adları ve görünüşleri minomasal_karakterler.json dosyasından gelir.
# ---------------------------------------------------------------------------
import base64, io, zlib

GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta'
STORY_MODELS = [m for m in (os.environ.get('MINOMASAL_STORY_MODEL', ''), 'gemini-3.8-flash', 'gemini-3.5-flash', 'gemini-3.5-flash-lite') if m]
QC_MODELS = [m for m in (os.environ.get('MINOMASAL_QC_MODEL', ''), 'gemini-3.5-flash-lite', 'gemini-3.8-flash') if m]
TTS_MODEL = os.environ.get('MINOMASAL_TTS_MODEL', 'gemini-3.8-flash-tts')
TTS_STYLE = os.environ.get('MINOMASAL_TTS_STYLE', 'warm, gentle fairy-tale narrator for young children, lively and clear')
CF_MODEL = '@cf/black-forest-labs/flux-2-klein-4b'
IMG_W, IMG_H = 864, 1536          # 9:16; 1080x1920'ye montaj sırasında büyütülür
QC_MIN_ACCEPT = 7                 # bu puan ve üstü: hemen kabul
QC_MIN_FLOOR = 5                  # en iyi deneme bunun altındaysa üretim DURUR
SCENE_ATTEMPTS = 2  # Gemini görsel maliyetini sınırlamak için en fazla iki kalite denemesi
STYLE_LOCK = ("Colorful children's animated storybook illustration, soft 3D-rendered look, vibrant but balanced pastel colors, "
              "richly detailed environment filling every edge, no white canvas, no blank white background, no washed-out colors, "
              "consistent character design, vertical 9:16 composition, full bleed, main subjects inside the central 70 percent, "
              "no text, no letters, no watermark, no border")
CHAR_FILE = Path(__file__).with_name('minomasal_karakterler.json')
CHAR_SHEET_DIR = Path(__file__).with_name('karakter_gorselleri')   # isteğe bağlı: onaylı kalıcı karakter kartları


def load_bible():
    return json.loads(CHAR_FILE.read_text(encoding='utf-8'))


def ids_for_topic(topic):
    """Konu numarasından karakter kimliklerini bulur (defterdeki story_characters_31_100)."""
    number = KONULAR.index(topic) + 1
    return list(load_bible().get('story_characters_31_100', {}).get(str(number), []))


def _clean_err(r):
    try:
        e = r.json()
        e = e.get('error', e) if isinstance(e, dict) else e
        msg = e.get('message') if isinstance(e, dict) else str(e)
        if not msg and isinstance(e, dict) and e.get('errors'): msg = '; '.join(str(x.get('message')) for x in e['errors'])
        return str(msg or r.text)[:300]
    except Exception:
        return r.text[:300]


def gemini_post(path, payload, tries=4, timeout=120):
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key: raise RuntimeError('GEMINI_API_KEY GitHub Secret eksik.')
    last = ''
    for k in range(tries):
        try:
            r = requests.post(f'{GEMINI_BASE}/{path}', headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, json=payload, timeout=timeout)
        except requests.exceptions.RequestException as e:
            last = f'ağ hatası ({type(e).__name__}, {timeout} sn)'
            print(f'Gemini {path.split(":")[0]} {last}; deneme {k+1}/{tries}')
            if k < tries - 1: time.sleep(5 * (k + 1)); continue
            break
        if r.status_code == 200: return r.json()
        last = f'HTTP {r.status_code}: {_clean_err(r)}'
        if r.status_code == 429 and ('per day' in last.lower() or 'daily' in last.lower()):
            raise RuntimeError(f'Gemini günlük ücretsiz kota doldu ({path.split(":")[0]}; kota Pasifik saatiyle gece yarısı, Türkiye saatiyle 11:00\'de sıfırlanır): {last}')
        if r.status_code in (429, 500, 502, 503, 504) and k < tries - 1:
            time.sleep(6 * (2 ** k)); continue
        break
    raise RuntimeError(f'Gemini isteği başarısız ({path.split(":")[0]}): {last}')


def gemini_text(prompt, models, images=(), as_json=False, timeout=90, rounds=2):
    """Modelleri sırayla dener: 503/429/404/403 gibi hatalarda sıradaki modele geçer; iki tur sonra durur."""
    parts = [{'text': prompt}] + [{'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(b).decode()}} for b in images]
    payload = {'contents': [{'role': 'user', 'parts': parts}]}
    if as_json: payload['generationConfig'] = {'responseMimeType': 'application/json'}
    errors = []
    for rnd in range(rounds):
        for m in models:
            try:
                data = gemini_post(f'models/{m}:generateContent', payload, tries=2, timeout=timeout)
                cand = (data.get('candidates') or [{}])[0]
                text = ''.join(p.get('text', '') for p in cand.get('content', {}).get('parts', []))
                if not text.strip(): raise RuntimeError('boş yanıt')
                return text, m
            except RuntimeError as e:
                if 'Secret eksik' in str(e): raise
                errors.append(f'{m}: {str(e)[:120]}')
                print(f'Gemini modeli atlandı -> {errors[-1]}')
        if rnd < rounds - 1: time.sleep(30)          # yoğunluk geçsin diye kısa bekleme, sonra ikinci tur
    raise RuntimeError('Gemini metin modeli kullanılamadı -> ' + ' | '.join(errors[-4:]))


def create_story(topic, key=None, model=None):
    number = KONULAR.index(topic) + 1
    bible = load_bible(); ids = ids_for_topic(topic)
    if not ids: raise RuntimeError(f'{number}. konu için karakter defterinde kayıt yok: {topic}')
    chars = bible['characters']
    cast = '\n'.join(f"- id={i} | ad={chars[i]['name']} | tür={chars[i]['type_tr']} | kişilik={chars[i]['personality_tr']}" for i in ids)
    prompt = f"""4–8 yaş çocuklarına Türkçe öğretici bir masal yaz. Konu: {topic}.
Toplam 75–110 kelime, tam 10 sahne, her sahnede 1–2 kısa cümle. İlk cümle merak uyandırsın. Olaylar sebep-sonuç sırasıyla ilerlesin.
Tek somut ders, korkutucu içerik yok, tehlikeli davranışa özendirme yok, satın alma/abone ol çağrısı yok.
Son cümlede çocukla ilgili kısa bir düşünme sorusu sor.
KARAKTERLER (yalnız bunlar olsun, adlarını aynen kullan, yeni karakter ekleme):
{cast}
Yalnız JSON döndür: {{"title":"kısa Türkçe başlık","moral":"ders","scenes":[{{"narration":"Türkçe 1–2 kısa cümle","visual":"bu anlatımdaki olayın İngilizce görsel açıklaması: yalnız eylem, ortam ve kadraj; karakterlerin görünüşünü yazma, yalnız adlarını kullan","present":["bu sahnede görünen karakter id'leri"],"sfx":"none"}}]}}.
Her sahnede anlatımda adı geçen karakter "present" listesinde olsun. Sahneler birbirini görsel olarak takip etsin.
"""
    # Özel gün kuralları yalnızca ilgili dört hikâyeye uygulanır.
    ozel_gunler = {
        "Minik Sincabın Kırmızı Beyaz Bayrağı": "29 EKİM CUMHURİYET BAYRAMI:",
        "Orman Okulunda Cumhuriyet Coşkusu": "29 EKİM CUMHURİYET BAYRAMI:",
        "Küçük Baykuş Atatürk'ü Öğreniyor": "10 KASIM ATATÜRK'Ü ANMA GÜNÜ:",
        "Orman Okulunda Atatürk'ü Anma Günü": "10 KASIM ATATÜRK'Ü ANMA GÜNÜ:",
    }
    baslik = ozel_gunler.get(topic)
    if baslik:
        metin = Path(__file__).with_name("minomasal_ozel_gun_kurallari.txt").read_text(encoding="utf-8")
        ortak_baslik = "ORTAK KURALLAR:"
        bitis = "10 KASIM ATATÜRK'Ü ANMA GÜNÜ:" if baslik.startswith("29 EKİM") else ortak_baslik
        if baslik not in metin or bitis not in metin or ortak_baslik not in metin:
            raise RuntimeError("Özel gün kuralları eksik.")
        ozel = metin.split(baslik, 1)[1].split(bitis, 1)[0]
        ortak = metin.split(ortak_baslik, 1)[1]
        prompt += "\n\nBU HİKÂYEYE ÖZEL ZORUNLU KURALLAR:\n" + ozel.strip() + "\n\nORTAK KURALLAR:\n" + ortak.strip()
    story = None
    for att in range(3):
        extra_hint = '' if att == 0 else '\n\nÖNEMLİ: "scenes" dizisinde TAM 10 sahne olmalı, ne eksik ne fazla.'
        text, used = gemini_text(prompt + extra_hint, STORY_MODELS, as_json=True)
        print('Hikâye modeli:', used)
        try: cand = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip()))
        except ValueError: print('Hikâye JSON okunamadı, tekrar deneniyor.'); continue
        if isinstance(cand, dict) and len(cand.get('scenes', [])) == 10: story = cand; break
        print(f'Hikâye {len(cand.get("scenes", [])) if isinstance(cand, dict) else 0} sahne üretti (10 gerekli), tekrar deneniyor.')
    if story is None: raise RuntimeError('Gemini 3 denemede tam 10 sahnelik geçerli hikâye üretemedi.')
    # Görünüş bilgisi modele bırakılmaz: defterden eklenir.
    story['characters'] = ' '.join(f"{chars[i]['name']}: {chars[i]['appearance_en']}" for i in ids)
    story['char_ids'] = ids
    for s in story.get('scenes', []):
        present = [x for x in s.get('present', []) if x in ids]
        s['present'] = present or list(ids)
    return validate(story)


# ------------------------------- görsel ------------------------------------

def _png_bytes(im, box=480):
    im = im.convert('RGB').copy(); im.thumbnail((box, box), Image.Resampling.LANCZOS)
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()


class CFFlagged(RuntimeError):
    """Cloudflare içerik filtresi çıktıyı işaretledi (çoğu zaman yanlış alarm; farklı seed/istemle geçilir)."""


SAFE_PREFIX = 'Wholesome, family-friendly, gentle and cheerful scene for preschool children. '


def cf_generate(prompt, refs, seed, width, height):
    acc = os.environ.get('CLOUDFLARE_ACCOUNT_ID', ''); tok = os.environ.get('CLOUDFLARE_API_TOKEN', '')
    if not acc or not tok: raise RuntimeError('CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN GitHub Secret eksik.')
    url = f'https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{CF_MODEL}'
    for attempt in range(3):
        fields = {'prompt': (None, prompt), 'width': (None, str(width)), 'height': (None, str(height)), 'seed': (None, str(int(seed)))}
        for i, png in enumerate(refs[:4]): fields[f'input_image_{i}'] = (f'ref{i}.png', png, 'image/png')
        try:
            r = requests.post(url, headers={'Authorization': 'Bearer ' + tok}, files=fields, timeout=240)
        except requests.exceptions.RequestException as e:
            print(f'Cloudflare ağ hatası ({type(e).__name__}); deneme {attempt+1}/3')
            if attempt < 2: time.sleep(5 * (attempt + 1)); continue
            raise RuntimeError(f'Cloudflare bağlantı hatası: {type(e).__name__}')
        if r.status_code == 200:
            if r.headers.get('content-type', '').startswith('image/'): raw = r.content
            else:
                j = r.json()
                if not j.get('success', True): raise RuntimeError('Cloudflare hata: ' + _clean_err(r))
                raw = base64.b64decode(j['result']['image'])
            im = Image.open(io.BytesIO(raw)); im.load(); return im.convert('RGB')
        msg = _clean_err(r)
        if r.status_code == 400 and 'flagged' in msg.lower(): raise CFFlagged(f'Cloudflare içerik filtresi: {msg}')
        if r.status_code in (401, 403): raise RuntimeError(f'Cloudflare yetki hatası (HTTP {r.status_code}): token izni veya hesap kimliği yanlış olabilir. {msg}')
        if r.status_code == 429 or 'neuron' in msg.lower() or '4006' in msg:
            raise RuntimeError(f'Cloudflare günlük ücretsiz kota dolmuş olabilir (HTTP {r.status_code}): {msg}')
        if r.status_code >= 500 and attempt < 2: time.sleep(5 * (attempt + 1)); continue
        raise RuntimeError(f'Cloudflare görsel hatası (HTTP {r.status_code}): {msg}')



def gemini_image_generate(prompt, refs, width, height, model=None):
    """Gemini Nano Banana ile tek görsel üretir; referans karakter görsellerini aynı isteğe ekler."""
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key:
        raise RuntimeError('GEMINI_API_KEY GitHub Secret eksik.')
    model = model or GORSEL_MODELI
    ratio = '9:16' if height > width else '1:1'
    inputs = [{'type': 'text', 'text': prompt}]
    for png in refs[:4]:
        inputs.append({
            'type': 'image',
            'mime_type': 'image/png',
            'data': base64.b64encode(png).decode('ascii')
        })
    payload = {
        'model': model,
        'input': inputs,
        'response_format': {
            'type': 'image',
            'mime_type': 'image/jpeg',
            'aspect_ratio': ratio,
            'image_size': '1K'
        }
    }
    last = ''
    for attempt in range(2):
        try:
            response = requests.post(
                f'{GEMINI_BASE}/interactions',
                headers={
                    'x-goog-api-key': key,
                    'Content-Type': 'application/json',
                    'Api-Revision': '2026-05-20'
                },
                json=payload,
                timeout=300
            )
        except requests.exceptions.RequestException as e:
            last = f'ağ hatası ({type(e).__name__})'
            if attempt == 0:
                time.sleep(4)
                continue
            raise RuntimeError(f'Gemini görsel bağlantı hatası: {last}')
        if response.status_code == 200:
            data = response.json()
            image_data = (data.get('output_image') or {}).get('data')
            if not image_data:
                for step in data.get('steps', []):
                    if step.get('type') == 'model_output':
                        for block in step.get('content', []):
                            if block.get('type') == 'image' and block.get('data'):
                                image_data = block['data']
                                break
                    if image_data:
                        break
            if not image_data:
                raise RuntimeError('Gemini görsel yanıtı başarılı görünüyor ancak görsel verisi içermiyor.')
            try:
                raw = base64.b64decode(image_data)
                im = Image.open(io.BytesIO(raw))
                im.load()
                return im.convert('RGB')
            except Exception as e:
                raise RuntimeError(f'Gemini görsel çıktısı okunamadı: {type(e).__name__}')
        last = f'HTTP {response.status_code}: {_clean_err(response)}'
        if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(6)
            continue
        raise RuntimeError(f'Gemini görsel üretimi başarısız: {last}')
    raise RuntimeError(f'Gemini görsel üretimi başarısız: {last}')

def judge(image, expected, anchors, visual=''):
    """Gemini görü modeli kalite kontrolü. Dönüş: (puan, sorunlar) ya da (None, [neden]) — kontrol yapılamadıysa."""
    names = ', '.join(f"{c['name']} ({c['type_tr']})" for c in expected)
    prompt = (f"You are a strict quality checker for children's storybook illustrations. Image 1 is the generated picture. "
              f"The following images are reference pictures of the expected characters, in this order: {names}. "
              f"Check: (1) every expected character is visible and clearly the same species/vehicle with the same colors and accessories as its reference; "
              f"(2) no unexpected extra characters; (3) no text, letters or watermark; (4) no anatomy errors such as extra or missing limbs or merged bodies; "
              f"(5) the picture matches this scene: {visual or 'n/a'}. "
              f'Return only JSON: {{"score": integer 0-10, "problems": ["short English strings"]}}.')
    try:
        text, _ = gemini_text(prompt, QC_MODELS, images=[_png_bytes(image, 768)] + [_png_bytes(a, 384) for a in anchors], as_json=True, timeout=60, rounds=1)
        d = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip()))
        return float(d.get('score')), [str(x) for x in d.get('problems', [])][:5]
    except Exception as e:
        return None, [f'kontrol yapılamadı: {str(e)[:160]}']


def character_anchor(cid, c, folder):
    """Karakterin referans görseli: önce kalıcı kart, sonra bu videonun önbelleği, yoksa sabit seed ile üretilir."""
    sheet = CHAR_SHEET_DIR / f'{cid}.png'
    if sheet.is_file(): return Image.open(sheet).convert('RGB')
    path = folder / f'{cid}.png'
    if path.exists(): return Image.open(path).convert('RGB')
    prompt = (f"Character reference picture of {c['name']}. {c['appearance_en']} Single character only, full body, centered, "
              f"friendly neutral pose, plain soft pastel background. {STYLE_LOCK}")
    base = zlib.crc32(cid.encode()) % 900000
    best = (-1, None); flagged = 0; judged = 0
    anchor_attempts = 2 if IMAGE_PROVIDER == 'gemini' else 5
    for k in range(anchor_attempts):
        try:
            anchor_prompt = (SAFE_PREFIX + prompt) if flagged else prompt
            im = (gemini_image_generate(anchor_prompt, [], 768, 768) if IMAGE_PROVIDER == 'gemini'
                  else cf_generate(anchor_prompt, [], base + k * 7919, 768, 768))
        except CFFlagged:
            flagged += 1; print(f'Karakter kartı {c["name"]} deneme {k+1}: içerik filtresi işaretledi, yeniden deneniyor.'); continue
        judged += 1
        score, problems = judge(im, [c], [], 'single character reference picture')
        print(f'Karakter kartı {c["name"]} deneme {k+1}: puan={score} {problems}')
        if score is None: best = (None, im); break       # kontrol yapılamadı: ilk görseli kullan
        if score > best[0]: best = (score, im)
        if score >= QC_MIN_ACCEPT or judged >= 3: break
    if best[1] is None: raise RuntimeError(f'{c["name"]} karakter kartı: görsel üretimi tüm denemelerde başarısız oldu.')
    if best[0] is not None and best[0] < QC_MIN_FLOOR: raise RuntimeError(f'{c["name"]} karakter kartı kalite kontrolünden geçemedi (puan {best[0]}).')
    path.parent.mkdir(parents=True, exist_ok=True); best[1].save(path)
    return best[1]


def scene_prompt(scene, chars, extra_ref=False):
    refs = [f"reference image {i} shows {c['name']}" for i, c in enumerate(chars)]
    if extra_ref: refs.append(f"reference image {len(chars)} shows the established art style and setting")
    keep = 'Keep every character exactly as in its reference image: same species, body shape, colors and accessories.'
    who = ' '.join(f"{c['name']}: {c['appearance_en']}" for c in chars)
    p = f"{'; '.join(refs)}. {keep} Characters: {who} Scene: {scene['visual']}. {STYLE_LOCK}"
    if len(p) > 1900: p = f"{'; '.join(refs)}. {keep} Scene: {scene['visual']}. {STYLE_LOCK}"
    return p


def make_images(story, folder, key=None, model=None, local=''):
    folder.mkdir(exist_ok=True); out = []; report = []
    supplied = sorted(p for p in Path(local).glob('*') if p.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']) if local else []
    if local and len(supplied) != len(story['scenes']): raise ValueError('Yüklenen görsel sayısı sahne sayısına eşit olmalı; 01.jpg, 02.jpg… adlandırın.')
    bible = load_bible()['characters']; ids = story.get('char_ids') or []
    cache = folder.parent / 'karakterler'; anchors = {}
    if ids and not supplied:
        for cid in ids:
            anchors[cid] = character_anchor(cid, bible[cid], cache)
            print(f'Karakter kartı hazır: {bible[cid]["name"]}')
    first_ok = None
    for i, s in enumerate(story['scenes']):
        path = folder / f'{i+1:02}.jpg'
        if not path.exists():
            if supplied: im = Image.open(supplied[i])
            else:
                present = [x for x in (s.get('present') or ids) if x in anchors] or list(anchors)
                chars = [bible[x] for x in present][:4]
                refs = [_png_bytes(anchors[x]) for x in present][:4]
                extra = first_ok is not None and len(refs) < 4
                if extra: refs.append(_png_bytes(first_ok))
                prompt = scene_prompt(s, chars, extra)
                best = (-1, None, []); flagged = 0; judged = 0
                for k in range(SCENE_ATTEMPTS + 2):
                    use_refs = refs[:len(chars)] if flagged else refs
                    pr = (SAFE_PREFIX + prompt) if flagged else prompt
                    try:
                        if IMAGE_PROVIDER == 'gemini':
                            cand = gemini_image_generate(pr, use_refs, IMG_W, IMG_H, model)
                        elif IMAGE_PROVIDER == 'cloudflare':
                            cand = cf_generate(pr, use_refs, SEED + i + k * 1000, IMG_W, IMG_H)
                        else:
                            raise ValueError(f'Bilinmeyen MINOMASAL_IMAGE_PROVIDER: {IMAGE_PROVIDER}')
                    except CFFlagged as e:
                        flagged += 1
                        print(f'Sahne {i+1} deneme {k+1}: içerik filtresi görseli işaretledi (yanlış alarm olabilir), farklı seed ve yumuşatılmış istemle devam: {str(e)[:80]}')
                        continue
                    judged += 1
                    score, problems = judge(cand, chars, [anchors[x] for x in present][:4], s.get('visual', ''))
                    print(f'Sahne {i+1} deneme {k+1}: puan={score} {problems}')
                    if score is None: best = (None, cand, problems); break
                    if score > (best[0] if best[0] is not None else -1): best = (score, cand, problems)
                    if score >= QC_MIN_ACCEPT or judged >= SCENE_ATTEMPTS: break
                if best[1] is None:
                    raise RuntimeError(f'Sahne {i+1}: görsel üretimi tamamlanamadı. Sahne açıklaması: {s.get("visual", "")[:160]}')
                if best[0] is not None and best[0] < QC_MIN_FLOOR:
                    raise RuntimeError(f'Sahne {i+1} kalite kontrolünden geçemedi (en iyi puan {best[0]}): {best[2]}. Video üretimi durduruldu.')
                im = best[1]; report.append({'scene': i + 1, 'score': best[0], 'problems': best[2]})
                if i == 0: first_ok = im
            ImageOps.fit(im.convert('RGB'), (1080, 1920), method=Image.Resampling.LANCZOS).save(path, quality=95)
        with Image.open(path) as im2: im2.verify()
        out.append(path); print(f'Görsel {i+1}/{len(story["scenes"])} hazır')
    if report: save_json(folder.parent / 'gorsel_kontrol.json', report)
    return out


# -------------------------------- ses --------------------------------------

def tts_scene(text):
    """Tek sahne için Gemini TTS (Interactions API). WAV baytları döner."""
    payload = {'model': TTS_MODEL,
               'input': [{'type': 'user_input', 'content': [{'type': 'text', 'text': text,
                          'annotations': [{'type': 'speech_metadata', 'style': TTS_STYLE}]}]}],
               'response_format': {'type': 'audio'},
               'generation_config': {'speech_config': [{'voice': SES}]}}
    data = gemini_post('interactions', payload, timeout=240)
    audio = None
    for step in data.get('steps', []):
        if step.get('type') == 'model_output':
            for c in step.get('content', []):
                if c.get('type') == 'audio' and c.get('data'): audio = c['data']
    if not audio: raise RuntimeError('Gemini TTS yanıtında ses verisi yok.')
    raw = base64.b64decode(audio)
    if raw[:4] != b'RIFF':        # başlıksız PCM gelirse (24 kHz, mono, 16-bit) WAV başlığı ekle
        b = io.BytesIO()
        with wave.open(b, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(raw)
        raw = b.getvalue()
    return raw


def _silences(wav):
    """ffmpeg silencedetect ile sessizlik aralıklarını (başlangıç, bitiş, süre) bulur."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(wav), '-af', 'silencedetect=noise=-38dB:d=0.18', '-f', 'null', '-'],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r'silence_start: (-?[0-9.]+)', r.stderr)]
    ends = [(float(e), float(d)) for e, d in re.findall(r'silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)', r.stderr)]
    return [(max(0.0, st), en, du) for st, (en, du) in zip(starts, ends)]


def plan_cuts(texts, total, sil):
    """Sahne sınırlarını: kelime payına göre beklenen konuma en yakın (ve uzun) sessizliğin ortasına koyar."""
    w = [max(1, len(re.sub(r'\W', '', t))) for t in texts]; tot = sum(w)
    avg = total / len(texts); cuts = []; prev = 0.0; acc = 0; fallback = 0
    for k in range(len(texts) - 1):
        acc += w[k]; exp = total * acc / tot
        lo = max(prev + 0.8, exp - 0.55 * avg); hi = exp + 0.55 * avg
        cand = [(abs((s0 + e0) / 2 - exp) - 0.4 * min(d, 1.0), (s0 + e0) / 2) for s0, e0, d in sil
                if lo <= (s0 + e0) / 2 <= hi and s0 > 0.3 and e0 < total - 0.3]
        if cand: t = min(cand)[1]
        else: t = max(exp, prev + 0.8); fallback += 1
        cuts.append(t); prev = t
    if fallback: print(f'UYARI: {fallback} sahne sınırı sessizliğe oturtulamadı, kelime payı kullanıldı.')
    return cuts


async def voices(story, folder):
    """Tüm masal TEK Gemini TTS isteğiyle seslendirilir (ücretsiz katman günde 10 istek), sonra sahnelere bölünür."""
    folder.mkdir(parents=True, exist_ok=True)
    n = len(story['scenes']); audios = [folder / f'ses_{i+1:02}.mp3' for i in range(n)]
    if not all(a.exists() for a in audios):
        texts = [s['narration'].strip() for s in story['scenes']]
        full = folder / 'ses_tam.wav'
        if not full.exists(): full.write_bytes(await asyncio.to_thread(tts_scene, '\n\n'.join(texts)))
        total = duration(full); sil = _silences(full); cuts = plan_cuts(texts, total, sil)
        bounds = [0.0] + cuts + [total]
        save_json(folder / 'ses_kesim.json', {'total': round(total, 2), 'cuts': [round(c, 2) for c in cuts], 'silences': [[round(x, 2), round(y, 2)] for x, y, _ in sil]})
        for i, a in enumerate(audios):
            run(['ffmpeg', '-y', '-loglevel', 'error', '-i', full, '-ss', f'{bounds[i]:.3f}', '-to', f'{bounds[i+1]:.3f}',
                 '-af', 'apad=pad_dur=0.2', '-codec:a', 'libmp3lame', a])
    out = []
    for i, a in enumerate(audios):
        meta = folder / f'ses_{i+1:02}.json'
        if not meta.exists(): save_json(meta, [])
        out.append((a, duration(a), json.loads(meta.read_text(encoding='utf-8'))))
        print(f'Ses {i+1}/{n} hazır ({out[-1][1]:.1f} sn)')
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
    """Bütün video boyunca tek ve kesintisiz fon müziği."""
    
    text = (
        story.get("title", "") + " " +
        story.get("moral", "") + " " +
        " ".join(s["narration"] for s in story["scenes"])
    ).lower()

    if any(w in text for w in ["kork", "üzül", "ağla", "özür", "pişman"]):
        music_name = "emotional.mp3"
    elif any(w in text for w in ["kaybol", "gizem", "merak", "araştır", "keşfet"]):
        music_name = "mystery.mp3"
    else:
        music_name = "happy.mp3"

    music_path = MUZIK_KLASORU / music_name


    if not music_path.is_file():
        raise FileNotFoundError(f"Fon müziği bulunamadı: {music_path}")

    total = sum(lengths)
    output = folder / "sinematik_muzik.wav"

    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", "-1",
        "-i", music_path,
        "-t", str(total),
        "-af", "aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo",
        "-c:a", "pcm_s16le",
        output
    ])

    print("Tek fon müziği hazır:", music_path)
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
    
    # Kapak görseli: videonun 2. saniyesi
    thumbnail = folder / "kapak_2sn.jpg"

    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", "2",
        "-i", str(final),
        "-frames:v", "1",
        "-q:v", "2",
        str(thumbnail),
    ])

    if not thumbnail.is_file() or thumbnail.stat().st_size == 0:
        raise RuntimeError("Kapak görseli oluşturulamadı.")

    return final

async def produce(topic, supplied_story=None):
    
    story = validate(supplied_story) if supplied_story else create_story(topic, API_KEY, HIKAYE_MODELI)

    from minomasal_masalsi_kopru import prepare_story_for_render
    story = prepare_story_for_render(
        story,
        supplied_story=supplied_story is not None
    )
    story.setdefault('char_ids', ids_for_topic(topic))

    identity={'story':story,'voice':SES,'rate':SES_HIZI,'image_provider':IMAGE_PROVIDER,'image_model':GORSEL_MODELI,'seed':SEED,'local':GORSel_KLASORU,'music_files':{k:hashlib.sha256((MUZIK_KLASORU / v).read_bytes()).hexdigest()[:12] if (MUZIK_KLASORU / v).is_file() else 'missing' for k,v in MUZIK_DOSYALARI.items()},'music_level':MUZIK_SEVIYESI,'sfx':SFX_KLASORU,'fps':FPS,'channel':KANAL_ADI,'engine':5}
    fingerprint=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:12]
    folder=(ROOT/fingerprint).resolve(); folder.mkdir(parents=True,exist_ok=True)
    save_json(folder/'hikaye.json',story)
    complete=folder/'tamam.json'; final=folder/'masal_short.mp4'
    if complete.exists() and final.exists() and duration(final)>1:
        print('Önceden tamamlandı:',final); return final
    audios=await voices(story,folder)
    print(f'Görsel sağlayıcı: {IMAGE_PROVIDER} | model: {GORSEL_MODELI}')
    images=make_images(story,folder/'gorseller',API_KEY,GORSEL_MODELI,GORSel_KLASORU)
    final=render(story,images,audios,folder)
    save_json(complete,{'title':story['title'],'duration':duration(final),'video':str(final)})
    print('Video hazır:',final); return final


def upload_youtube(video, title, topic):
    """Upload to YouTube with configured visibility; return video ID."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    keys = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    missing = [key for key in keys if not os.environ.get(key)]
    if missing:
        raise RuntimeError("YouTube GitHub Secrets eksik: " + ", ".join(missing))
    credentials = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    credentials.refresh(Request())
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    body = {
        "snippet": {
            "title": title[:100],
            "description": f"{topic} üzerine çocuklar için öğretici bir MinoMasal hikâyesi.\n#MinoMasal #ÇocukMasalları",
            "categoryId": "1",
        },
        "status": {"privacyStatus": YOUTUBE_GORUNURLUK, "selfDeclaredMadeForKids": True},
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    result = None
    while result is None:
        _, result = request.next_chunk()
    video_id = result.get("id") if isinstance(result, dict) else None
    if not video_id:
        raise RuntimeError("YouTube API yanıtında video ID bulunamadı; yeniden yüklemeden önce kanalı kontrol edin.")
    return video_id


async def main():
    state_file = Path("minomasal_yayin_durumu.json")
    if not state_file.is_file():
        raise RuntimeError("Yayın geçmişi JSON dosyası bulunamadı; tekrar yükleme riskinden durduruldu.")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    preview_file = Path("minomasal_onizleme_durumu.json")
    preview_state = json.loads(preview_file.read_text(encoding="utf-8")) if preview_file.exists() else {}

    if YAYIN_AKTIF:
        # Yayın modunda önizleme tamamlandı bilgisi, yayımlandı anlamına GELMEZ.
        pending = next(((i, t) for i, t in enumerate(KONULAR, 1)
                        if not state.get(str(i), {}).get("complete")
                        and not state.get(str(i), {}).get("youtube_uploaded")
                        and not preview_state.get(str(i), {}).get("youtube_uploaded")), None)
    else:
        pending = next(((i, t) for i, t in enumerate(KONULAR, 1)
                        if not state.get(str(i), {}).get("complete")
                        and not preview_state.get(str(i), {}).get("preview_complete")), None)
    if pending is None:
        print("Bekleyen hikâye yok.")
        return
    num, topic = pending
    print(f"{'YouTube yüklemesi' if YAYIN_AKTIF else 'Önizleme'}: {num}. {topic}")
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY GitHub Secret eksik.")
    video = await produce(topic)
    story = json.loads((video.parent / "hikaye.json").read_text(encoding="utf-8"))
    title = str(story.get("title") or topic).strip() + " | MinoMasal"
    if duration(video) <= 1:
        raise RuntimeError("Video geçersiz; ilerleme kaydedilmedi.")

    if YAYIN_AKTIF:
        # YouTube isteği başarılı olsa da GitHub'a durum dosyası commit edilmeden
        # iş akışı kesilirse yeniden yükleme riski vardır; workflow'da concurrency kullanın.
        video_id = upload_youtube(video, title, topic)
        state[str(num)] = {
            **state.get(str(num), {}), "topic": topic, "title": title,
            "complete": True, "youtube_uploaded": True,
            "youtube_video_id": video_id, "privacy_status": YOUTUBE_GORUNURLUK,
        }
        save_json(state_file, state)
        preview_state[str(num)] = {
            **preview_state.get(str(num), {}), "topic": topic, "title": title,
            "preview_complete": True, "youtube_uploaded": True,
            "youtube_video_id": video_id,
        }
        save_json(preview_file, preview_state)
        print("YOUTUBE YÜKLEME BAŞARILI. Görünürlük:", YOUTUBE_GORUNURLUK, "Video ID:", video_id)
    else:
        shutil.copy2(video, ROOT / "minomasal_test_video.mp4")
        (ROOT / "test_ozeti.json").write_text(json.dumps({
            "number": num, "topic": topic, "title": title,
            "video": "minomasal_test_video.mp4", "youtube_uploaded": False,
            "voice": SES, "rate": SES_HIZI,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        preview_state[str(num)] = {
            "topic": topic, "title": title, "preview_complete": True,
            "youtube_uploaded": False, "artifact_name": "minomasal-preview",
        }
        save_json(preview_file, preview_state)
        print("ÖNİZLEME TAMAMLANDI; YouTube'a yüklenmedi. Dosya:", ROOT / "minomasal_test_video.mp4")

if __name__ == "__main__":
    asyncio.run(main())
