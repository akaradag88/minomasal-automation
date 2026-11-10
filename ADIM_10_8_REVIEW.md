# Adım 10.8 inceleme notları

- 402: bakiye/kredi yetersizliği, tek çağrı; ücretli alternatif yok.
- 429 / 500 / 502 / 503 / 504: en fazla üç çağrı, 3 ve 6 saniye bekleme.
- Bağlantı hataları ve servis yanıt gövdeleri/anahtarları loglanmaz.
- Render öncesi sahne/görsel/ses sayısı ve dosyaları doğrulanır. MP4 ses/video
  akışları ve tam çözümlenebilirliği denetlenir. Üretim kanıtı dosyaları SHA-256
  ile bağlar; eksik/değişmiş varlıklar yayın öncesinde engellenir.
- Eski staging/cache kanıtsızsa güvenli biçimde durur. Manuel staging arşivleri
  artık production_assets ve *.production.json dosyalarını da içermelidir.
- 45 ve 46 numaraları skipped olarak korunur, üretimde ve yayıncıda reddedilir.
  2026-11-10 günlük kaydı skipped; sonraki günleri belirsiz kilit gibi engellemez.
- Günlük ve manuel çift-platform workflow'ları aynı sabit concurrency grubunu
  kullanmaya devam eder (cancel-in-progress: false). İkisine de main dalı koşulu
  eklendi. Dış çağrı öncesindeki defter commit/push ve ambiguous koruması korunur.
- Numara atlama reddedilir; iki platformda yayımlanmış kayıt yeniden yüklenmez.
- Kullanıcı onayıyla 46 da atlandı. Yayın defterine göre sonraki içerik
  normal masal #47: Kaybolan Oyuncak Kamyon.

Doğrulama (gerçek API / sosyal yayın yok):

```
.venv/bin/python -m unittest test_minomasal_10_8 test_minomasal_gunluk_kilit test_minomasal_v4 test_minomasal_v4_47_revize test_minomasal_v4_47_sureklilik test_minomasal_v4_mantik_kontrol
```

47 test geçti. FFmpeg ile yerel sentetik MP4/ses üretildi; varlık taşıma,
eksik görselle yayın engeli ve bozuk MP4 doğrulandı. HTTP çağrıları mock edildi.
Canlı workflow çalıştırılmadı. Bu dal birleştirilmeden main otomasyonu değişmez.
