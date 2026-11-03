"""MinoMasal: GitHub Contents API uzerinden gunluk tek-yayin kilidi.

Yalnizca LIVE workflow tarafindan kullanilir. Her Turkiye takvim gunu icin
TEK dosya olusturulur: minomasal_gunluk_kilitleri/YYYY-MM-DD.json.

Kilit basariyla GitHub'a yazilmadan hicbir platforma upload yapilmamalidir.
Bir hata olursa gunluk kilit kendiliginden kaldirilmaz; manuel uzlastirma gerekir.
"""

import argparse
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Istanbul')
LOCK_DIR = 'minomasal_gunluk_kilitleri'


class GitHubHttpError(RuntimeError):
    def __init__(self, status, reason):
        self.status = status
        super().__init__(f'GitHub API HTTP {status}: {reason}')


def _env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(f'Eksik ortam degiskeni: {name}')
    return value


def _context():
    repo = _env('GITHUB_REPOSITORY')
    if repo != 'akaradag88/minomasal-automation':
        raise RuntimeError('Beklenmeyen GitHub deposu; kilit reddedildi.')
    return repo, _env('MINOMASAL_LOCK_TOKEN')


def _request(method, path, body=None):
    repo, token = _context()
    url = 'https://api.github.com/repos/' + repo + '/contents/' + urllib.parse.quote(path, safe='/')
    if method == 'GET':
        url += '?ref=main'
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'MinoMasal-Daily-Lock',
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        # Token veya response body degeri loglanmaz.
        raise GitHubHttpError(exc.code, exc.reason) from None


def today():
    return datetime.now(TZ).date().isoformat()


def path_for(day):
    # Takvim gunu disinda path kabul edilmez.
    if len(day) != 10 or datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
        raise RuntimeError('Gecersiz kilit tarihi.')
    return f'{LOCK_DIR}/{day}.json'


def get_file(path):
    try:
        status, response = _request('GET', path)
    except GitHubHttpError as exc:
        if exc.status == 404:
            return None, None
        raise
    if status != 200 or response.get('encoding') != 'base64':
        raise RuntimeError('GitHub dosya cevabi beklenen bicimde degil.')
    try:
        value = json.loads(base64.b64decode(response['content']).decode('utf-8'))
    except (ValueError, KeyError, UnicodeError) as exc:
        raise RuntimeError('GitHub kilit/defter dosyasi okunamadi.') from exc
    return value, response['sha']


