
"""MinoMasal #17 Instagram kurtarma.
Yalnızca Instagram'a yayın yapar. YouTube'a dokunmaz.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

LEDGER = Path("minomasal_platform_durumu.json")
VIDEO_URL = (
    "https://github.com/akaradag88/minomasal-video-hosting/"
    "releases/download/minomasal-story-17/minomasal-17.mp4"
)
API = "https://graph.facebook.com/v26.0"
NUMBER = "17"


def save(ledger):
    temp = LEDGER.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(LEDGER)


def graph(method, path, params):
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        url += "?" + data.decode()
        request = urllib.request.Request(url)
    else:
        request = urllib.request.Request(url, data=data, method="POST")

    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def main():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    row = ledger["stories"][NUMBER]
    ig = row["instagram"]

    if row["youtube"]["status"] != "published":
        raise RuntimeError("YouTube kaydı beklenen durumda değil.")

    if ig["status"] != "pending":
        raise RuntimeError("Instagram durumu pending değil.")

    if os.environ.get("PUBLISH_ENABLED") != "true":
        print("DRY RUN: Kayıtlar doğrulandı. Yayın yapılmadı.")
        return

    auth = {"access_token": os.environ["INSTAGRAM_ACCESS_TOKEN"]}
    user_id = os.environ["INSTAGRAM_USER_ID"]

    # API çağrısından önce belirsiz durumu kaydet.
    ig["status"] = "ambiguous"
    save(ledger)

    result = graph("POST", f"{user_id}/media", {
        **auth,
        "media_type": "REELS",
        "video_url": VIDEO_URL,
        "caption": row["title"] + "\n#MinoMasal #ÇocukHikayeleri",
    })
    ig["container_id"] = result["id"]
    save(ledger)

    for _ in range(25):
        status = graph("GET", ig["container_id"], {
            **auth,
            "fields": "id,status_code",
        }).get("status_code")

        print("Instagram processing:", status)

        if status == "FINISHED":
            break

        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing: {status}")

        time.sleep(30)
    else:
        raise RuntimeError("Instagram işlem süresi doldu.")

    result = graph("POST", f"{user_id}/media_publish", {
        **auth,
        "creation_id": ig["container_id"],
    })

    ig["status"] = "published"
    ig["media_id"] = result["id"]
    row["video_asset"] = {
        "url": VIDEO_URL,
        "release_tag": "minomasal-story-17",
    }
    save(ledger)

    print("Instagram published:", result["id"])


if __name__ == "__main__":
    main()
