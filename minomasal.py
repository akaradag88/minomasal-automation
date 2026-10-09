
# MinoMasal - GitHub Actions video otomasyonu
# Ilk asama: Guvenli ortam kontrolu

import os
from pathlib import Path

YAYIN_AKTIF = False
YOUTUBE_AKTIF = True

ROOT = Path("minomasal_data")
ROOT.mkdir(parents=True, exist_ok=True)

def main():
    print("MinoMasal otomasyonu baslatildi.")
    print("Video uretimi: Henuz aktif degil")
    print("YouTube yukleme: Kapali")

    gerekli_bilgiler = [
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REFRESH_TOKEN",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
    ]

    eksikler = [
        ad for ad in gerekli_bilgiler
        if not os.getenv(ad)
    ]

    if eksikler:
        print("Eksik ortam degiskenleri:", ", ".join(eksikler))
    else:
        print("Gerekli ortam degiskenleri mevcut.")

if __name__ == "__main__":
    main()
