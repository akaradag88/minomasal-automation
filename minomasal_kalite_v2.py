"""MinoMasal2: karakter sozlugune bagli, yayin yapmayan hikaye olusturucusu.

Onaylanmis JSON hikayelerini veya mevcut gunluk yayin dosyalarini DEGISTIRMEZ.
Gorevi: yeni uretilecek masallarda sinirli oyuncu kadrosu + sabit gorunum.
"""
import json
from pathlib import Path
import re
import unicodedata
import requests

CHARACTERS_JSON = Path(__file__).with_name('minomasal_karakterler.json')
PRESERVE_APPROVED = {33, 34, 45, 46}


def number_for_topic(topic, all_topics):
    try:
        return all_topics.index(topic) + 1
    except ValueError as exc:
        raise ValueError(f"Hikaye numarasi bulunamadi: {topic!r}") from exc


def _norm(s):
    s = str(s).replace('İ', 'i').replace('I', 'ı').casefold()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    return s.replace('ı', 'i')


def dictionary_entry(topic, all_topics):
    data = json.loads(CHARACTERS_JSON.read_text(encoding='utf-8'))
    number = number_for_topic(topic, all_topics)
    keys = data.get('story_characters_31_100', {}).get(str(number))
    if not keys:
        # 1-30 icin onayli karakter eslemesi henuz yok.
        return number, [], data
    if len(keys) > 4:
        raise ValueError(
            f'{number}. hikaye sozlukte {len(keys)} karakter iceriyor. '
            'En cok 4 kuralina aykiri: mevcut sozluk degistirilmedi; kontrol gerekli.'
        )
    cast = []
    for key in keys:
        if key not in data['characters']:
            raise ValueError(f'Karakter sozlugunde {key!r} tanimsiz.')
        cast.append((key, data['characters'][key]))
    return number, cast, data


def prompt_rules(topic, all_topics):
    number, cast, _ = dictionary_entry(topic, all_topics)
    parts = [
        'KESIN GORSEL KADRO KURALI: Masalda en fazla 4 adlandirilmis karakter; tercihen 1-2 karakter.',
        'Her sahnede 1 veya 2 gorunen karakter olsun. Gereksiz figuran, kalabalik, ekstra hayvan, gorunmeyen yeni isim ekleme.',
        'Ana karakterin sabit turunu, adini, govdesini, renklerini, aksesuarlarini butun sahnelerde koru.',
        'Anlatilan olay ile English visual tasviri tam ayni olsun. Her sahnede tek ana eylem.',
        '10 sahne, toplam 100-130 Turkce narration kelimesi. Her sahnede kisa ve kolay anlasilir metin.',
        'Her sahne icin sadece gercekte gorunecek karakterleri ve eylemi visual icinde tarif et.',
    ]
    if cast:
        text = ' | '.join(
            f'{c["name"]} ({c["type_tr"]}): {c["appearance_en"]}' for _, c in cast
        )
        parts += [
            'TEK IZINLI ADLANDIRILMIS KARAKTER KADROSU: ' + text,
            'Bu isimleri birebir kullan. Tur, isim veya kiyafet degistirme. Baska isim veya yan karakter uydurma.',
            'Bu karakterlerin isimleri narration metninde en az bir kez dogru gecsin.',
        ]
    else:
        parts += [
            f'{number}. hikayenin karakter sozlugunde henuz sabit eslemesi yok. '
            'Bu pilotta yeni karakter isimleri uretme; yalnizca konu icindeki karakter tanimlarini kullan.'
        ]
    return '\n'.join(parts)


