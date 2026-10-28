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

# Sahne resimlerinde en sık karışan somut nesnelerin sözlüğü.
# Türkçe anlatımda geçen nesne İngilizce visual içinde somut olarak bulunmalı.
# Dar tutuldu: soyut sözcükleri/eylemleri yanlışlıkla nesne saymayalım.
SCENE_OBJECTS = (
    ("taş", r"\btas(?:i|a|ta|tan|lar|lari|larla|in|ini)?\b", r"\b(?:rock|rocks|stone|stones|boulder|boulders|pebble|pebbles)\b"),
    ("kütük", r"\b(?:kutug(?:u|un|e|de|den)?|kutuk(?:ler|leri|lere|lerin|lerle)?)\b", r"\b(?:log|logs|fallen tree trunk|wooden trunk)\b"),
    ("köprü", r"\bkopru(?:yu|nun|ye|de|den|ler|leri)?\b", r"\b(?:bridge|bridges|footbridge)\b"),
    ("ip", r"\bip(?:i|in|e|le|ten|ler|leri)?\b", r"\b(?:rope|ropes|string|strings|cord|cords)\b"),
    ("balon", r"\bbalon(?:u|un|a|da|dan|lar|lari)?\b", r"\b(?:balloon|balloons)\b"),
    ("yıldız", r"\byildiz(?:i|in|a|da|dan|lar|lari)?\b", r"\b(?:star|stars|starlight)\b"),
    ("çiçek", r"\b(?:ciceg(?:i|in|e|de|den)?|cicek(?:ler|leri|lere|lerin|lerle)?)\b", r"\b(?:flower|flowers|blossom|blossoms)\b"),
    ("kitap", r"\b(?:kitab(?:i|in|a|da|dan)?|kitap(?:lar|lari|lara|larin|larla)?)\b", r"\b(?:book|books|storybook|storybooks)\b"),
)


def validate_scene_object_match(narration, visual, scene_number):
    """Güvenilir somut nesne eşleşmesi; görüntüdeki gerçek nesneyi garanti etmez."""
    tr_text, en_text = _norm(narration), _norm(visual)
    for label, tr_regex, en_regex in SCENE_OBJECTS:
        if re.search(tr_regex, tr_text) and not re.search(en_regex, en_text):
            raise ValueError(
                f"{scene_number}. sahne: anlatımda '{label}' var, ancak İngilizce visual "
                f"bu nesneyi tanımlamıyor. Görseli olayla eşleştir."
            )



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
        'Sahne nesnelerini ASLA DEGISTIRME: narration tas diyorsa rock/stone; kutuk diyorsa log; kopru diyorsa bridge yaz.',
        'English visual icinde gorunen KIM, NE YAPIYOR, HANGI SOMUT NESNEYLE, NEREDE ve NASIL KADRAJLANMIS acikca yaz.',
        'English visual en az 20 civari anlamli kelimeyle belirgin eylem, somut nesne ve mekan tarif et; sadece ruh hali ve atmosfer yazma.',
        'Gorunmeyen olaylari resme koyma; anlatimda olmayan kütük, tas, canli, esya, kiyafet veya yeni hareket uydurma.',
        '10 sahne, toplam 75-110 Turkce narration kelimesi. Akici bir hikaye icin tercihen 85-95 kelime hedefle.',
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
    for idx, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise ValueError(f'{idx}. sahne nesnesi JSON object olmali.')
        if not isinstance(scene.get('narration'), str) or not isinstance(scene.get('visual'), str):
            raise ValueError(f'{idx}. sahnede narration veya visual eksik.')
        if not scene['narration'].strip() or not scene['visual'].strip():
            raise ValueError(f'{idx}. sahnede bos narration veya visual.')
        validate_scene_object_match(scene['narration'], scene['visual'], idx)
    total_words = sum(len(s['narration'].split()) for s in scenes)
    if not 75 <= total_words <= 110:
        raise ValueError(f'75-110 kelime bekleniyor; bulunan {total_words}.')
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
        # Sözlükte fil Edi için fildişi yok; AI'nin kendiliğinden eklemesini yasakla.
        # Narration/visual içinde açıkça fildişi isteniyorsa kontrollü biçimde dur.
        if any(c['name'] == 'Edi' for c in current_names):
            if re.search(r'\btusks?\b', sc['visual'], re.I) and not re.search(
                r'\b(?:no|without|zero)\s+tusks?\b|\btuskless\b', sc['visual'], re.I
            ):
                raise ValueError('Edi: visual sözlükte olmayan fildişi ekliyor; görünüşü sabitle.')
            appearance += ' Edi has NO tusks; keep his blue vest, light-gray body, large pink-inner ears and short trunk unchanged.'
        sc['visual'] = (
            sc['visual'].strip().rstrip('.') + '. '
            + appearance
            + ' Literal match to the narrated physical action and objects. '
              'One clear foreground action, consistent anatomy and accessories. '
              'Exactly these visible characters, no crowd, no extra animals, no text.'
        )
        enriched.append(sc)
    story['scenes'] = enriched
    return story


