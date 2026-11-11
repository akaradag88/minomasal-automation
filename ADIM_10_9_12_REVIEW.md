# Adım 10.9.12 — son Cloudflare doğrulaması

11 Kasım 2026, mevcut taslak PR #4 ve mevcut dal üzerinden devam edildi.
Main birleştirmesi, ödeme, plan yükseltmesi, LIVE workflow veya video yayını yok.

## Doğrulanan sonuçlar

- Üç Secret mevcut. Üretim ve denetim tokenları **farklı**; yalnız bu boole
  sonuç raporlandı. Token değeri, parçası veya özeti raporlanmadı.
- Üretim tokenıyla model katalog erişimi başarılı; tam FLUX.1 schnell modeli bulundu.
- Denetim tokenıyla `GET /accounts/{account_id}/subscriptions` başarılı,
  `success=true`, abonelik listesi boş. Önceki abonelik HTTP403 hatası tekrarlanmadı.
  Hesap ücretli aboneliği olmayan hesap olarak sınıflandırıldı (`unbilled_account`).
  Bu, adı açıkça Workers Free olan abonelik kaydı bulunduğu anlamına gelmez;
  ücretli abonelik yokluğu ve belgelenmiş varsayılan ücretsiz tahsis esas alındı.
- Denetim tokenıyla `POST /graphql` tüm modellerin UTC günlük Neuron sorgusu başarılı.
  11 Kasım 2026 16:34–16:35 UTC anında raporlanan kullanım **0**, günlük ücretsiz
  tahsis **10.000**, raporlanan kalan **10.000 Neuron**. Analytics gecikmesi nedeniyle
  bu kesin bir gerçek zamanlı bakiye garantisi değildir.

Başarılı salt okunur denetim:
[43059601080](https://github.com/akaradag88/minomasal-automation/actions/runs/43059601080).
Temizlenmiş rapor: [cloudflare-preflight-report.json](docs/adim_10_9_12/cloudflare-preflight-report.json).

## Düzeltilen şema uyumsuzluğu

İlk iki metadata denetiminde HTTP403 yoktu fakat ücretsiz plan kapısı durdu.
Cloudflare `result_info` nesnesini gönderiyor, opsiyonel `total_count` alanını
göndermiyordu. Önceki kod metadata nesnesi varsa bu alanı zorunlu tutuyordu.
[Resmî abonelik API şeması](https://developers.cloudflare.com/api/resources/accounts/subresources/subscriptions/methods/get/)
tek sayfalık liste ve metadata alanlarının opsiyonel olduğunu gösteriyor.
Artık boş metadata veya yalnız `count` içeren tutarlı nesne kabul edilir;
verilen count/total_count tutarsızsa, total_count null/bool ise ya da page 1 değilse
güvenli durulur. Ücretli/bilinmeyen abonelik kontrolü kaldırılmadı.
Teşhis çıktısı yalnız sabit boole/tür/sayı bilgileri içerir, ham yanıt içermez.

## Gerçek kalite testinde yeni engel

Ücretsiz plan/kota kontrolleri geçtikten sonra yalnız bir manuel kalite çalışması:
[43059736058](https://github.com/akaradag88/minomasal-automation/actions/runs/43059736058).
Her görsel öncesi gün/kota kontrolü ve 1.000 Neuron rezervi uygulandı.

İlk sahnenin `POST /accounts/{account_id}/ai/run/{model_name}` isteği
**HTTP400** döndürdü. Bu istek tekrar denenmedi. İkinci sahneye geçilmedi.
Bu adım toplamı: **1 inference isteği, 0 görsel**; sonraki inference denemesi yapılmadı.
400'ün kesin nedeni bilinmiyor: ham hata gövdesi hassas veri riski nedeniyle
loglanmıyor. Katalog erişimi, gerçek inference yetkisi ve hesabın model kullanımına
hazır olduğu için yeterli kanıt değildir. 400'ü token izni, ödeme gereksinimi veya
geçersiz seed hatası olarak kesinleştiren kanıt yok; bunlardan biri olmuş gibi raporlanmadı.

İstenen ortak karakter: turuncu tilki, beyaz ağız çevresi, yeşil gözler, mavi atkı,
kırmızı kabin ve kırmızı kasalı oyuncak kamyon; yalnız bir tilki, başka kıyafet yok.
Model `@cf/black-forest-labs/flux-1-schnell`, seed **1234**, steps **4**.
Görsel oluşmadığından yüz, göz, atkı, renk, kamyon ve fazla karakter kontrolü
yapılamadı. Seed göndermek tek başına karakter tutarlılığı garantisi değildir.

Artifact [cloudflare-flux-test-43059736058](https://github.com/akaradag88/minomasal-automation/actions/runs/43059736058/artifacts/13871839957)
yalnız güvenli raporu içerir; görsel içermez (14 günlük saklama).
Kalıcı rapor: [cloudflare-quality-report.json](docs/adim_10_9_12/cloudflare-quality-report.json).

## Kapasite ve test sonucu

[Güncel fiyatlandırma](https://developers.cloudflare.com/workers-ai/platform/pricing/):
günde ücretsiz 10.000 Neuron, sıfırlama 00:00 UTC. Free planda aşım durur;
Paid plana geçiş yapılmadı. FLUX schnell 512×512 karo başına 4,80 ve adım başına
9,60 Neuron. 1024×1024, dört adım varsayımıyla görsel başına **57,6**, iki test
görseli **115,2**, günlük on görsel **576 Neuron** tahmini. Bunlar kapasite
hesaplarıdır, gerçekleşmiş tüketim ölçümleri değildir. Çıktı ölçüleri, yeniden
üretim ve hesapta başka işler toplamı etkiler. API erişimi ve kalite engeli
çözülmeden sürdürülebilir günlük on görsel üretildiği söylenemez.

` .venv-readiness/bin/python run_readiness_tests.py`: **108 test başarılı**.
Actions kalite çalışmasında ayrıca **16 odaklı çevrimdışı test başarılı**;
sonraki workflow failure sonucu inference HTTP400'dür. Yeni regresyon testi
opsiyonel abonelik metadata alanlarını ve eksik/tutarsız sayfa reddini doğrular.

Bu adımda defter, günlük kilit, seslendirme, render, YouTube/Instagram ve
canlı workflow dosyaları değişmedi. Otomasyon onayı `approved_for_automation=[]`
olarak korundu. Bozuk/eksik görselle yayına geçiş yok. Çalışma alanı ve PR
taslağı incelemeye sunuldu; canlı otomasyona hazır olduğu ilan edilmedi.

Kalan işler: inference HTTP400'ün güvenli, ham hata/Secret göstermeyen teşhisle
çözülmesi; bundan sonra en fazla iki başarılı test görselinin üretilmesi ve
görsel karakter/nesne tutarlılığının incelenmesi; kalite uygunsa otomasyon onayı.
Mevcut kanıt tekrar Billing izni veya ödeme gerektiğini göstermiyor.
