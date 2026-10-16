
"""Publish one existing MinoMasal story to Facebook Reels.

Requires an explicit story number and publication authorization.
Never regenerates or republishes an existing Facebook story.
"""

import argparse
import json
from minomasal_facebook_cover import prepare_facebook_cover_asset
import os
import time
from pathlib import Path

from minomasal_facebook_publish import (
    FACEBOOK_LEDGER,
    facebook_video_url,
    require_facebook_publish_authorization,
    reserve_facebook_publication,
    facebook_reels_start_upload,
    validate_facebook_upload_session,
    record_facebook_upload_session,
    record_facebook_upload_details,
    facebook_reels_upload_video,
    validate_facebook_video_transfer,
    record_facebook_upload_complete,
    facebook_reels_finish,
    validate_facebook_publish_response,
    facebook_reels_check_status,
    save_facebook_ledger,
)


def publish(number):
    require_facebook_publish_authorization()

    if number < 20:
        raise RuntimeError("19 ve önceki videolar bu akışla yayımlanamaz.")

    ledger = json.loads(
        Path(FACEBOOK_LEDGER).read_text(encoding="utf-8")
    )

    if str(number) in ledger["stories"]:
        raise RuntimeError(
            "Facebook kaydı zaten var. Manuel kontrol gerekli."
        )

    source = json.loads(
        Path("minomasal_platform_durumu.json").read_text(encoding="utf-8")
    )
    story = source["stories"].get(str(number))

    if not story:
        raise RuntimeError("Hikâye henüz üretilmemiş.")

    
    url = facebook_video_url(number)
    title = story["title"]

    # Facebook için ayrı kapaklı MP4 hazırla.
    # Yayın kaydı oluşturmadan önce bu işlem tamamlanmalı.
    if number >= 22:
        url = prepare_facebook_cover_asset(number, url)

    # Record the attempt before contacting Facebook.
    reserve_facebook_publication(number)


    session = validate_facebook_upload_session(
        facebook_reels_start_upload()
    )
    video_id = session["video_id"]

    record_facebook_upload_session(number, video_id)
    record_facebook_upload_details(number, video_id, url)

    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]

    transfer = facebook_reels_upload_video(
        session["upload_url"], url, token
    )
    validate_facebook_video_transfer(transfer)
    record_facebook_upload_complete(number, video_id)

    # Record the irreversible publication attempt first.
    ledger = json.loads(
        Path(FACEBOOK_LEDGER).read_text(encoding="utf-8")
    )
    ledger["stories"][str(number)]["finish_attempted"] = True
    save_facebook_ledger(ledger)

    result = facebook_reels_finish(video_id, token, title)
    validate_facebook_publish_response(result, video_id)

    for _ in range(20):
        state = facebook_reels_check_status(video_id, token)
        status = state.get("status", {})
        phase = status.get("publishing_phase", {})

        if (
            phase.get("status") == "complete"
            and phase.get("publish_status") == "published"
        ):
            ledger = json.loads(
                Path(FACEBOOK_LEDGER).read_text(encoding="utf-8")
            )
            record = ledger["stories"][str(number)]
            record["status"] = "published"
            record["post_id"] = video_id
            save_facebook_ledger(ledger)
            print(f"SUCCESS: Facebook story {number} published.")
            return

        if phase.get("status") in ("error", "failed"):
            raise RuntimeError("Facebook publishing failed.")

        time.sleep(15)

    raise RuntimeError(
        "Facebook publication unconfirmed. Do not rerun. "
        "Manually reconcile the existing video ID."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", type=int, required=True)
    args = parser.parse_args()
    publish(args.number)
