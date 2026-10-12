
"""MinoMasal daily staging coordinator.

Selects the next unpublished story and produces its video.
Publishing is handled separately by minomasal_dual_publish.py.
"""

import asyncio
import json
import os
import shutil
from pathlib import Path

from minomasal import KONULAR, duration, produce
from minomasal_ledger import read, validate

LEDGER = Path("minomasal_platform_durumu.json")
STAGING = Path("staging")


def choose(ledger):
    validate(ledger)
    stories = ledger["stories"]

    sixteen = stories.get("16")
    if not sixteen or any(
        sixteen[p]["status"] != "published"
        for p in ("youtube", "instagram")
    ):
        raise RuntimeError(
            "Story 16 is not published on both platforms."
        )

    for number in range(17, len(KONULAR) + 1):
        record = stories.get(str(number))

        if record is None:
            return number

        if record["topic"] != KONULAR[number - 1]:
            raise RuntimeError(
                f"Story {number}: topic mismatch."
            )

        statuses = [
            record[p]["status"]
            for p in ("youtube", "instagram")
        ]

        if statuses == ["published", "published"]:
            continue

        raise RuntimeError(
            f"Story {number} incomplete: {statuses}. "
            "Manual reconciliation required."
        )

    print("All predefined stories have been published.")
    return None


async def main():
    ledger = read(LEDGER)
    number = choose(ledger)

    if number is None:
        return

    topic = KONULAR[number - 1]
    video = await produce(topic)

    if not video.is_file() or duration(video) <= 1:
        raise RuntimeError("Produced video is missing or invalid.")

    story = json.loads(
        (video.parent / "hikaye.json").read_text(
            encoding="utf-8"
        )
    )

    STAGING.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, STAGING / "masal_short.mp4")

    metadata = {
        "number": number,
        "topic": topic,
        "title": str(story.get("title") or topic).strip()
        + " | MinoMasal",
        "video": "masal_short.mp4",
        "mode": "daily_staging",
    }

    (STAGING / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )

    print(f"STAGED story #{number}: {topic}; no upload yet")

    with open(
        os.environ["GITHUB_OUTPUT"],
        "a",
        encoding="utf-8",
    ) as out:
        out.write(f"number={number}\n")


if __name__ == "__main__":
    asyncio.run(main())
