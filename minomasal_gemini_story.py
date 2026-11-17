"""Gemini story generation for MinoMasal. No publishing or image generation."""
import json
import os
import re
import time

import requests

MODEL = os.environ.get("MINOMASAL_STORY_MODEL", "gemini-3.5-flash-lite")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _validate_story(story):
    if not isinstance(story, dict) or not isinstance(story.get("title"), str):
        raise ValueError("Masal başlığı eksik.")
    if not isinstance(story.get("characters"), str) or not story["characters"].strip():
        raise ValueError("Sabit karakter tanımı eksik.")
    scenes = story.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 10:
        raise ValueError("Masal tam 10 sahneden oluşmalı.")
    narrations = []
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise ValueError("Sahne nesnesi hatalı.")
        for field in ("narration", "visual"):
            if not isinstance(scene.get(field), str) or not scene[field].strip():
                raise ValueError(f"{index}. sahnede {field} eksik.")
        scene.setdefault("sfx", "none")
        narration = scene["narration"].strip()
        if len(narration.split()) > 35:
            raise ValueError("Sahne anlatımı çok uzun.")
        narrations.append(narration)
    combined = " ".join(narrations)
    words = len(combined.split())
    if not 75 <= words <= 110:
        raise ValueError(f"Masal uzunluğu {words}; 75–110 kelime gerekli.")
    if re.search(r"(\b\w{3,}\b)(?:\s+\1){1,}", combined, re.IGNORECASE):
        raise ValueError("Masalda yinelenen kelimeler var.")
    if re.search(r"([A-Za-zÇĞİÖŞÜçğıöşü]{3,})\1", combined):
        raise ValueError("Masalda bozuk tekrarlı yazım olabilir.")
    return story


def generate_story(topic, prompt):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY GitHub secret eksik.")
    instructions = (
        "Sen MinoMasal için deneyimli Türkçe çocuk masalı yazarısın. "
        "Yalnız geçerli JSON üret. Tam 10 sahne, toplam 75–110 Türkçe anlatım kelimesi, "
        "en fazla 4 karakter. Doğal, akıcı, düzgün Türkçe kullan; "
        "kelime/hece tekrarı, anlamsız sözcük ve dil karışımı yasak. "
        "Sahneler neden-sonuç ilişkisiyle ilerlesin; her görsel anlatılan olayı göstersin. "
        "Başlık, moral, İngilizce sabit characters tarifi ve "
        "scenes dizisi ver. Her sahnede narration (Türkçe), visual (İngilizce), sfx alanları olsun. "
        "JSON dışında açıklama veya markdown ekleme. "
        "Konu: " + topic
    )
    payload = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.55, "responseMimeType": "application/json"},
    }
    # Only transient server overloads trigger a model fallback.
    models = list(dict.fromkeys([MODEL, "gemini-3.1-flash-lite", "gemini-3.5-flash"]))
    last_error = None
    for model in models:
        url = API_URL.format(model=model)
        for attempt in range(3):
            try:
                response = requests.post(
                    url, headers={"x-goog-api-key": api_key},
                    json=payload, timeout=90
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    print(f"Gemini transient HTTP {response.status_code}; model={model}; attempt={attempt + 1}", flush=True)
                    last_error = RuntimeError(f"Gemini geçici HTTP {response.status_code}")
                    if attempt < 2:
                        time.sleep(3 * (2 ** attempt))
                        continue
                    break
                response.raise_for_status()
                data = response.json()
                text = "".join(
                    part.get("text", "")
                    for part in data["candidates"][0]["content"]["parts"]
                )
                story = _validate_story(json.loads(text))
                print(f"Gemini story model succeeded: {model}", flush=True)
                return story
            except (ValueError, KeyError, IndexError, requests.RequestException) as exc:
                last_error = exc
                # Bad model output is retried on the same model; HTTP 4xx
                # (except 429 handled above) is a configuration error.
                if isinstance(exc, requests.HTTPError):
                    raise RuntimeError(f"Gemini API error HTTP {exc.response.status_code} on {model}") from exc
                if attempt < 2:
                    time.sleep(3 * (2 ** attempt))
    raise RuntimeError(f"Gemini masal üretimi doğrulanamadı: {last_error}") from last_error
