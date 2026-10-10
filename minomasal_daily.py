"""MinoMasal daily coordinator. Default is a no-network, no-publish preflight.

Live mode is deliberately disabled pending an end-to-end review. This module
is additive: it does not change the existing minomasal.py or state files.
"""
import argparse
import json
from pathlib import Path

TOPICS = [
    'Paylaşmayı Öğrenen Sincap', 'Yalan Söyleyen Küçük Tilki',
    'Karanlıktan Korkan Tavşan', 'Dişlerini Fırçalamayan Timsah',
    'Her Şeye Kızan Minik Aslan', 'Oyuncaklarını Toplamayan Panda',
    'Sabırsız Küçük Kaplumbağa', 'Arkadaşını Dinlemeyen Maymun',
    'Ellerini Yıkamayı Unutan Ayıcık', 'Kaybetmeyi Sevmeyen Kaplan',
    'Sırasını Bekleyemeyen Minik Panda', 'Kaybolan Küçük Penguen',
    'Başkalarının Eşyalarını İzinsiz Alan Maymun', 'Yağmurdan Korkan Minik Kedi',
    'Her Şeyi Tek Başına Yapmak İsteyen Kunduz',
    'Yeni Okuluna Gitmek İstemeyen Tavşan',
    'Bulduğu Oyuncağı Sahibine Veren Kirpi',
    'Arkadaşına Kötü Söz Söyleyen Papağan',
    'Her Şeyi Ekrandan İzlemek İsteyen Ayıcık',
    'Küçük Karıncanın Büyük Hayali', 'Ormanı Kirleten Rakun',
    'Yemeğini Beğenmeyen Koala', 'Uçmaya Korkan Minik Kuş',
    'Özür Dilemeyi Öğrenen Fil', 'Teşekkür Etmeyen Küçük Geyik',
    'Uyumak İstemeyen Baykuş', 'Sebze Yemeyen Tavşan',
    'Sözünü Tutmayan Kunduz', 'Farklı Görünen Zürafa',
    'Yapamam Diyen Küçük Fare'
]


def load(path):
    file = Path(path)
    if not file.is_file():
        raise SystemExit(f'Güvenlik nedeniyle durduruldu: eksik durum dosyası: {path}')
    data = json.loads(file.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise SystemExit(f'Geçersiz JSON durum dosyası: {path}')
    return data


def youtube_done(item):
    return bool(item.get('youtube_uploaded') or item.get('uploads', {}).get('youtube', {}).get('status') == 'success')


def plan(state, preview):
    # Existing completed stories must not be regenerated just because IG is pending.
    for num, topic in enumerate(TOPICS, 1):
        row = state.get(str(num), {})
        if row.get('complete') or row.get('production_complete') or youtube_done(row):
            continue
        if preview.get(str(num), {}).get('youtube_uploaded'):
            continue
        return {'number': num, 'topic': topic, 'action': 'produce_new',
                'youtube': 'not_uploaded', 'instagram': 'not_published'}
    return {'action': 'no_new_story'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', default='minomasal_yayin_durumu.json')
    parser.add_argument('--preview', default='minomasal_onizleme_durumu.json')
    parser.add_argument('--mode', choices=['preflight', 'publish'], default='preflight')
    args = parser.parse_args()
    if args.mode != 'preflight':
        raise SystemExit('YAYIN KİLİTLİ: Güvenli yayın ve kalıcı durum kaydı entegrasyonu tamamlanmadı.')
    state, preview = load(args.state), load(args.preview)
    result = plan(state, preview)
    result['mode'] = 'preflight_only'
    result['publish_enabled'] = False
    result['youtube_known'] = [int(n) for n, item in state.items() if n.isdigit() and youtube_done(item)]
    result['instagram_known'] = [13]  # Manually verified; to be migrated to persistent IG state.
    result['warnings'] = [
        'YouTube public/private visibility must be explicitly configured before live mode.',
        'IG story 14 was processed but not published; do not mark it as published.',
        'GitHub Release assets require cleanup only AFTER confirmed publication.',
        'Cross-run state persistence and ambiguous API retries must be solved before live mode.',
        'Existing preview schedule must be disabled before enabling a future daily publisher.'
    ]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