def _write(path, value, message, sha=None):
    body = {
        'message': message + ' [skip ci]',
        'content': base64.b64encode((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')).decode(),
        'branch': 'main',
    }
    if sha is not None:
        body['sha'] = sha
    return _request('PUT', path, body)


def _output(**kwargs):
    path = os.environ.get('GITHUB_OUTPUT')
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as dest:
        for key, value in kwargs.items():
            dest.write(f'{key}={value}\n')


def _check_prior_unresolved(day):
    """Bir onceki gunun belirsiz rezervasyonu varsa yeni yayin acma."""
    try:
        status, entries = _request('GET', LOCK_DIR)
    except GitHubHttpError as exc:
        if exc.status == 404:  # Henuz hic kilit dosyasi uretilmemis.
            return False
        raise
    if status != 200 or not isinstance(entries, list):
        raise RuntimeError('Gunluk kilit klasoru okunamadi.')
    for item in entries:
        if item.get('type') != 'file' or not item.get('name', '').endswith('.json'):
            continue
        date_part = item['name'][:-5]
        try:
            path_for(date_part)
        except (ValueError, RuntimeError):
            raise RuntimeError('Kilit klasorunde gecersiz dosya adi var.')
        if date_part >= day:
            continue
        info, _ = get_file(item['path'])
        if info is None or info.get('status') != 'published':
            print(f'ONCEKI KILIT BELIRSIZ: {date_part}; manuel uzlastirma gerekli.')
            return True
    return False


def _before_start(day):
    start = os.environ.get('MINOMASAL_LOCK_START_DATE', '').strip()
    if start:
        path_for(start)
        return day < start
    return False


def preflight():
    day = today()
    lock, _ = get_file(path_for(day))
    earliest = _before_start(day)
    unresolved = _check_prior_unresolved(day)
    eligible = lock is None and not earliest and not unresolved
    _output(eligible=str(eligible).lower(), day=day)
    if eligible:
        print(f'ON KONTROL: {day} icin kilit yok. Sahnelenebilir; HENUZ YAYIN YOK.')
    else:
        reason = ('baslangic tarihinden once' if earliest else
                  'onceki gunlerden belirsiz kilit var' if unresolved else
                  f'bugun kilit var (status={lock.get("status")})')
        print(f'YAYIN ATLANDI: {day}: {reason}.')
    return eligible


def _current_ledger_has_story(number):
    ledger, _ = get_file('minomasal_platform_durumu.json')
    if not isinstance(ledger, dict) or not isinstance(ledger.get('stories'), dict):
        raise RuntimeError('Canli GitHub yayin defteri dogrulanamadi.')
    return str(number) in ledger['stories']


def acquire(number, metadata_path='staging/metadata.json'):
    # Her zaman staging metadata ile kilitlenecek hikaye ayni olmali.
    meta = json.loads(Path(metadata_path).read_text(encoding='utf-8'))
    if type(number) is not int or number < 1 or meta.get('number') != number:
        raise RuntimeError('Sahneleme/hikaye numarasi eslesmiyor.')
    run_id = _env('GITHUB_RUN_ID')
    attempt = _env('GITHUB_RUN_ATTEMPT')
    day = today()
    if _before_start(day) or _check_prior_unresolved(day):
        raise RuntimeError('Baslangic tarihi/onceki kilit kontrolu gecilemedi.')
    path = path_for(day)
    old, _ = get_file(path)
    if old is not None:
        print(f'KILIT VAR: {day} icin baska yayin girisimi var; YAYIN YOK.')
        _output(acquired='false', day=day)
        return False
    if _current_ledger_has_story(number):
        raise RuntimeError(f'#{number} canli yayin defterinde zaten mevcut; tekrar baslatma.')
    value = {
        'date': day,
        'story_number': number,
        'topic': meta['topic'],
        'run_id': run_id,
        'run_attempt': attempt,
        'status': 'reserved',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    try:
        code, _ = _write(path, value, f'Reserve MinoMasal daily slot {day} story {number}')
    except GitHubHttpError as exc:
        if exc.status in (409, 422):
            # Yalnizca gercekten yarismayi baska bir calisma kazandiysa atla.
            winner, _ = get_file(path)
            if winner is not None:
                print(f'YARIS KILIDI: {day} baska calisma tarafindan alindi; YAYIN YOK.')
                _output(acquired='false', day=day)
                return False
        raise
    if code != 201:
        raise RuntimeError(f'Beklenmeyen kilit olusturma sonucu: HTTP {code}')
    print(f'KILIT ALINDI: {day}, hikaye #{number}, run_id={run_id}.')
    _output(acquired='true', day=day)
    return True


def verify(number, day):
    lock, _ = get_file(path_for(day))
    if lock is None:
        raise RuntimeError('GitHub gunluk kilidi yok; yayin engellendi.')
    if not (lock.get('story_number') == number
            and lock.get('run_id') == _env('GITHUB_RUN_ID')
            and lock.get('run_attempt') == _env('GITHUB_RUN_ATTEMPT')
            and lock.get('status') == 'reserved'):
        raise RuntimeError('Kilit bu run/hikayeye ait degil ya da yayin zaten tamamlandi.')
    print(f'GUNLUK KILIT DOGRULANDI: {day}, #{number}.')


def finish(number, day):
    verify(number, day)
    ledger, _ = get_file('minomasal_platform_durumu.json')
    row = (ledger or {}).get('stories', {}).get(str(number), {})
    yt = row.get('youtube', {})
    ig = row.get('instagram', {})
    if not (yt.get('status') == 'published' and yt.get('video_id')
            and ig.get('status') == 'published' and ig.get('media_id')):
        raise RuntimeError('YouTube ve Instagram kayitlari tamam degil; kilit reserved kalacak.')
    lock, sha = get_file(path_for(day))
    lock['status'] = 'published'
    lock['youtube_video_id'] = yt['video_id']
    lock['instagram_media_id'] = ig['media_id']
    lock['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    status, _ = _write(path_for(day), lock, f'Complete MinoMasal daily slot {day}', sha=sha)
    if status != 200:
        raise RuntimeError('Kilit tamamlama beklenmeyen sonuc; reserved olarak incele.')
    print(f'GUNLUK YAYIN TAMAMLANDI: {day}, #{number}.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('preflight', 'acquire', 'verify', 'finish'))
    p.add_argument('--number', type=int)
    p.add_argument('--day')
    args = p.parse_args()
    if args.mode == 'preflight':
        preflight()
    elif args.mode == 'acquire':
        if args.number is None:
            p.error('--number gerekli')
        acquire(args.number)
    else:
        if args.number is None or not args.day:
            p.error('--number ve --day gerekli')
        (verify if args.mode == 'verify' else finish)(args.number, args.day)


if __name__ == '__main__':
    main()
