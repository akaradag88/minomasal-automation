
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
    
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)



    
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




def save_facebook_ledger(ledger):
    """Save publication state and push it to GitHub."""
    import json
    import subprocess
    from pathlib import Path

    path = Path(FACEBOOK_LEDGER)
    temp = path.with_suffix(".json.tmp")

    temp.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    temp.replace(path)

    subprocess.run(
        ["git", "add", str(path)],
        check=True
    )

    changed = subprocess.run(
        ["git", "diff", "--cached", "--quiet"]
    ).returncode

    if changed == 0:
        raise RuntimeError("Facebook kayıtlarında değişiklik yok.")

    subprocess.run(
        ["git", "commit", "-m", "Update Facebook publication state [skip ci]"],
        check=True
    )

    try:
        subprocess.run(
            ["git", "push", "origin", "HEAD:main"],
            check=True
        )
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "Facebook kayıtları GitHub'a kaydedilemedi. "
            "Yayın durumunu kontrol etmeden tekrar deneme!"
        )

def reserve_facebook_publication(story_number):
    """Block retries before any Facebook upload attempt."""
    import json
    from pathlib import Path

    path = Path(FACEBOOK_LEDGER)
    ledger = json.loads(path.read_text(encoding="utf-8"))

    if ledger.get("schema_version") != 1:
        raise RuntimeError("Facebook kayıt sürümü geçersiz.")

    stories = ledger.get("stories")
    if not isinstance(stories, dict):
        raise RuntimeError("Facebook kayıt yapısı geçersiz.")

    key = str(story_number)

    if key in stories:
        raise RuntimeError(
            f"Video {story_number} daha önce işleme alınmış. "
            "Manuel kontrol olmadan tekrar denenemez."
        )

    stories[key] = {
        "status": "ambiguous",
        "video_id": None,
        "post_id": None
    }

    save_facebook_ledger(ledger)

    print(f"Video {story_number} için yayın denemesi kaydedildi.")
    return True

def require_facebook_publish_authorization():
    """Block publication unless explicitly authorized."""
    import os

    if os.environ.get("FACEBOOK_PUBLISH_ENABLED") != "true":
        raise RuntimeError(
            "Facebook yayını kapalı. "
            "FACEBOOK_PUBLISH_ENABLED=true gerekli."
        )

    if os.environ.get("FACEBOOK_CONFIRM_PUBLISH") != "YES":
        raise RuntimeError(
            "Facebook yayını için ikinci onay gerekli."
        )

    print("Facebook yayın yetkilendirmesi doğrulandı.")


