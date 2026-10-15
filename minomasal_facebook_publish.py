
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
