
"""MinoMasal 17. video Instagram kurtarma hazırlığı.

Bu dosya yalnızca kayıtları kontrol eder.
Video üretmez ve hiçbir platformda yayın yapmaz.
"""

import json
from pathlib import Path

LEDGER = Path("minomasal_platform_durumu.json")
NUMBER = "17"

def main():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    record = ledger["stories"][NUMBER]

    print("Hikâye:", record["topic"])
    print("YouTube:", record["youtube"]["status"])
    print("YouTube ID:", record["youtube"]["video_id"])
    print("Instagram:", record["instagram"]["status"])

    if record["youtube"]["status"] != "published":
        raise RuntimeError("YouTube kaydı doğrulanamadı.")

    if record["instagram"]["status"] != "pending":
        raise RuntimeError("Instagram kaydı beklenen durumda değil.")

    print("KONTROL BAŞARILI: Instagram kurtarma hazırlığı uygun.")

if __name__ == "__main__":
    main()
