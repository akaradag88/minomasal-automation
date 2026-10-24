
"""Facebook 29. video için tek seferlik kurtarma."""

import json
import os
import time
from pathlib import Path

from minomasal_facebook_publish import (
    FACEBOOK_LEDGER,
    facebook_reels_check_status,
    facebook_reels_finish,
    validate_facebook_publish_response,
    save_facebook_ledger,
)

NUMBER = "29"
VIDEO_ID = "1453876890009815"

def main():
    if os.environ.get("FACEBOOK_RECOVERY_CONFIRM") != "YES":
        raise RuntimeError("Kurtarma yayini icin onay yok.")

    path = Path(FACEBOOK_LEDGER)
    ledger = json.loads(path.read_text(encoding="utf-8"))
    record = ledger["stories"][NUMBER]

    if (
        record["status"] != "ambiguous"
        or str(record["video_id"]) != VIDEO_ID
        or record.get("upload_complete") is not True
        or record.get("finish_attempted") is not True
        or record.get("post_id") is not None
    ):
        raise RuntimeError("Kurtarma kaydi beklenen durumda degil.")

    if record.get("recovery_attempted"):
        raise RuntimeError("Kurtarma daha once denenmis. Tekrar yasak.")

    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]

    result = facebook_reels_check_status(VIDEO_ID, token)
    status = result.get("status", {})

    if status.get("video_status") != "upload_complete":
        raise RuntimeError("Video aktarimi dogrulanamadi.")

    phase = status.get("publishing_phase", {})

    if phase.get("status") != "not_started":
        raise RuntimeError(
            "Yayin asamasi degismis. Kurtarma durduruldu."
        )

    # Facebook'a istek gondermeden ONCE kalici kayit olustur.
    record["recovery_attempted"] = True
    save_facebook_ledger(ledger)

    print("KURTARMA GIRISIMI GITHUB'A KAYDEDILDI")

    source = json.loads(
        Path("minomasal_platform_durumu.json").read_text(
            encoding="utf-8"
        )
    )
    title = source["stories"][NUMBER]["title"]

    response = facebook_reels_finish(VIDEO_ID, token, title)
    validate_facebook_publish_response(response, VIDEO_ID)

    print("FACEBOOK FINISH ISTEGI GONDERILDI")

    for _ in range(20):
        result = facebook_reels_check_status(VIDEO_ID, token)
        phase = result.get("status", {}).get("publishing_phase", {})

        if (
            phase.get("status") == "complete"
            and phase.get("publish_status") == "published"
        ):
            ledger = json.loads(path.read_text(encoding="utf-8"))
            record = ledger["stories"][NUMBER]
            record["status"] = "published"
            record["post_id"] = VIDEO_ID
            save_facebook_ledger(ledger)
            print("FACEBOOK 29 YAYINLANDI")
            return

        if phase.get("status") in ("error", "failed"):
            raise RuntimeError("Facebook yayin hatasi.")

        time.sleep(15)

    raise RuntimeError(
        "Yayin dogrulanamadi. Otomatik tekrar YASAK."
    )

if __name__ == "__main__":
    main()