def verify_and_enrich(story, topic, all_topics):
    """Sadece uretilmis yeni hikayeyi dogrula; canonical JSON dosyasini degistirme."""
    number, cast, _ = dictionary_entry(topic, all_topics)
    scenes = story.get('scenes')
    if not isinstance(scenes, list) or len(scenes) != 10:
        raise ValueError(f'10 sahne bekleniyor; {len(scenes) if isinstance(scenes,list) else "sahne yok"}.')
    total_words = sum(len(s['narration'].split()) for s in scenes)
    if not 100 <= total_words <= 130:
        raise ValueError(f'100-130 kelime bekleniyor; bulunan {total_words}.')
    for idx, scene in enumerate(scenes, 1):
        if not isinstance(scene.get('narration'), str) or not isinstance(scene.get('visual'), str):
            raise ValueError(f'{idx}. sahnede narration veya visual eksik.')
        if not scene['narration'].strip() or not scene['visual'].strip():
            raise ValueError(f'{idx}. sahnede bos narration veya visual.')
    if not cast:
        # 1-30 icin dogrudan character guard garantisi yok.
        raise ValueError(
            f'{number}. hikaye icin onayli karakter eslemesi bulunamadi. '
            'Karaktersiz otomatik videoya izin verilmedi; sozluk genisletilmeli.'
        )
    narrative = ' '.join(s['narration'] for s in scenes)
    for key, char in cast:
        if not re.search(r'(?<!\w)' + re.escape(_norm(char['name'])) + r'(?!\w)', _norm(narrative)):
            raise ValueError(f'Onayli {key} karakterinin adi ({char["name"]}) narration icinde yok.')
    # Harici karakter ismi icin bilinen karakter adlari kontrol edilir.
    # Tumu yakalayamaz: ek karakter uydurulmasi ayrica goruntu QA ile kontrol edilmeli.
    # "Damla", "Ruzgar" gibi ayni zamanda ortak kelime olabilecek adlarda yanlis alarm olmasin.
    reserved = {'damla', 'ruzgâr', 'rüzgâr', 'şifa', 'efe', 'mert', 'lina'}
    allowed = {_norm(char['name']) for _, char in cast}
    # Metin basligi ve gorsellerde yeni karakter adi uretilmesine engel olmak icin
    # sozlukteki bilinen adlar icinden riskli olmayanlari yakala.
    known = json.loads(CHARACTERS_JSON.read_text(encoding='utf-8'))['characters']
    for c in known.values():
        candidate = _norm(c['name'])
        if candidate in allowed or _norm(c['name']) in {_norm(x) for x in reserved}:
            continue
        if re.search(r'(?<!\w)' + re.escape(candidate) + r'(?!\w)', _norm(narrative)):
            raise ValueError(f'Beklenmeyen sozluk karakteri adi tespit edildi: {c["name"]}')
    story = dict(story)
    # mm.make_images, 'characters' metnini HER sahne promptuna ekler.
    # Bu nedenle burada yalnizca ANA karakter vardir; yardimcilar
    # ilgili sahnenin 'visual' metnine eklenir.
    main = cast[0][1]
    story['characters'] = f'{main["name"]}: {main["appearance_en"]}'
    enriched = []
    for scene in scenes:
        sc = dict(scene)
        # Ana karakterin tam tanimini her sahnede sabitle;
        # yardimcilari yalnizca o sahnede adi geciyorsa tarif et.
        current_names = []
        for i, (_, char) in enumerate(cast):
            name = char['name']
            if i == 0 or re.search(r'(?<!\w)' + re.escape(_norm(name)) + r'(?!\w)', _norm(sc['narration'] + ' ' + sc['visual'])):
                current_names.append(char)
        if len(current_names) > 2:
            raise ValueError('Bir sahnede 2 karakterden fazlasi referanslandi; sahne duzenlenmeli.')
        appearance = ' '.join(
            f'{c["name"]} MUST look exactly like: {c["appearance_en"]}' for c in current_names
        )
        sc['visual'] = sc['visual'].strip().rstrip('.') + '. ' + appearance + ' Exactly these visible characters, no crowd, no extra animals, no text.'
        enriched.append(sc)
    story['scenes'] = enriched
    return story


def create_story_v2(topic, key, model, all_topics):
    """Yalnizca yeni hikaye icin; tek Pollinations istegi kullanir."""
    number, cast, _ = dictionary_entry(topic, all_topics)
    if number in PRESERVE_APPROVED:
        raise ValueError(
            f'{number}. ozel gun hikayesi korunuyor. '
            'Yeni otomatik onizleme yerine onayli JSON akisi kullanilmali.'
        )
    if not cast:
        raise ValueError(f'{number}. hikaye icin onayli karakter eslemesi yok; API cagrisi yapilmadi.')
    if not key:
        raise RuntimeError('POLLINATIONS_API_KEY bulunamadi.')
    prompt = f'''4-8 yas cocuklar icin Turkce, ogretici ve sicak bir masal yaz. Konu: {topic}.
{prompt_rules(topic, all_topics)}
Tek somut ders anlat. Korku, siddet, tehlikeli davranis, urun/abone ol cagrisi kullanma.
Diyaloglari az tut, cocugun anlayacagi akici masalsi anlatim kur.
Yalnizca JSON nesnesi dondur:
{{"title":"Turkce baslik", "moral":"kisa ders", "characters":"cast appearance", "scenes":[{{"narration":"Turkce metin", "visual":"English scene description", "sfx":"none"}}]}}
JSON metnini vermeden once 10 sahne ve toplam 100-130 narration kelimesi kontrolunu yap.'''
    r = requests.post(
        'https://gen.pollinations.ai/v1/chat/completions',
        headers={'Authorization':'Bearer ' + key},
        json={'model': model, 'messages': [{'role':'user','content':prompt}], 'response_format':{'type':'json_object'}},
        timeout=150,
    )
    if r.status_code != 200:
        raise RuntimeError(f'Hikaye servisi HTTP {r.status_code}.')
    text = r.json()['choices'][0]['message']['content']
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    story = json.loads(text)
    return verify_and_enrich(story, topic, all_topics)
