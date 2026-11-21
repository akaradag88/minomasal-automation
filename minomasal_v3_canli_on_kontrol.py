"""MinoMasal V3 live-readiness check. Standard-library only; NEVER publishes.

Checks the *current checkout* and the next story in the actual ledger.
Its --activated flag also checks the one-line live workflow migration.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

LEDGER = Path('minomasal_platform_durumu.json')
WORKFLOW = Path('.github/workflows/minomasal-daily-live.yml')
STAGE = Path('minomasal_gunluk_kalite_stage_v3.py')
REQUIRED = (
    'minomasal.py', 'minomasal_daily_live.py',
    'minomasal_dual_publish.py', 'minomasal_ledger.py',
    'minomasal_kalite_v2.py', 'minomasal_sami_hizalama_v2.py',
    'minomasal_karakterler.json', 'requirements-minomasal.txt',
    str(STAGE), str(LEDGER), str(WORKFLOW),
)


def topics_from_source():
    tree = ast.parse(Path('minomasal.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'KONULAR'
            for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
                raise RuntimeError('KONULAR listesi gecersiz')
            return value
    raise RuntimeError('KONULAR bulunamadi')


def next_story(ledger, topics):
    if ledger.get('schema_version') != 1 or not isinstance(ledger.get('stories'), dict):
        raise RuntimeError('Yayin defterinin semasi gecersiz')
    entries = ledger['stories']
    for n in range(16, len(topics) + 1):
        row = entries.get(str(n))
        if n == 16 and row is None:
            raise RuntimeError('#16 kaydi yok; yayini durdur')
        if row is None:
            return n, topics[n - 1]
        if row.get('topic') != topics[n-1]:
            raise RuntimeError(f'#{n} kaydinda topic uyusmazligi')
        for platform, id_key in [('youtube', 'video_id'), ('instagram', 'media_id')]:
            data = row.get(platform, {})
            if data.get('status') != 'published' or not data.get(id_key):
                raise RuntimeError(
                    f'#{n} {platform}: {data.get("status")}; '
                    'cift yayina sebep olmamak icin durduruldu'
                )
    raise RuntimeError('KONULAR listesindeki butun hikayeler yayinda')


def check_story(n, topic):
    if n in (33, 34) or n < 35:
        raise RuntimeError(f'#{n} eski/ozel hikaye; yeni V3 standart yoluna giremez')
    if n == 100:
        raise RuntimeError('#100 karakter sozlugunde 5 karakterli; onay gerekiyor')
    if n in (45, 46):
        name = 'hikaye_03.json' if n == 45 else 'hikaye_04.json'
        path = Path(name)
        if not path.is_file():
            raise RuntimeError(f'#{n} onayli ozel gun hikayesi eksik: {name}')
        story = json.loads(path.read_text(encoding='utf-8'))
        if story.get('title') != topic or len(story.get('scenes', [])) != 10:
            raise RuntimeError(f'#{n} ozel gun JSON baslik/sahne kontrolu gecemedi')
        return ['ONAYLI OZEL GUN JSON'], name
    characters = json.loads(Path('minomasal_karakterler.json').read_text(encoding='utf-8'))
    keys = characters.get('story_characters_31_100', {}).get(str(n))
    if not isinstance(keys, list) or not 1 <= len(keys) <= 4:
        raise RuntimeError(f'#{n} karakter eslemesi 1-4 olmali: {keys}')
    names = []
    for key in keys:
        entry = characters.get('characters', {}).get(key)
        if not entry or not entry.get('name') or not entry.get('appearance_en'):
            raise RuntimeError(f'{key} karakter kimligi eksik')
        names.append(entry['name'])
    return names, None


def check_workflow(activated):
    source = WORKFLOW.read_text(encoding='utf-8')
    if not re.search(r"cron:\s*['\"]0 16 \* \* \*['\"]", source):
        raise RuntimeError('19:00 TR icin cron 0 16 * * * bulunamadi')
    if 'workflow_dispatch:' not in source:
        raise RuntimeError('Manuel workflow tetikleme kaydi yok')
    if 'python minomasal_dual_publish.py' not in source:
        raise RuntimeError('Mevcut YouTube/Instagram publisher adimi eksik')
    if "MINOMASAL_YOUTUBE_UPLOAD: 'false'" not in source:
        raise RuntimeError('Stage asamasinda YouTube upload false olmali')
    if "PUBLISH_ENABLED: 'true'" not in source:
        raise RuntimeError('Publisher icin mevcut yetki bayragi bulunamadi')
    active = bool(re.search(r'^\s*run:\s*python\s+minomasal_gunluk_kalite_stage_v3\.py\s*$', source, re.M))
    if activated and not active:
        raise RuntimeError('Canli workflow V3 stage komutunu kullanmiyor')
    return active


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--activated', action='store_true',
                        help='Canli workflow V3 stage komutuna gecmis olmali')
    args = parser.parse_args()
    for file in REQUIRED:
        if not Path(file).is_file():
            raise RuntimeError(f'Gerekli dosya eksik: {file}')
    stage_tree = ast.parse(STAGE.read_text(encoding='utf-8'))
    available = {n.name for n in ast.walk(stage_tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if not {'main', 'approved_special'} <= available:
        raise RuntimeError('minomasal_gunluk_kalite_stage_v3.py eksik/eski surum')
    topics = topics_from_source()
    record = json.loads(LEDGER.read_text(encoding='utf-8'))
    number, topic = next_story(record, topics)
    names, special = check_story(number, topic)
    active = check_workflow(args.activated)
    report = {
        'result': 'ready_no_publish',
        'next_story': number,
        'topic': topic,
        'characters': names,
        'approved_special_json': special,
        'live_workflow_v3_active': active,
        'publish_performed': False,
    }
    Path('minomasal_v3_canli_on_kontrol_raporu.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('ON KONTROL TAMAMLANDI. YAYIN, VIDEO URETIMI VE API CAGRISI YAPILMADI.')


if __name__ == '__main__':
    main()
