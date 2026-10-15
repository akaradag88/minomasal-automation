
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

import base64
import urllib.request

from nacl import encoding, public

repo = "akaradag88/minomasal-automation"
github_token = os.environ["MINOMASAL_GITHUB_TOKEN"]
secret_name = "FACEBOOK_LONG_USER_TOKEN"

headers = {
    "Authorization": f"Bearer {github_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

def github_api(method, endpoint, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/secrets/{'public-key' if endpoint == 'public-key' else endpoint}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response) if method == "GET" else None

key_info = github_api("GET", "public-key")

public_key = public.PublicKey(
    key_info["key"].encode(),
    encoding.Base64Encoder()
)

encrypted = public.SealedBox(public_key).encrypt(
    result["access_token"].encode()
)

github_api("PUT", secret_name, {
    "encrypted_value": base64.b64encode(encrypted).decode(),
    "key_id": key_info["key_id"],
})

print("Uzun süreli Facebook User Token GitHub Secrets'a kaydedildi.")
