"""No-network tests for optional V4 titles and protected 10 November stories."""
import json
from pathlib import Path
import tempfile
import unittest

from minomasal_v4_baslik import apply_title, load_config, text_supports_title

TOPICS = ['example'] * 60
for number, topic in {
    45: "Küçük Baykuş Atatürk'ü Öğreniyor",
    46: "Orman Okulunda Atatürk'ü Anma Günü",
    47: 'Kaybolan Oyuncak Kamyon',
    48: 'İlk Görevine Çıkan İtfaiye Aracı',
    49: 'Sabırsız Küçük Yarış Arabası',
    50: 'Çamura Saplanan Traktör',
    52: 'Küçük Beton Mikserinin Büyük Görevi',
    55: 'Küçük Vinç ve Yüksek Kule',
    60: 'Köprü Yapan İş Makineleri',
}.items():
    TOPICS[number - 1] = topic


def story_with(text):
    return {'title': 'Eski Başlık', 'scenes': [{'narration': text, 'visual': text, 'sfx': 'none'} for _ in range(10)]}


class V4Tests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.stage = self.root / 'staging'
        self.stage.mkdir()
        (self.stage / 'masal_short.mp4').write_bytes(b'fake video fixture, not published')

    def metadata(self, n):
        data = {'number': n, 'topic': TOPICS[n-1],
                'title': 'Eski Başlık | MinoMasal', 'mode': 'quality_v3_staging',
                'video': 'masal_short.mp4'}
        (self.stage / 'metadata.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return data

    def read_title(self):
        return json.loads((self.stage / 'metadata.json').read_text(encoding='utf-8'))['title']

    def test_config_schema_and_whitelist(self):
        cfg = load_config()
        self.assertEqual(set(cfg['stories']), {'47','48','49','50','52','55','60'})
        self.assertNotIn('kepçe', cfg['stories']['60']['publish_title'].lower())

    def test_47_title_applied_only_when_story_matches(self):
        self.metadata(47)
        result = apply_title(self.stage, 47, story_with('Oyuncak kamyon oyuncak şantiyede kayboldu.'), topics=TOPICS)
        self.assertEqual(result, 'applied')
        self.assertIn('Şantiyede Kayboldu', self.read_title())

    def test_47_story_mismatch_preserves_original(self):
        self.metadata(47)
        result = apply_title(self.stage, 47, story_with('Oyuncak kamyon bahçede mutlu oldu.'), topics=TOPICS)
        self.assertEqual(result, 'skipped')
        self.assertEqual(self.read_title(), 'Eski Başlık | MinoMasal')

    def test_45_and_46_always_preserved(self):
        for n in (45, 46):
            self.metadata(n)
            self.assertEqual(apply_title(self.stage, n, story_with('Şantiye'), topics=TOPICS), 'not_configured')
            self.assertEqual(self.read_title(), 'Eski Başlık | MinoMasal')

    def test_topic_mismatch_aborts_without_writing(self):
        self.metadata(47)
        obj = json.loads((self.stage / 'metadata.json').read_text(encoding='utf-8'))
        obj['topic'] = 'Bambaşka konu'
        (self.stage / 'metadata.json').write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Staging topic'):
            apply_title(self.stage, 47, story_with('Şantiyede kayboldu.'), topics=TOPICS)
        self.assertEqual(self.read_title(), 'Eski Başlık | MinoMasal')

    def test_60_approved_cast_only(self):
        self.metadata(60)
        story = story_with('Traktör ve Vinç köprüyü tamamlamak için çalıştı.')
        self.assertEqual(apply_title(self.stage, 60, story, topics=TOPICS), 'applied')
        self.assertIn('Traktör ve Vinç', self.read_title())

    def test_out_of_scope_unmodified(self):
        self.metadata(51)
        self.assertEqual(apply_title(self.stage, 51, story_with('Bir çekici'), topics=TOPICS), 'not_configured')
        self.assertEqual(self.read_title(), 'Eski Başlık | MinoMasal')


if __name__ == '__main__':
    unittest.main()
