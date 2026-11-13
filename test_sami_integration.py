
import asyncio
import tempfile
from pathlib import Path

from minomasal import voices

story = {
    "scenes": [
        {
            "narration": (
                "Merhaba çocuklar! Bugün küçük bir kirpinin "
                "ormanda yaşadığı heyecan verici bir macerayı "
                "anlatacağım. Hazırsanız masalımız başlıyor!"
            )
        }
    ]
}

async def main():
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        results = await voices(story, folder)

        audio, seconds, words = results[0]

        assert audio.exists(), "MP3 dosyası oluşturulamadı."
        assert seconds > 1, "Ses süresi geçersiz."
        assert isinstance(words, list), "Altyazı verisi geçersiz."

        print(f"SAMI TEST BASARILI - Sure: {seconds:.1f} saniye")

if __name__ == '__main__':
    try:asyncio.run(main())
    except Exception:raise SystemExit('Live voice test stopped; details withheld, no publication.') from None
