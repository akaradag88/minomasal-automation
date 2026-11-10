"""Offline production evidence and fail-closed publication checks."""
import hashlib
import json
import subprocess
from pathlib import Path


def ensure_allowed_topic(topic):
    from minomasal import KONULAR
    from minomasal_ledger import read, LEDGER
    row = read(LEDGER)['stories'].get(str(KONULAR.index(topic) + 1), {})
    if row.get('status') == 'skipped':
        raise RuntimeError('Atlanan hikâye yeniden üretilemez veya yayımlanamaz.')


def validate_video(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError('MP4 eksik veya boş.')
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True)
    try:
        info = json.loads(result.stdout)
        kinds = {s['codec_type'] for s in info['streams']}
        good = result.returncode == 0 and {'video', 'audio'} <= kinds and float(info['format']['duration']) > 1
    except (ValueError, KeyError, TypeError):
        good = False
    if not good:
        raise RuntimeError('MP4 ses/video doğrulaması başarısız.')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                              '-f', 'null', '-'], capture_output=True)
    if decoded.returncode:
        raise RuntimeError('MP4 çözümlenemiyor; yayın engellendi.')


def validate_inputs(story, images, audios):
    from minomasal import validate, duration
    from PIL import Image
    validate(story)
    count = len(story['scenes'])
    if len(images) != count or len(audios) != count:
        raise RuntimeError('Eksik görsel/ses/sahne; yayın engellendi.')
    for path in images:
        with Image.open(path) as image:
            image.verify()
    for path, seconds, words in audios:
        if not Path(path).is_file() or seconds <= 0 or duration(path) <= 0:
            raise RuntimeError('Sahne seslendirmesi eksik veya geçersiz.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def receipt_path(video):
    return Path(video).with_suffix('.production.json')


def write_receipt(video, story, images, audios):
    validate_inputs(story, images, audios)
    assets = [Path(video).parent / 'hikaye.json', *map(Path, images),
              *(Path(a[0]) for a in audios)]
    data = {'video_sha256': digest(video),
            'assets': [{'path': str(p.resolve().relative_to(Path(video).parent.resolve())), 'sha256': digest(p)} for p in assets]}
    receipt_path(video).write_text(json.dumps(data), encoding='utf-8')


def validate_receipt(video):
    data = json.loads(receipt_path(video).read_text(encoding='utf-8'))
    if digest(video) != data['video_sha256'] or not data['assets']:
        raise RuntimeError('Üretim kanıtı MP4 ile uyuşmuyor.')
    for asset in data['assets']:
        if digest(Path(video).parent / asset['path']) != asset['sha256']:
            raise RuntimeError('Üretim sahnesi/görseli/sesi değişmiş.')
    validate_video(video)


def copy_receipt(source, target):
    import shutil
    validate_receipt(source)
    data = json.loads(receipt_path(source).read_text(encoding='utf-8'))
    for i, asset in enumerate(data['assets']):
        original = Path(source).parent / asset['path']
        relative = Path('production_assets') / f'{i:03}{original.suffix}'
        dest = Path(target).parent / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, dest)
        asset['path'] = str(relative)
    receipt_path(target).write_text(json.dumps(data), encoding='utf-8')
