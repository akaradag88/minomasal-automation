"""Explicit live voice smoke command, never an import-time API request."""
import wave
from minomasal_sami_tts_interactions import create_sami_wav

def main():
    path=create_sami_wav("Merhaba çocuklar. Bugün Tonton ile sakin kalıp yolumuzu bulmayı öğreneceğiz.","minomasal_sami_test.wav")
    with wave.open(str(path),'rb') as sound:
        print('Sami WAV verified:',sound.getframerate(),'Hz,',round(sound.getnframes()/sound.getframerate(),2),'seconds; human listening required.')

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Live TTS test stopped safely; free account confirmation or synthesis failed. Details withheld.') from None
