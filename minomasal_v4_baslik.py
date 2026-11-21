"""MinoMasal V4: no-network, metadata-only optional publishing titles.

Never changes KONULAR, publication ledger, video, audio, or scene files.
Only stage/metadata.json may be updated, after validating the generated story.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata

CONFIG = Path(__file__).with_name('minomasal_yayin_basliklari.json')
SPECIAL_NUMBERS = {33, 34, 45, 46}
EXPECTED_TOPICS = {
    47: 'Kaybolan Oyuncak Kamyon',
    48: 'İlk Görevine Çıkan İtfaiye Aracı',
    49: 'Sabırsız Küçük Yarış Arabası',
    50: 'Çamura Saplanan Traktör',
    52: 'Küçük Beton Mikserinin Büyük Görevi',
    55: 'Küçük Vinç ve Yüksek Kule',
    60: 'Köprü Yapan İş Makineleri',
}


def load_config(path=CONFIG):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('stories'), dict):
        raise ValueError('Başlık JSON şeması beklenen biçimde değil.')
    if {int(k) for k in data['stories']} != set(EXPECTED_TOPICS):
        raise ValueError('Başlık dosyasındaki numaralar onaylı 47/48/49/50/52/55/60 kümesiyle uyuşmuyor.')
    for key, entry in data['stories'].items():
        number = int(key)
        if number in SPECIAL_NUMBERS or not 47 <= number <= 60:
            raise ValueError(f'Özel veya kapsam dışı hikâye: #{number}')
        if entry.get('topic') != EXPECTED_TOPICS[number]:
            raise ValueError(f'#{number}: KONULAR başlığı değiştirilmiş.')
        title = entry.get('publish_title', '')
        if not isinstance(title, str) or not title.endswith(' | MinoMasal') or len(title) > 100:
            raise ValueError(f'#{number}: yayın başlığı eksik/uzun/uyumsuz.')
        if not isinstance(entry.get('editorial_hint'), str) or not entry['editorial_hint'].strip():
            raise ValueError(f'#{number}: giriş yönergesi eksik.')
        groups = entry.get('required_terms')
        if not isinstance(groups, list) or not groups or any(
            not isinstance(g, list) or not g or any(not isinstance(w, str) or not w for w in g)
            for g in groups
        ):
            raise ValueError(f'#{number}: içerik doğrulama koşulları hatalı.')
    if 'kepçe' in data['stories']['60']['publish_title'].casefold() or 'kamyon' in data['stories']['60']['publish_title'].casefold():
        raise ValueError('#60 sözlüğünde kepçe veya kamyon bulunmuyor.')
    return data


def topics_from_minomasal(path='minomasal.py'):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'KONULAR'
            for target in node.targets
        ):
            topics = ast.literal_eval(node.value)
            if not isinstance(topics, (tuple, list)):
                raise ValueError('KONULAR dizisi geçersiz.')
            return topics
    raise ValueError('KONULAR listesi bulunamadı.')


def preflight(config_path=CONFIG, topics_path='minomasal.py', characters_path='minomasal_karakterler.json'):
    data = load_config(config_path)
    topics = topics_from_minomasal(topics_path)
    chars = json.loads(Path(characters_path).read_text(encoding='utf-8'))
    for key, item in data['stories'].items():
        n = int(key)
        if len(topics) < n or topics[n - 1] != item['topic']:
            raise ValueError(f'#{n} konusu mevcut KONULAR ile uyuşmuyor.')
        cast = chars.get('story_characters_31_100', {}).get(key, [])
        if not cast or len(cast) > 4 or any(x not in chars['characters'] for x in cast):
            raise ValueError(f'#{n} karakter sözlüğü eksik ya da kurala aykırı.')
    if set(chars['story_characters_31_100']['60']) != {'traktor', 'vinc', 'beton_mikseri', 'cekici'}:
        raise ValueError('#60 karakter sözlüğü beklenenden farklı; otomatik başlık kullanılmasın.')
    return data


def normalize(s):
    s = str(s).replace('İ', 'i').replace('I', 'ı').casefold()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    return s.replace('ı', 'i')


def text_supports_title(story, entry):
    if not story or not isinstance(story.get('scenes'), list) or len(story['scenes']) != 10:
        return False
    content = normalize(' '.join(
        str(s.get('narration', '')) + ' ' + str(s.get('visual', ''))
        for s in story['scenes']
    ))
    return all(any(normalize(term) in content for term in group) for group in entry['required_terms'])


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def find_matching_story(root, stage_video, old_title):
    """Locate the EXACT produced MP4's story JSON; never guess a story from filename alone."""
    root, stage_video = Path(root), Path(stage_video)
    if not root.is_dir() or not stage_video.is_file():
        return None
    target = sha256(stage_video)
    found = []
    for video in root.glob('*/masal_short.mp4'):
        if sha256(video) != target:
            continue
        story_path = video.parent / 'hikaye.json'
        if story_path.is_file():
            story = json.loads(story_path.read_text(encoding='utf-8'))
            if str(story.get('title', '')).strip() + ' | MinoMasal' == old_title:
                found.append(story)
    return found[0] if len(found) == 1 else None


def apply_title(stage_dir='staging', number=None, story=None, config_path=CONFIG, topics=None):
    """Returns 'applied', 'skipped', or 'not_configured'; never touches ledger or media."""
    config = load_config(config_path)
    stage_dir = Path(stage_dir)
    meta_path = stage_dir / 'metadata.json'
    metadata = json.loads(meta_path.read_text(encoding='utf-8'))
    number = int(number if number is not None else metadata['number'])
    if number != metadata.get('number'):
        raise ValueError('Workflow numarası ile staging numarası uyuşmuyor.')
    if topics is None:
        topics = topics_from_minomasal()
    if number <= 0 or number > len(topics) or metadata.get('topic') != topics[number - 1]:
        raise ValueError('Staging topic, KONULAR ile uyuşmuyor. Yayın engellendi.')
    if number in SPECIAL_NUMBERS or str(number) not in config['stories']:
        print(f'V4: #{number} özel gün/kapsam dışı, metadata değiştirilmedi.')
        return 'not_configured'
    entry = config['stories'][str(number)]
    if entry['topic'] != metadata['topic']:
        raise ValueError('Onaylı konu eşleşmiyor.')
    if metadata.get('mode') != 'quality_v3_staging':
        raise ValueError('Bu adım yalnızca onaylı quality_v3_staging formatını işler.')
    video = stage_dir / 'masal_short.mp4'
    if not video.is_file() or video.stat().st_size == 0:
        raise ValueError('Staging videosu bulunamadı.')
    if story is None:
        # Fresh Actions runner'da tek üretilmiş video beklenir.
        story = find_matching_story('minomasal_kalite_v3_daily_data', video, metadata['title'])
    if not text_supports_title(story, entry):
        print(f'V4: #{number} hikâye yeni başlığı doğrulamadı; mevcut yayın başlığı korunuyor.')
        return 'skipped'
    if metadata['title'] == entry['publish_title']:
        return 'applied'
    metadata['title'] = entry['publish_title']
    tmp = meta_path.with_name('metadata.json.v4.tmp')
    try:
        tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(tmp, meta_path)
    finally:
        tmp.unlink(missing_ok=True)
    print(f'V4: #{number} onaylı yayın başlığı uygulandı: {metadata["title"]}')
    return 'applied'
