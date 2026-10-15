
import os
import json
import urllib.parse
import urllib.request

params = urllib.parse.urlencode({
    "grant_type": "fb_exchange_token",
    "client_id": os.environ["FACEBOOK_APP_ID"],
    "client_secret": os.environ["FACEBOOK_APP_SECRET"],
    "fb_exchange_token": os.environ["FACEBOOK_SHORT_USER_TOKEN"],
})

url = "https://graph.facebook.com/v26.0/oauth/access_token"

with urllib.request.urlopen(
    urllib.request.Request(url + "?" + params),
    timeout=30
) as response:
    result = json.load(response)

if not result.get("access_token"):
    raise RuntimeError("Uzun süreli token alınamadı.")

print("Uzun süreli User Token başarıyla oluşturuldu.")
print("Geçerlilik süresi (saniye):", result.get("expires_in"))
