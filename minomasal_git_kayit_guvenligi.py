"""MinoMasal: safely handle an unrelated GitHub main-branch push race.

Never force pushes. Never auto-merge a changed publication ledger.
This module has no external APIs other than git push/fetch.
"""

import json
import subprocess

LEDGER_PATH = "minomasal_platform_durumu.json"


def _git(*args):
    return subprocess.run(
        ["git", *args], text=True, capture_output=True, check=False
    )


def _must_git(*args):
    result = _git(*args)
    if result.returncode != 0:
        raise RuntimeError(
            f"Git işlem hatası ({' '.join(args)}): "
            f"{(result.stderr or result.stdout).strip()[-700:]}"
        )
    return result.stdout.strip()


def _ledger_at(rev):
    raw = _must_git("show", f"{rev}:{LEDGER_PATH}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{rev} sürümündeki yayın defteri bozuk.") from exc


def safe_push_ledger():
    """Push the already-committed ledger, rebasing once if only other files changed.

    Called *after* git commit and *before* any upload. If the remote ledger has
    changed, stop for manual reconciliation instead of overwriting it.
    """
    result = _git("push", "origin", "HEAD:main")
    if result.returncode == 0:
        print("Yayın defteri GitHub'a başarıyla gönderildi.")
        return

    message = f"{result.stdout}\n{result.stderr}".lower()
    if "fetch first" not in message and "non-fast-forward" not in message:
        raise RuntimeError(
            "GitHub push reddedildi; otomatik uzlaştırma uygulanmadı. "
            f"{(result.stderr or result.stdout).strip()[-650:]}"
        )

    print("main dalı ilerlemiş; yayın defteri değişmiş mi kontrol ediliyor...")
    _must_git("fetch", "origin", "main")

    # HEAD^ is the version immediately before the local publishing-state commit.
    # If another process altered this ledger, do not rewrite it or retry uploads.
    original_ledger = _ledger_at("HEAD^")
    remote_ledger = _ledger_at("origin/main")
    if remote_ledger != original_ledger:
        raise RuntimeError(
            "GitHub'daki yayın defteri çalışma sırasında değişmiş. "
            "Yayın durduruldu; kayıtları manuel karşılaştırın. "
            "Zorlayarak push veya otomatik tekrar yükleme YAPILMADI."
        )

    result = _git("rebase", "origin/main")
    if result.returncode != 0:
        _git("rebase", "--abort")
        raise RuntimeError(
            "Güncel dal ile güvenli birleştirme yapılamadı. "
            "Yayın durduruldu; dosyaları inceleyin."
        )

    result = _git("push", "origin", "HEAD:main")
    if result.returncode != 0:
        raise RuntimeError(
            "Güncelledikten sonra da GitHub push reddedildi. "
            "Yayın durduruldu; tekrar çalıştırmadan önce kayıtları kontrol edin. "
            f"{(result.stderr or result.stdout).strip()[-600:]}"
        )
    print("Yayın defteri korunarak main dalı güncellendi.")
