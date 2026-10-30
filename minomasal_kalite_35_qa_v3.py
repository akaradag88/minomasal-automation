"""MinoMasal2 - Story 35+ read-only preflight and opt-in video QA.

NEVER uploads or edits publication history. --render is explicitly opt-in.
Production is intentionally NOT activated by this file.
"""
import argparse
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path

LEDGER = Path('minomasal_platform_durumu.json')
REPORT = Path('minomasal_kalite_v3_qa_rapor.json')
STATE_FILES = (
    LEDGER,
    Path('minomasal_yayin_durumu.json'),
    Path('minomasal_onizleme_durumu.json'),
    Path('minomasal_facebook_durumu.json'),
)
APPROVED_SPECIAL = {33, 34, 45, 46}
QA_ROOT = Path('minomasal_kalite_v3_qa_data')


def get_topics():
    tree = ast.parse(Path('minomasal.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'KONULAR'
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError('minomasal.py icinde KONULAR bulunamadi.')


def digest_states():
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in STATE_FILES if path.is_file()
    }


def inspect_next(topics):
    data = json.loads(LEDGER.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise RuntimeError('Yayin defterinin semasi gecersiz.')
    rows = data.get('stories')
    if not isinstance(rows, dict):
        raise RuntimeError('Yayin defterinde stories alani eksik.')
    for number in range(16, len(topics) + 1):
        row = rows.get(str(number))
        if number == 16 and row is None:
            raise RuntimeError('#16 kaydi eksik; otomatik yayina gecme.')
        if row is None:
            return number, topics[number - 1]
        if row.get('topic') != topics[number - 1]:
            raise RuntimeError(f'#{number}: topic ile KONULAR uyusmuyor.')
        for platform, id_key in [('youtube', 'video_id'), ('instagram', 'media_id')]:
            platform_row = row.get(platform, {})
            if platform_row.get('status') != 'published' or not platform_row.get(id_key):
                raise RuntimeError(
                    f'#{number} {platform}: durum {platform_row.get("status")!r}; '
                    'mukerrer yayini onlemek icin durduruldu.'
                )
    return None, None


def verify_local_files(number, topics):
    required = ['minomasal.py', 'minomasal_kalite_v2.py',
                'minomasal_sami_hizalama_v2.py', 'minomasal_karakterler.json',
                'minomasal_daily_live.py', 'requirements-minomasal.txt']
    for name in required:
        if not Path(name).is_file():
            raise RuntimeError(f'Eksik dosya: {name}')
    for script, functions in {
        'minomasal_kalite_v2.py': ('create_story_v2', 'verify_and_enrich'),
        'minomasal_sami_hizalama_v2.py': ('aligned_scene_voices', '_timestamp_words'),
        'minomasal.py': ('produce', 'render'),
    }.items():
        tree = ast.parse(Path(script).read_text(encoding='utf-8'))
        available = {n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        missing = set(functions) - available
        if missing:
            raise RuntimeError(f'{script}: eksik fonksiyonlar: {sorted(missing)}')
    if number is None:
        raise RuntimeError('Yayinlanacak yeni hikaye kalmadi.')
    if number in (33, 34):
        raise RuntimeError('Onayli 33/34 icin yeniden otomatik hikaye olusturma yasak.')
    if number in (45, 46):
        raise RuntimeError(f'#{number} ozel gun; onayli JSON kullanilmali.')
    if number == 100:
        raise RuntimeError('#100 bes karakterli; ayri onay gerekli.')
    if not 35 <= number <= 99:
        raise RuntimeError(f'#{number}: bu test 35-99 arasi standart hikayeler icin.')
    data = json.loads(Path('minomasal_karakterler.json').read_text(encoding='utf-8'))
    keys = data['story_characters_31_100'].get(str(number))
    if not keys or len(keys) > 4:
        raise RuntimeError(f'#{number}: izinli karakter sayisi 1-4 olmali; mevcut {keys}')
    names = []
    for key in keys:
        entry = data['characters'].get(key)
        if not entry or not entry.get('name') or not entry.get('appearance_en'):
            raise RuntimeError(f'Karakter tanimi eksik: {key}')
        names.append(entry['name'])
    return names


async def render_preview(number, topic):
    if os.environ.get('MINOMASAL_YOUTUBE_UPLOAD', 'false').lower() != 'false':
        raise RuntimeError('Yayin bayragi kapali olmali.')
    if os.environ.get('PUBLISH_ENABLED', 'false').lower() == 'true':
        raise RuntimeError('PUBLISH_ENABLED=true iken test yapilmaz.')
    if os.environ.get('MINOMASAL_30SN_TEST', 'false').lower() != 'false':
        raise RuntimeError('Normal hikaye testi icin 30sn bayragi kapali olmali.')

    import minomasal as mm
    from minomasal_kalite_v2 import create_story_v2
    from minomasal_sami_hizalama_v2 import aligned_scene_voices
    if mm.KONULAR[number-1] != topic:
        raise RuntimeError('Hikaye numarasi ile baslik uyusmuyor.')
    mm.create_story = lambda t, key, model: create_story_v2(t, key, model, mm.KONULAR)
    mm.voices = aligned_scene_voices
    mm.ROOT = QA_ROOT.resolve()  # eski gunluk/pilot onbelleklerinden ayri
    mm.ROOT.mkdir(parents=True, exist_ok=True)
    video = await mm.produce(topic)
    if not video.is_file() or mm.duration(video) <= 1:
        raise RuntimeError('Video eksik/gecersiz.')
    story_path = video.parent / 'hikaye.json'
    story = json.loads(story_path.read_text(encoding='utf-8'))
    words = sum(len(s['narration'].split()) for s in story['scenes'])
    if len(story['scenes']) != 10 or not 75 <= words <= 110:
        raise RuntimeError(f'Video kalitesi: {len(story["scenes"])} sahne / {words} kelime')
    subtitle = video.parent / 'altyazi.srt'
    if not subtitle.is_file() or not subtitle.read_text(encoding='utf-8').strip():
        raise RuntimeError('Altyazi eksik/bos.')
    print('YAYINSIZ VIDEO HAZIR:', video, flush=True)
    print('Sahne:', len(story['scenes']), 'Kelime:', words,
          'Sure:', round(mm.duration(video), 2), flush=True)
    return {'video': str(video), 'story_json': str(story_path),
            'subtitles': str(subtitle), 'words': words,
            'duration_seconds': round(mm.duration(video), 2)}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true',
                        help='Gercek API ile yayinsiz MP4 uret; varsayilan sadece on kontrol.')
    args = parser.parse_args()
    before = digest_states()
    topics = get_topics()
    number, topic = inspect_next(topics)
    names = verify_local_files(number, topics)
    print(f'YAYINSIZ ON KONTROL: sıradaki #{number}: {topic}')
    print('Onayli karakterler:', ', '.join(names))
    print('10 sahne; 75-110 kelime; Sami tek istek; hizalamali altyazi')
    report = {'result': 'preflight_passed', 'next_story': number,
              'topic': topic, 'approved_characters': names,
              'published': False, 'render_requested': args.render}
    if args.render:
        report.update(await render_preview(number, topic))
        report['result'] = 'video_created_without_publish'
    if digest_states() != before:
        raise RuntimeError('Yayin durumu dosyasi degismis! Kontrol basarisiz.')
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8')
    print('BASARILI:', report['result'])
    print('YAYIN YAPILMADI. YAYIN DEFTERI DEGISTIRILMEDI.')


if __name__ == '__main__':
    asyncio.run(main())
