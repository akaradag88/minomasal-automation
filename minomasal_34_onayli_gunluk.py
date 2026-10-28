"""Replace only the GitHub Actions stage command; #34 uses approved JSON.

Publishing remains in the existing minomasal_dual_publish.py step.
All other story numbers delegate to the unmodified daily coordinator.
"""
import asyncio
import json
import os
from pathlib import Path
import shutil

import minomasal as mm
import minomasal_daily_live as daily
from minomasal_ledger import read

APPROVED = Path('hikaye_02.json')
TITLE = 'Orman Okulunda Cumhuriyet Coşkusu'

async def main():
    ledger = read(daily.LEDGER)
    number = daily.choose(ledger)
    if number != 34:
        if number is not None:
            print(f'#34 icin ozel yol gerekmiyor. Siradaki #{number}; standart gunluk sistem kullaniliyor.')
            await daily.main()
        return
    if not APPROVED.exists():
        raise RuntimeError('Onayli hikaye_02.json bulunamadi. Yeni hikaye uretilmeyecek.')
    story = json.loads(APPROVED.read_text(encoding='utf-8'))
    mm.validate(story)
    if (story.get('title') != TITLE or len(story['scenes']) != 10
            or mm.KONULAR[33] != TITLE):
        raise RuntimeError('#34 onayli JSON baslik veya sahne sayisi farkli; yayina gecilmedi')
    text=' '.join(s['narration'] for s in story['scenes'])
    if 'Atatürk' not in text or '29 Ekim' not in text:
        raise RuntimeError('Onayli Cumhuriyet Bayrami anlatiminda zorunlu bilgiler eksik')
    print('#34: Onayli hikaye_02.json secildi. 10 sahne, karakter metni DEGISTIRILMEZ.')
    print('Ozel gun istisnasi: onayli JSON 5 karakter iceriyor; genel 4 karakter kurali burada uygulanmaz.')
    from minomasal_sami_hizalama_v2 import aligned_scene_voices
    mm.voices = aligned_scene_voices
    # Eski video ve ses onbellekleriyle karismasin; yalnizca #34 icin ayri kok klasor.
    mm.ROOT = Path('minomasal_34_onayli_data').resolve()
    mm.ROOT.mkdir(parents=True, exist_ok=True)
    video = await mm.produce(TITLE, supplied_story=story)
    if not video.is_file() or mm.duration(video) <= 1:
        raise RuntimeError('34 video olusmadi veya gecersiz')
    actual=json.loads((video.parent/'hikaye.json').read_text(encoding='utf-8'))
    if actual != story:
        raise RuntimeError('#34 hikaye metni degismis. Guvenli durdurma.')
    if not (video.parent/'altyazi.srt').is_file():
        raise RuntimeError('#34 altyazi dosyasi eksik. Yayin yapilmadi.')
    daily.STAGING.mkdir(parents=True,exist_ok=True)
    shutil.copy2(video, daily.STAGING / 'masal_short.mp4')
    meta={'number':34,'topic':TITLE,'title':TITLE+' | MinoMasal',
          'video':'masal_short.mp4','mode':'daily_approved_special_day'}
    (daily.STAGING/'metadata.json').write_text(
        json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('STAGED story #34. Sonraki workflow adimi yayinlayabilir.')
    # GitHub Actions dual publisher is triggered only after successful stage.
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
        out.write('number=34\n')

if __name__ == '__main__':
    asyncio.run(main())
