"""Conservative wrapper around the EXISTING MinoMasal Quality V3 stage.

The entire current stage remains authoritative. This file adds optional prompt
hints for configured story numbers and a guarded publishing-title override.
The independent dual-platform publisher stays unchanged.
"""
import argparse
import os
from pathlib import Path
import runpy

from minomasal_v4_baslik import apply_title, load_config, preflight


def install_prompt_guidance():
    import minomasal_kalite_v2 as quality
    entries = load_config()['stories']
    previous_rules = quality.prompt_rules

    def v4_rules(topic, all_topics):
        baseline = previous_rules(topic, all_topics)
        try:
            num = all_topics.index(topic) + 1
        except ValueError:
            return baseline
        entry = entries.get(str(num))
        if entry is None or entry['topic'] != topic:
            return baseline  # #45/#46 and all other stories are 100% unchanged.
        return (baseline + '\n\nV4 HIKAYE ANLATIMI (yapıyı bozma):\n'
                '- İlk sahnede küçük bir olay veya merak uyandıran sorun doğrudan başlasın.\n'
                '- 10 sahne ve 75-110 anlatım kelimesi kuralını KORU.\n'
                '- İlk 3-5 saniyede sorun; ortada karakterin kararı; sonda çözüm.\n'
                '- Aynı onaylı karakter isimleri ve sabit fiziksel görünüşleri kullan.\n'
                '- NARRATION ve English VISUAL aynı somut olayı göstersin.\n'
                '- Video başlığında vaat edilen olay, hikâyede gerçekten yaşansın.\n'
                '- Ek bir ana karakter, tehlike, korku, şiddet, trafik riski oluşturma.\n'
                '- Ek hikâye yönlendirmesi: ' + entry['editorial_hint'] + '\n')

    quality.prompt_rules = v4_rules


def run_daily_stage():
    output = os.environ.get('GITHUB_OUTPUT')
    if not output:
        raise RuntimeError('Canlı stage için GitHub Actions GITHUB_OUTPUT bulunamadı; yayın yapılmadı.')
    output_path = Path(output)
    before = output_path.read_text(encoding='utf-8') if output_path.exists() else ''
    install_prompt_guidance()
    # Run the current installed V3 stage, not a stale copied version.
    runpy.run_module('minomasal_gunluk_kalite_stage_v3', run_name='__main__')
    after = output_path.read_text(encoding='utf-8')
    if not after.startswith(before):
        raise RuntimeError('GITHUB_OUTPUT beklendiği gibi ilerlemedi.')
    output_lines = after[len(before):].splitlines()
    staged = [v for v in output_lines if v.startswith('number=')]
    if not staged:
        print('V4: yeni hikâye üretilmedi; staging başlığı değiştirilmedi.')
        return
    if len(staged) != 1:
        raise RuntimeError('V3 stage birden fazla numara yazdı; yayın güvenliği için durduruldu.')
    number = int(staged[0].split('=', 1)[1])
    # Metadata guard runs even for unconfigured numbers (no-op for #45, #46).
    result = apply_title(stage_dir='staging', number=number)
    print(f'V4 stage metadata sonucu: {result}; sıra #{number}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Yerel dosya ve konu kontrolü, API/yayın yok.')
    args = parser.parse_args()
    if args.check:
        cfg = preflight()
        print('V4_PREFLIGHT_OK: izinli numaralar', ', '.join(sorted(cfg['stories'], key=int)))
        print('Özel hikâyeler 45/46 korunuyor; konu, ses, video, ledger ve yayın değişmedi.')
        return
    run_daily_stage()


if __name__ == '__main__':
    main()
