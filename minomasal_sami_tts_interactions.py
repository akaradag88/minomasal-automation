"""Gemini 3.8 TTS (Interactions API) için MinoMasal tek-ses WAV üretimi.

Bu modül tek başına yayın yapmaz ve GitHub kayıtlarını değiştirmez.
Sami adının hesapta erişilebilir olup olmadığı gerçek API testinde doğrulanır.
"""
import base64
import os
from pathlib import Path
import wave

from google import genai

MODEL = "gemini-3.8-flash-tts"
VOICE = "Sami"
STYLE = (
    "Sıcak, samimi, neşeli bir Türkçe çocuk masalı anlatıcısı gibi "
    "doğal tempoda, bütün kelimeleri eksiksiz oku; "
    "sahneler arasında kısa ve doğal duraklamalar yap."
)


def create_sami_wav(transcript: str, output_path: str | Path) -> Path:
    """Metni birebir okutur; API'nin hazır WAV çıktısını güvenle kaydeder.

    İstek tek sefer yapılır. Kota veya ses adı hatasında otomatik farklı sese geçilmez.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY secret eksik.")
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError("TTS transcript boş olamaz.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    interaction = client.interactions.create(
        model=MODEL,
        input=[{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": transcript.strip(),
                "annotations": [{"type": "speech_metadata", "style": STYLE}],
            }],
        }],
        response_format={"type": "audio", "mime_type": "audio/wav"},
        generation_config={"speech_config": [{"voice": VOICE}]},
    )

    audio = getattr(interaction, "output_audio", None)
    data = getattr(audio, "data", None) if audio is not None else None
    if not data:
        raise RuntimeError("Gemini TTS çıktı sesi döndürmedi.")
    if isinstance(data, str):
        raw = base64.b64decode(data, validate=True)
    elif isinstance(data, bytes):
        raw = data if data.startswith(b"RIFF") else base64.b64decode(data, validate=True)
    else:
        raise RuntimeError("Beklenmeyen Gemini TTS ses verisi türü.")
    if not (len(raw) >= 44 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"):
        raise RuntimeError("Gemini TTS ses çıktısı geçerli WAV başlığı içermiyor.")
    temp = output_path.with_name(output_path.name + ".tmp")
    try:
        temp.write_bytes(raw)
        with wave.open(str(temp), "rb") as sound:
            if sound.getnframes() <= 0 or sound.getframerate() <= 0:
                raise RuntimeError("WAV verisi boş veya bozuk.")
        temp.replace(output_path)
    finally:
        if temp.exists():
            temp.unlink()
    return output_path
