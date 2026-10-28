"""MinoMasal2 #33 approved Republic Day story: isolated preview; NEVER publish.

Source: the user-approved hikaye_01.json, verified by immutable SHA256.
Renders the original narration and original visual story instructions unchanged.
For each image generation request, limits the character appearance block to
only the cast of that scene to avoid unwanted background characters.
"""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

import minomasal as mm
from minomasal_sami_hizalama_v2 import aligned_scene_voices

STORY_NUMBER = 33
TOPIC = "Minik Sincabın Kırmızı Beyaz Bayrağı"
APPROVED_PATH = Path("minomasal_29ekim_onayli/hikaye_01.json")
APPROVED_SHA256 = "8b95189bffdf4f0b0f30368b234f62ec5d431bd4686809cb32a61f38713f3d3d"
OUTPUT = Path("minomasal_29ekim_preview")
LEDGER = Path("minomasal_platform_durumu.json")
STATE_NAMES = (
    "minomasal_yayin_durumu.json",
    "minomasal_onizleme_durumu.json",
    "minomasal_platform_durumu.json",
    "minomasal_facebook_durumu.json",
)

# Visual-only cast references. Does NOT change the approved JSON, narration,
# scene order, title, or authorized special-day character identities.
CAST = [
    ("Minik Sincap", "a small russet squirrel with a fluffy curled tail, cream chest and bright brown eyes"),
    ("Ela Tavşan", "a light-brown rabbit with long white-tipped ears, warm eyes and a blue scarf"),
    ("Deniz Karga", "a black crow with shiny feathers and a short gray beak"),
    ("Öğretmen Baykuş", "a wise tawny owl with large golden eyes and a small green vest"),
]
SCENE_CAST = [
    ("Minik Sincap",),
    ("Minik Sincap", "Ela Tavşan"),
    ("Minik Sincap", "Ela Tavşan"),
    ("Minik Sincap", "Ela Tavşan", "Öğretmen Baykuş"),
    ("Minik Sincap", "Ela Tavşan", "Öğretmen Baykuş"),
    ("Minik Sincap", "Ela Tavşan", "Öğretmen Baykuş"),
    ("Minik Sincap", "Ela Tavşan", "Deniz Karga", "Öğretmen Baykuş"),
    ("Minik Sincap", "Ela Tavşan", "Öğretmen Baykuş"),
    ("Minik Sincap", "Ela Tavşan"),
    ("Minik Sincap", "Ela Tavşan"),
]


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_hashes():
    return {n: _hash(Path(n)) for n in STATE_NAMES if Path(n).is_file()}


def _load_story():
    if not APPROVED_PATH.is_file():
        raise RuntimeError("Onaylı hikaye_01.json bulunamadı.")
    if _hash(APPROVED_PATH) != APPROVED_SHA256:
        raise RuntimeError("Onaylı hikâye dosyasının içeriği değişmiş; test durduruldu.")
    story = json.loads(APPROVED_PATH.read_text(encoding="utf-8"))
    mm.validate(story)
    if story["title"] != TOPIC or len(story["scenes"]) != 10:
        raise RuntimeError("#33 başlık veya 10 sahne şartı uyuşmuyor.")
    if mm.KONULAR[STORY_NUMBER - 1] != TOPIC:
        raise RuntimeError("#33 konusu minomasal.py içindeki listeyle uyuşmuyor.")
    for name, appearance in CAST:
        if f"{name}: {appearance}" not in story["characters"]:
            raise RuntimeError(f"Onaylı JSON'daki karakter tanımı uyuşmuyor: {name}")
    n = sum(len(s["narration"].split()) for s in story["scenes"])
    print(f"Onaylı özel gün hikâyesi: {len(story['scenes'])} sahne, {n} kelime.")
    print("NOT: Onaylı #33 metni genel 75–110 kelime test sınırından muaf; metin değiştirilmiyor.")
    if "Atatürk" not in " ".join(s["narration"] for s in story["scenes"]):
        raise RuntimeError("Onaylı hikâyede Atatürk anlatımı bulunamadı.")
    return story