def create_story_v2(topic, key, model, all_topics):
    """Yeni hikaye olustur; kalite hatalarinda en fazla iki kez onarmayi dene.

    Sadece yayinSIZ Adim 7 testinde kullanilir. Seslendirme ve video
    ancak verify_and_enrich basariliysa baslar. Onayli JSON'lari degistirmez.
    """
    number, cast, _ = dictionary_entry(topic, all_topics)
    if number in PRESERVE_APPROVED:
        raise ValueError(
            f'{number}. ozel gun hikayesi korunuyor. '
            'Yeni otomatik onizleme yerine onayli JSON akisi kullanilmali.'
        )
    if not cast:
        raise ValueError(
            f'{number}. hikaye icin onayli karakter eslemesi yok; API cagrisi yapilmadi.'
        )
    if not key:
        raise RuntimeError('POLLINATIONS_API_KEY bulunamadi.')

    # 10 sahnede 80-100 kelimeyi hedefle; kalite kapisi 75-110 kelimeyi kabul eder.
    # Asiri katı sahne-basi uzunluk kuralı yerine akiciliga oncelik ver.
    base_prompt = f"""4-8 yas cocuklar icin Turkce, ogretici, sicak bir masal yaz.
Konu: {topic}.
{prompt_rules(topic, all_topics)}
KESIN SAYISAL KURAL:
- Tam 10 scenes nesnesi olustur.
- Her sahnede genellikle 8-10 Turkce kelime kullan; anlatimin akici olmasi oncelikli.
- Toplam narration kelime sayisi tercihen 85-95; KABUL ARALIGI 75-110.
- Kelimeler boslukla ayrilir; title, moral ve visual kelime hesabina girmez.
- Her sahnede anlami olan akici 1-2 cumle yaz; sirf uzunluk icin
  tekrarlama veya dolgu cumlesi ekleme.
- Ilk sahnede merak uyandir, sonraki sahnelerde sebep-sonuc kur,
  sonunda cocuk icin basit bir dusunme sorusu sor.
Tek somut ders anlat. Korku, siddet, tehlikeli davranis, urun/abone ol cagrisi kullanma.
Diyaloglari az tut. Yalnizca bu masalin onayli kadrosundaki isimleri kullan.
YALNIZCA JSON nesnesi dondur:
{{"title":"Turkce baslik","moral":"kisa ders","characters":"cast appearance","scenes":[{{"narration":"yaklasik 8-10 Turkce kelime","visual":"English scene description","sfx":"none"}}]}}
JSON'u vermeden once 10 sahnenin kelimelerini say. Ayrica her narration ile English visual icindeki nesneleri tek tek karsilastir: tas=rock, kutuk=log, kopru=bridge, ip=rope, balon=balloon, yildiz=star, cicek=flower, kitap=book. Birbirinin yerine baska nesne koyma."""

    # Once tum JSON'u olustur; uzunluk hatasinda sadece Turkce narration'lari
    # kontrollu olarak yenile. Boylece resim komutlari/karakter kimligi korunsun.
    last_problem = None
    previous_story = None
    last_length_issue = False
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        repairing_length = (
            attempt > 1
            and last_length_issue
            and isinstance(previous_story, dict)
            and isinstance(previous_story.get('scenes'), list)
            and len(previous_story['scenes']) == 10
        )

        if repairing_length:
            # Kisa ve tek isli istem: yeniden tum hikayeyi/gorselleri uretme.
            # JSON'un sadece 10 Turkce narration metni isteniyor.
            source_scenes = [
                {
                    'scene': i,
                    'narration': scene.get('narration', ''),
                    'visual': scene.get('visual', ''),
                }
                for i, scene in enumerate(previous_story['scenes'], 1)
            ]
            current_total = sum(len(x['narration'].split()) for x in source_scenes)
            print(f'Anlatim duzeltmesi: mevcut {current_total} kelime, hedef 85-95.', flush=True)
            prompt = f"""GOREV: Asagidaki 10 sahnenin YALNIZCA Turkce narration metinlerini
kisaltilmis/uzatilmis ama dogal bir cocuk masali olacak sekilde duzenle.
Mevcut toplam: {current_total} kelime. KESIN kabul araligi 75-110,
HEDEF toplam 85-95 kelime. Her sahne 8-10 kelime hedeflesin.
Tam 10 metin dondur, sahnelerin sirasi degismeyecek.

Sabit kurallar:
- Her sahnenin olayini, eylemini ve 'visual' icindeki somut nesnelerini aynen koru.
- Yeni karakter, isim, nesne, eylem veya olay uydurma.
- Karakter adlarini aynen koru; son sahnedeki cocuga soruyu koru.
- Dogal, anlamli, tam cumleler yaz; kelimeleri ortadan kesme.
- Ingilizce 'visual' alanlari yeniden yazilmayacak; bu metinler onlarla uyumlu kalmali.
- Aciklama, numara veya markdown yazma.
SADECE su JSON sekli: {{"narrations":["1. sahne metni","2. sahne metni", ... 10 metin]}}

MEVCUT SAHNELER:
{json.dumps(source_scenes, ensure_ascii=False)}"""
        elif attempt > 1 and previous_story is not None:
            prompt = (
                base_prompt
                + '\n\nONCEKI HIKAYE KALITE KONTROLUNDEN GECMEDI: '
                + str(last_problem)
                + '\nOlay mantigini ve onayli karakterleri koru; butun sahneleri '
                  've English visual tasvirlerini kurala uygun yeniden yaz.\n'
                + json.dumps(previous_story, ensure_ascii=False)
            )
        else:
            prompt = base_prompt

        print(
            f'Hikaye kalite denemesi {attempt}/{max_attempts}: '
            + ('yalniz anlatim duzeltmesi' if repairing_length else 'hikaye olusturma'),
            flush=True,
        )
        r = requests.post(
            'https://gen.pollinations.ai/v1/chat/completions',
            headers={'Authorization': 'Bearer ' + key},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'response_format': {'type': 'json_object'},
            },
            timeout=150,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f'Hikaye servisi HTTP {r.status_code}; kota veya servis durumunu kontrol edin.'
            )

        try:
            content = r.json()['choices'][0]['message']['content']
            content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip())
            answer = json.loads(content)
            if not isinstance(answer, dict):
                raise ValueError('JSON nesnesi bekleniyordu.')

            if repairing_length:
                narrations = answer.get('narrations')
                if not (isinstance(narrations, list)
                        and len(narrations) == 10
                        and all(isinstance(x, str) and x.strip() for x in narrations)):
                    raise ValueError('Duzeltme 10 narration metni icermiyor.')
                # Orijinal gorselleri ve karakterleri aynen koru.
                import copy
                candidate = copy.deepcopy(previous_story)
                for scene, text_value in zip(candidate['scenes'], narrations):
                    scene['narration'] = text_value.strip()
                previous_story = candidate
            else:
                if 'scenes' not in answer:
                    raise ValueError('Hikaye yanitinda scenes bulunamadi.')
                previous_story = answer

            scenes = previous_story['scenes']
            if not isinstance(scenes, list):
                raise ValueError('scenes bir liste olmali.')
            lengths = [
                len(scene.get('narration', '').split())
                for scene in scenes if isinstance(scene, dict)
            ]
            total = sum(lengths)
            print(f'Sahne kelimeleri: {lengths}; toplam: {total}', flush=True)
            if not 75 <= total <= 110:
                last_length_issue = True
                last_problem = ValueError(f'75-110 kelime bekleniyor; bulunan {total}.')
                print(f'Hikaye kalite denemesi {attempt} basarisiz: {last_problem}', flush=True)
                continue

            last_length_issue = False
            valid_story = verify_and_enrich(previous_story, topic, all_topics)
            print(f'Hikaye kalite kontrolu BASARILI (deneme {attempt}).', flush=True)
            return valid_story
        except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
            last_problem = exc
            # Bozuk veya kontrolu gecmeyen bir tam JSON, bir sonraki denemede
            # yeniden yazilir. Yanlis metni otomatik kesip video uretmeyiz.
            last_length_issue = False
            print(f'Hikaye kalite denemesi {attempt} basarisiz: {exc}', flush=True)

    raise RuntimeError(
        f'Hikaye {max_attempts} denemede kalite kontrolunu gecemedi. '
        f'Son hata: {last_problem}. Seslendirme ve yayin baslatilmadi.'
    )
