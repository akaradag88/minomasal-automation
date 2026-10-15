
import os
import json
import urllib.request
import urllib.parse
import urllib.error

PAGE_ID = os.environ["FACEBOOK_PAGE_ID"]
TOKEN = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]

url = (
    f"https://graph.facebook.com/v26.0/{PAGE_ID}"
    "?fields=id,name"
    "&access_token=" + urllib.parse.quote(TOKEN, safe="")
)

try:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.load(response)

    if str(data.get("id")) != PAGE_ID:
        raise RuntimeError("Facebook Page ID mismatch")

    print("Facebook bağlantısı başarılı!")
    print("Sayfa:", data.get("name"))
    print("Sayfa ID:", data.get("id"))
    print("Henüz video yayınlanmadı.")

except urllib.error.HTTPError as error:
    print("Facebook API hatası:", error.code)
    raise SystemExit(1)


# Facebook Reels publication safety settings
FACEBOOK_LEDGER = "minomasal_facebook_durumu.json"

# Publishing is disabled by default.
# A separate, explicitly authorized workflow will be required.
FACEBOOK_PUBLISH_ENABLED = False


def facebook_video_url(story_number):
    """Return the hosted MP4 URL for an existing story."""
    import json
    from pathlib import Path

    ledger_path = Path("minomasal_platform_durumu.json")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    story = ledger.get("stories", {}).get(str(story_number))
    if not story:
        raise RuntimeError(f"Hikaye {story_number} bulunamadı.")

    if story.get("youtube", {}).get("status") != "published":
        raise RuntimeError("YouTube yayını doğrulanamadı.")

    if story.get("instagram", {}).get("status") != "published":
        raise RuntimeError("Instagram yayını doğrulanamadı.")

    url = (story.get("video_asset") or {}).get("url")
    if not url or not url.startswith("https://"):
        raise RuntimeError("Geçerli video bağlantısı bulunamadı.")

    return url


if __name__ == "__main__" and os.environ.get("FACEBOOK_TEST_VIDEO") == "true":
    story_number = int(os.environ.get("FACEBOOK_STORY_NUMBER", "19"))
    video_url = facebook_video_url(story_number)
    print(f"Video {story_number} bağlantısı bulundu.")
    print("GitHub Releases MP4 bağlantısı hazır.")


def facebook_reels_start_upload():
    """Start a Facebook Reels upload session without publishing."""
    import json
    import urllib.parse
    import urllib.request

    page_id = os.environ["FACEBOOK_PAGE_ID"]
    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]

    url = f"https://graph.facebook.com/v26.0/{page_id}/video_reels"

    payload = urllib.parse.urlencode({
        "upload_phase": "start",
        "access_token": token,
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
    )


    
def validate_facebook_upload_session(result):
    """Validate the Facebook Reels upload session response."""
    if not isinstance(result, dict):
        raise RuntimeError("Geçersiz Facebook API yanıtı.")

    video_id = result.get("video_id")
    upload_url = result.get("upload_url")

    if not video_id or not upload_url:
        raise RuntimeError(
            "Facebook yükleme oturumunda video_id veya upload_url eksik."
        )

    print("Facebook yükleme oturumu yanıtı doğrulandı.")
    return {
        "video_id": str(video_id),
        "upload_url": upload_url,
    }

def check_facebook_publish_status(story_number):
    """Prevent automatic retries of existing or uncertain posts."""
    from pathlib import Path
    import json

    ledger_path = Path(FACEBOOK_LEDGER)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    if ledger.get("schema_version") != 1:
        raise RuntimeError("Facebook kayıt dosyası sürümü geçersiz.")

    stories = ledger.get("stories")
    if not isinstance(stories, dict):
        raise RuntimeError("Facebook yayın kayıtları geçersiz.")

    record = stories.get(str(story_number))

    if record is not None:
        raise RuntimeError(
            f"Video {story_number} için Facebook kaydı mevcut. "
            "Tekrar yayınlamadan önce manuel kontrol gerekli."
        )

    print(f"Video {story_number}: Facebook kayıtlarında bulunamadı.")
    return True

    
    if __name__ == "__main__" and os.environ.get("FACEBOOK_TEST_LEDGER") == "true":
        story_number = int(os.environ.get("FACEBOOK_STORY_NUMBER", "19"))
        check_facebook_publish_status(story_number)
        print("Facebook yayın kaydı güvenlik testi başarılı.")