def _make_scene_images(original_make_images, story, folder, key, model, local=""):
    """Keep each image prompt focused without rewriting the approved story."""
    if local:
        raise RuntimeError("Bu test yüklenen görsel klasörüyle çalışacak şekilde tasarlanmadı.")
    if len(story["scenes"]) != len(SCENE_CAST):
        raise RuntimeError("Özel gün sahne sayısı değişti.")
    folder.mkdir(parents=True, exist_ok=True)
    appearance = dict(CAST)
    output = []
    for i, (scene, names) in enumerate(zip(story["scenes"], SCENE_CAST), start=1):
        isolated = deepcopy(story)
        isolated["scenes"] = [deepcopy(scene)]
        isolated["characters"] = "; ".join(f"{name}: {appearance[name]}" for name in names)
        # Add prompt-only constraints. Approved JSON stays byte-for-byte intact.
        suffix = (
            "Show only the explicitly selected named characters; no unrelated animals, "
            "no crowd, no invented character names, consistent character colors and accessories. "
            "Follow the scene action and objects precisely."
        )
        if "flag" in scene["visual"].lower():
            suffix += " The Turkish flag is red with a single white crescent and one white five-pointed star."
        isolated["scenes"][0]["visual"] += " " + suffix
        scene_folder = folder / f"sahne_{i:02}"
        scene_folder.mkdir(parents=True, exist_ok=True)
        generated = original_make_images(isolated, scene_folder, key, model, "")
        if len(generated) != 1:
            raise RuntimeError(f"{i}. sahnede yalnızca 1 görsel bekleniyor.")
        output.append(generated[0])
    return output


async def main():
    if os.environ.get("MINOMASAL_YOUTUBE_UPLOAD", "false").lower() != "false" or mm.YAYIN_AKTIF:
        raise RuntimeError("Bu iş akışında hiçbir platforma yükleme yapılamaz.")
    if mm.KISA_MASAL_TEST:
        raise RuntimeError("Bu test kısa masal modu değil, onaylı özel gün modudur.")
    if not LEDGER.is_file():
        raise RuntimeError("Yayın defteri eksik; test güvenli biçimde durduruldu.")
    state = json.loads(LEDGER.read_text(encoding="utf-8"))
    row32 = state.get("stories", {}).get("32", {})
    if any(row32.get(platform, {}).get("status") != "published" for platform in ("youtube", "instagram")):
        raise RuntimeError("#32 iki platformda doğrulanmış değil; test durduruldu.")
    if not row32.get("instagram", {}).get("media_id"):
        raise RuntimeError("#32 Instagram medya kimliği eksik.")
    before = _state_hashes()
    story = _load_story()

    orig_images = mm.make_images
    mm.make_images = lambda story_, folder, key, model, local="": _make_scene_images(
        orig_images, story_, folder, key, model, local
    )
    mm.voices = aligned_scene_voices
    print("#33 özel gün: onaylı hikâye metni; yerel ses ve altyazı hizalaması; YAYIN YOK.")
    # The supplied_story=True path preserves the approved special-day JSON verbatim.
    video = await mm.produce(TOPIC, supplied_story=story)
    if not video.is_file() or mm.duration(video) <= 1:
        raise RuntimeError("Üretilen video geçersiz.")
    actual = json.loads((video.parent / "hikaye.json").read_text(encoding="utf-8"))
    if actual != story:
        raise RuntimeError("Üretilen videonun hikâyesi onaylı JSON'dan farklı!")
    subtitle = video.parent / "altyazi.srt"
    if not subtitle.is_file() or subtitle.stat().st_size == 0:
        raise RuntimeError("Zamanlanmış altyazılar bulunamadı.")
    if _state_hashes() != before:
        raise RuntimeError("Yayın durum dosyası değişmiş! Test durduruldu.")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, OUTPUT / "masal_33_onizleme.mp4")
    shutil.copy2(subtitle, OUTPUT / "altyazi_33.srt")
    shutil.copy2(APPROVED_PATH, OUTPUT / "hikaye_33_onayli.json")
    print(f"BAŞARILI. Video süresi: {mm.duration(video):.2f} saniye")
    print("YAYIN YAPILMADI. #33 hâlâ otomatik yayın için ayrı onay/entegrasyon gerektiriyor.")
    print("Dosyalar:", OUTPUT.resolve())


if __name__ == "__main__":
    asyncio.run(main())
