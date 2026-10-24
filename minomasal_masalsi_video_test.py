
"""MinoMasal masalsı video ön izlemesi - yayın yapmaz."""

import asyncio
import os
import shutil
from pathlib import Path

from minomasal import (
    produce,
    create_story,
    API_KEY,
    HIKAYE_MODELI,
)
from minomasal_masalsi_guvenli import prepare_masalsi_safely
from minomasal_masalsi_uygula import apply_masalsi


async def main():
    
    # Test ortaminda YouTube yuklemesi kesinlikle kapali olmali.
    if os.environ.get(
        "MINOMASAL_YOUTUBE_UPLOAD", "false"
    ).lower() != "false":
        raise RuntimeError(
            "GUVENLIK: Video on izlemesinde YouTube yuklemesi kapali olmali."
        )

    # Yayın ve ön izleme sıra kayıtlarına dokunma.
    topic = "Arkadaşına Yardım Eden Minik Fil"

    if not API_KEY:
        raise RuntimeError("POLLINATIONS_API_KEY eksik.")

    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY eksik.")

    print("TEST KONUSU:", topic)

    story = create_story(topic, API_KEY, HIKAYE_MODELI)

    original, candidate = prepare_masalsi_safely(
        story,
        API_KEY,
        model=HIKAYE_MODELI,
    )

    if candidate is None:
        print("Masalsı dönüşüm başarısız, orijinal kullanılacak.")
        preview_story = original
    else:
        # Yalnızca bu izole test videosunda uygula.
        preview_story = apply_masalsi(
            original,
            candidate,
            approved=True,
        )
        print("Masalsı aday test videosunda kullanılıyor.")

    # produce() doğrudan çağrılır, yayın yapan main() çağrılmaz.
    video = await produce(
        topic,
        supplied_story=preview_story,
    )

    output = Path("masalsi_video_onizleme.mp4")
    shutil.copy2(video, output)

    print("VIDEO HAZIR:", output)
    print("YAYIN YAPILMADI.")
    print("GUNLUK YAYIN KAYITLARI DEGISTIRILMEDI.")


if __name__ == "__main__":
    asyncio.run(main())
