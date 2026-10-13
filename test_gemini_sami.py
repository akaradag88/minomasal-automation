import os
import wave
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.generate_content(
    model="gemini-3.8-flash-tts",
    contents="Merhaba çocuklar! Bugün küçük bir kirpinin ormanda yaşadığı heyecan verici bir macerayı anlatacağım. Hazırsanız masalımız başlıyor!",
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Sami"
                )
            )
        ),
    ),
)

audio = response.candidates[0].content.parts[0].inline_data

if not audio or not audio.data:
    raise RuntimeError("Ses üretilemedi.")

with wave.open("minomasal_sami_test.wav", "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(24000)
    wav.writeframes(audio.data)

print("Sami ses testi başarılı!")