def facebook_reels_upload_video(upload_url, video_url, page_token):
    """Transfer an existing MP4 to Facebook without publishing."""
    import json
    import urllib.request
    from urllib.parse import urlparse


    if urlparse(upload_url).scheme != "https":
        raise RuntimeError("Geçersiz Facebook yükleme adresi.")

    if urlparse(upload_url).hostname not in (
        "rupload.facebook.com",
        "rupload.facebook.net",
    ):
        raise RuntimeError("Beklenmeyen Facebook yükleme sunucusu.")

    
    parsed_video = urlparse(video_url)

    if (
        parsed_video.scheme != "https"
        or parsed_video.hostname != "github.com"
        or not parsed_video.path.startswith(
            "/akaradag88/minomasal-video-hosting/releases/download/"
        )
    ):
        raise RuntimeError(
            "Video bağlantısı MinoMasal hosting deposuna ait değil."
        )


    request = urllib.request.Request(
        upload_url,
        data=b"",
        headers={
            "Authorization": f"OAuth {page_token}",
            "file_url": video_url,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)

def validate_facebook_video_transfer(result):
    """Validate Facebook video transfer response."""
    if not isinstance(result, dict):
        raise RuntimeError("Facebook video aktarım yanıtı geçersiz.")

    if result.get("success") is not True:
        raise RuntimeError(
            f"Facebook video aktarımı doğrulanamadı: {result}"
        )

    print("Facebook video aktarımı başarılı.")
    return True

def record_facebook_publication(story_number, video_id):
    """Record a confirmed Facebook publication."""
    import json
    from pathlib import Path

    if not video_id:
        raise RuntimeError("Facebook video kimliği eksik.")

    path = Path(FACEBOOK_LEDGER)
    ledger = json.loads(path.read_text(encoding="utf-8"))

    record = ledger.get("stories", {}).get(str(story_number))

    if not record or record.get("status") != "ambiguous":
        raise RuntimeError(
            "Facebook yayın denemesi kaydı bulunamadı."
        )

    record["status"] = "published"
    record["video_id"] = str(video_id)

    save_facebook_ledger(ledger)

    print(f"Facebook video {story_number} yayın kaydı tamamlandı.")

def facebook_reels_finish(video_id, page_token, title):
    """Request Facebook Reel publication after upload."""
    import json
    import urllib.parse
    import urllib.request

    if not video_id:
        raise RuntimeError("Facebook video ID eksik.")

    url = f"https://graph.facebook.com/v26.0/{video_id}/video_reels"

    payload = urllib.parse.urlencode({
        "upload_phase": "finish",
        "video_state": "PUBLISHED",
        "description": title,
        "access_token": page_token,
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)

def validate_facebook_publish_response(result, expected_video_id):
    """Validate Facebook Reels finish API response."""
    if not isinstance(result, dict):
        raise RuntimeError("Facebook yayın yanıtı geçersiz.")

    if result.get("success") is not True:
        raise RuntimeError(
            "Facebook yayın isteğinin başarılı olduğu doğrulanamadı."
        )

    returned_id = result.get("video_id")

    if returned_id and str(returned_id) != str(expected_video_id):
        raise RuntimeError("Facebook video kimliği uyuşmuyor.")

    print("Facebook yayın isteği API tarafından kabul edildi.")
    return True

def facebook_reels_check_status(video_id, page_token):
    """Read Facebook video processing and publishing status."""
    import json
    import urllib.parse
    import urllib.request

    if not str(video_id).isdigit():
        raise RuntimeError("Geçersiz Facebook video ID.")

    params = urllib.parse.urlencode({
        "fields": "id,status",
        "access_token": page_token,
    })

    url = f"https://graph.facebook.com/v26.0/{video_id}?{params}"

    request = urllib.request.Request(url, method="GET")

    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)

    if str(result.get("id")) != str(video_id):
        raise RuntimeError("Facebook video kimliği uyuşmuyor.")

    return result

def record_facebook_upload_session(story_number, video_id):
    """Persist the Facebook upload ID before transferring video."""
    from pathlib import Path
    import json

    if not str(video_id).isdigit():
        raise RuntimeError("Geçersiz Facebook video kimliği.")

    path = Path(FACEBOOK_LEDGER)
    ledger = json.loads(path.read_text(encoding="utf-8"))
    record = ledger.get("stories", {}).get(str(story_number))

    if not record or record.get("status") != "ambiguous":
        raise RuntimeError("Önceden ayrılmış yayın kaydı bulunamadı.")

    if record.get("video_id") is not None:
        raise RuntimeError("Video kimliği zaten kayıtlı; işlem durduruldu.")

    record["video_id"] = str(video_id)
    save_facebook_ledger(ledger)

    print("Facebook yükleme kimliği güvenli şekilde kaydedildi.")

def facebook_preflight(story_number):
    """Check publication requirements without publishing."""
    from pathlib import Path

    if not isinstance(story_number, int) or story_number < 1:
        raise RuntimeError("Geçersiz hikâye numarası.")

    if not Path(FACEBOOK_LEDGER).is_file():
        raise RuntimeError("Facebook yayın kayıt dosyası bulunamadı.")

    require_facebook_publish_authorization()
    check_facebook_publish_status(story_number)

    video_url = facebook_video_url(story_number)

    print(f"Hikâye {story_number} yayın öncesi kontrolü başarılı.")
    return video_url

def record_facebook_upload_complete(story_number, video_id):
    """Record completed upload without marking it published."""
    import json
    from pathlib import Path

    path = Path(FACEBOOK_LEDGER)
    ledger = json.loads(path.read_text(encoding="utf-8"))
    record = ledger.get("stories", {}).get(str(story_number))

    if not record or record.get("status") != "ambiguous":
        raise RuntimeError("Facebook yayın denemesi kaydı geçersiz.")

    if str(record.get("video_id")) != str(video_id):
        raise RuntimeError("Facebook video kimliği uyuşmuyor.")

    if record.get("upload_complete"):
        raise RuntimeError("Video aktarımı zaten kayıtlı.")

    record["upload_complete"] = True
    save_facebook_ledger(ledger)

    print(f"Facebook video {story_number}: aktarım kaydedildi.")

def validate_facebook_processing_status(result):
    """Check whether Facebook reports completed video processing."""
    if not isinstance(result, dict):
        raise RuntimeError("Facebook durum yanıtı geçersiz.")

    status = result.get("status")
    if not isinstance(status, dict):
        raise RuntimeError("Facebook video durum bilgisi eksik.")

    processing = status.get("processing_phase")
    if not isinstance(processing, dict):
        raise RuntimeError("Facebook işleme aşaması bilgisi eksik.")

    state = processing.get("status")

    if state != "complete":
        raise RuntimeError(
            f"Facebook video işleme henüz tamamlanmadı: {state}"
        )

    print("Facebook video işleme tamamlandı.")
    return True

def start_safe_facebook_publication(story_number):
    """Authorize and reserve a story before Facebook upload."""
    video_url = facebook_preflight(story_number)

    # Persist the attempt before making an external upload request.
    reserve_facebook_publication(story_number)

    print(f"Facebook video {story_number}: güvenli yayın kaydı oluşturuldu.")
    return video_url

def prepare_facebook_upload(story_number):
    """Reserve the story and start a Facebook upload session."""
    video_url = start_safe_facebook_publication(story_number)

    # An upload session is an external API operation.
    # The story is already marked ambiguous before this call.
    session = facebook_reels_start_upload()
    session = validate_facebook_upload_session(session)

    record_facebook_upload_session(
        story_number,
        session["video_id"]
    )

    record_facebook_upload_details(
        story_number,
        session["video_id"],
        video_url
    )

    print("Facebook yükleme oturumu hazır.")
    return {
        "video_url": video_url,
        "video_id": session["video_id"],
        "upload_url": session["upload_url"],
    }

def record_facebook_upload_details(story_number, video_id, video_url):
    """Save upload details without publishing."""
    import json
    from pathlib import Path

    path = Path(FACEBOOK_LEDGER)
    ledger = json.loads(path.read_text(encoding="utf-8"))
    record = ledger.get("stories", {}).get(str(story_number))

    if not record or record.get("status") != "ambiguous":
        raise RuntimeError("Facebook yayın kaydı bulunamadı.")

    if str(record.get("video_id")) != str(video_id):
        raise RuntimeError("Facebook video kimliği uyuşmuyor.")

    if record.get("video_url"):
        raise RuntimeError("Video bağlantısı zaten kayıtlı.")

    record["video_url"] = video_url
    save_facebook_ledger(ledger)

    print("Facebook yükleme bilgileri kaydedildi.")

def publish_first_facebook_reel(story_number):
    """Prepare the first Facebook Reel; publishing requires further steps."""
    if story_number != 19:
        raise RuntimeError("İlk yayın yalnızca 19. video için.")

    session = prepare_facebook_upload(story_number)

    print("Facebook yükleme oturumu oluşturuldu.")
    print("Video ID:", session["video_id"])

    return session

def complete_first_facebook_reel(story_number):
    """Upload and publish the first Facebook Reel."""
    if story_number != 19:
        raise RuntimeError("İlk yayın yalnızca 19. video için.")

    require_facebook_publish_authorization()

    session = prepare_facebook_upload(story_number)
    page_token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]

    transfer = facebook_reels_upload_video(
        session["upload_url"],
        session["video_url"],
        page_token
    )
    validate_facebook_video_transfer(transfer)

    record_facebook_upload_complete(
        story_number,
        session["video_id"]
    )



    title = "Ayıcığın Ekran Merakı | MinoMasal"

    result = facebook_reels_finish(
        session["video_id"],
        page_token,
        title
    )
    validate_facebook_publish_response(
        result,
        session["video_id"]
    )

    import time

    for attempt in range(20):
        status_result = facebook_reels_check_status(
            session["video_id"],
            page_token
        )

        status = status_result.get("status", {})
        publishing = status.get("publishing_phase", {})

        if publishing.get("status") == "complete":
            break

        if publishing.get("status") in ("error", "failed"):
            raise RuntimeError("Facebook yayın işlemi başarısız.")

        time.sleep(15)
    else:
        raise RuntimeError(
            "Facebook yayın durumu doğrulanamadı. "
            "Tekrar çalıştırmadan önce manuel kontrol gerekli."
        )

    record_facebook_publication(
        story_number,
        session["video_id"]
    )

    print("Facebook Reels yayın isteği başarıyla tamamlandı.")
