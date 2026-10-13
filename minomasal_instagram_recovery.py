
"""17. MinoMasal videosunu yeniden üretir.
YouTube veya Instagram'a yükleme yapmaz.
"""

import asyncio
import json
from pathlib import Path

from minomasal import produce, duration

LEDGER = Path("minomasal_platform_durumu.json")
NUMBER = "17"


async def main():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    record = ledger["stories"][NUMBER]

    if record["youtube"]["status"] != "published":
        raise RuntimeError("YouTube kaydı doğrulanamadı.")

    if record["instagram"]["status"] != "pending":
        raise RuntimeError("Instagram durumu pending değil.")

    topic = record["topic"]

    print("Yeniden üretiliyor:", topic)

    video = await produce(topic)

    if not video.is_file() or duration(video) <= 1:
        raise RuntimeError("Video üretimi başarısız.")

    print("VIDEO HAZIR:", video)
    print("Yayın yapılmadı.")


if __name__ == "__main__":
    asyncio.run(main())
