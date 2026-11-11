# Adım 10.9.7 — Cloudflare bağlantı ve kalite testi

> 11 Kasım güncellemesi: minimum token izinleri ve 403 ayrımı için
> [Adım 10.9.8 analizini](ADIM_10_9_8_REVIEW.md) esas alın. Önceki toplu izin önerisi
> üretim endpoint’inin minimum izni olarak değerlendirilmemelidir.

11 Kasım 2026, mevcut PR #4 dalı üzerinde. Main birleştirilmez.

## Yeni manuel test

`.github/workflows/minomasal-cloudflare-quality-test.yml` yalnız workflow_dispatch
ile ve yalnız PR #4 dalında çalışır. Varsayılan mod bağlantı/plan/kota kontrolüdür;
`generate_images=true` açıkça seçilirse bütün kontrollerden sonra iki sahne istenir.
Push, cron, pull_request, workflow_run veya otomatik bir üretim tetikleyicisi yok.

GitHub, default dalda olmayan yeni workflow'a dispatch için 404 döndürüyor.
Main'e dosya eklemeden test edebilmek için daha önce kayıtlı olan
`minomasal-pollinations-account-check.yml` dosyasının **yalnız PR dalındaki**
sürümüne `cloudflare_test` ve `generate_images` boolean girdileri eklendi.
`cloudflare_test=true` yalnız Cloudflare job'unu seçer. Pollinations job'u yalnız
main ref'inde ve cloudflare_test=false durumunda çalışabilir; bu testte atlanır.
Yeni bağımsız workflow ve bu manuel giriş aynı script/kontrolleri kullanır.

GitHub'ın kuralı:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch

## Sıfır ücret ve gizlilik kontrolleri

- Sadece CLOUDFLARE_ACCOUNT_ID ve CLOUDFLARE_API_TOKEN secret'ları ilgili adıma
  geçirilir. Çıktıda yalnız var/yok bilgisi, durumlar ve sayısal kullanım vardır.
- İstenen model tam olarak `@cf/black-forest-labs/flux-1-schnell`; başka model
  veya sağlayıcıya geçiş yoktur.
- Model erişimi GET models/search ile kontrol edilir; inference değildir.
- Abonelik listesi tam ve okunabilir olmalıdır. Ücretli/bilinmeyen/kısmi
  abonelikler reddedilir. Önceki PR'ın muhafazakâr ücretsiz plan politikası
  ortak doğrulama fonksiyonuna taşındı, gevşetilmedi.
- GraphQL ile UTC gün başlangıcından bugüne **tüm modellerin** toplam Neuron
  kullanımı istenir; hata veya yetki eksikliği sıfır kullanım kabul edilmez.
- Ücretsiz günlük kota 10.000 Neuron; bu küçük test için en az 1.000 Neuron
  boşluk aranır. Analytics gecikebilir; sıfır ücret koruması ayrıca sunucu
  tarafında aşımı faturalandırmayan Workers Free koşuluna dayanır.
- Her görselden önce kota tekrar okunur; gün/kota değişimi güvenli durur.
- En fazla iki inference POST; test üretim istekleri otomatik tekrar edilmez.
- API gövdeleri, hesap kimliği, anahtar veya ham istisna mesajları loglanmaz.
- Üretim makbuzu, defter, günlük kilit, ses, FFmpeg renderer, LIVE workflow ve
  YouTube/Instagram ayarları bu adımda değiştirilmedi. Depoya Remotion kurulmadı.

Gerekli token izinleri:

- Workers AI Read/Edit — model erişimi ve çağrısı.
- Billing Read — ücretli plan riskini dışlayan salt okunur abonelik kontrolü.
- Account Analytics Read — mevcut kullanım/kota sorgusu.

Billing Write veya herhangi bir ödeme işlemi gerekmez; kullanılmaz.
Yetki doğrulanamazsa görsel üretimi yapılmaz.

## Ticari kullanım ve ücretsiz kota kaynakları

- Cloudflare ücretsiz plan: 10.000 Neuron/gün; Paid plan aşımı ücretlendirebilir.
  https://developers.cloudflare.com/workers-ai/platform/pricing/
- FLUX.1 schnell Apache-2.0 ile ticari model kullanımına izin verir; Cloudflare
  servis koşulları ayrıca geçerlidir. FLUX dev lisansı bu modele uygulanmaz.
  https://huggingface.co/black-forest-labs/FLUX.1-schnell
- Billing Read ile abonelik doğrulaması:
  https://developers.cloudflare.com/api/resources/accounts/subresources/subscriptions/methods/get/
- Analytics Read izni:
  https://developers.cloudflare.com/analytics/graphql-api/getting-started/authentication/api-token-auth/

## Sahne ve artifact sözleşmesi

Ortak karakter: tek küçük turuncu tilki, beyaz ağız çevresi, yeşil göz, yuvarlak
surat, mavi tulum ve düz kırmızı atkı. Ortak kamyon: kırmızı kabin, sarı damper,
dört siyah teker, yazısız. Aynı tanım iki prompt'ta değiştirilmeden kullanılır.

1. Tilki orman yolunda oyuncak kamyonuyla oynar; kamyon tamamen görünür.
2. Aynı tilki ormanda kamyonunu arar; kamyon izleyiciye bir çalının yanında
   görünür, tilki başka yöne bakar. Böylece iki sahnede kamyon kıyaslanabilir.

Artifact adı `cloudflare-flux-test-<run_id>`, saklama 14 gün. Yalnız
`cloudflare_test_output/` yüklenir; hidden dosyalar hariçtir. Başarısızlıkta da
`report.json` kaydedilir. Üretim yapılırsa iki kaynak görüntü ve iki 1080×1920
JPEG eklenir. Otomatik semantik kalite onayı verilmez; gözle inceleme gerekir.

## Çevrimdışı testler

Başlangıçtaki 90 test geçti. Ek model/plan/kota, ücretli plan reddi, bozuk kota,
iki sabit sahne, secret redaksiyonu, yalnız manuel çalışma ve artifact sınırı
kontrolleriyle **104 test geçti**:

```
.venv-readiness/bin/python run_readiness_tests.py
```

İlk tam GitHub test denemesinde ffprobe eksikliği API adımından önce durdurdu.
Tam regresyon paketi yerelde 104 testle doğrulandı. Nihai manuel testte yalnız
requests, Pillow, PyYAML kurulur ve 14 odaklı çevrimdışı Cloudflare testi API
adımından önce çalışır; video/TTS araçları veya ağır SDK kurulmaz. Tam yerel
çalıştırıcı ağ bağlantılarını ve video render'ı engellemeye devam eder.
Gerçek bağlantı, plan/kota ve varsa kalite sonucu aşağıda kayıt altına alınır.

## Gerçek bağlantı testi sonucu

Çalışma: [43046808053](https://github.com/akaradag88/minomasal-automation/actions/runs/43046808053)
(11 Kasım, 18:17 Türkiye saati). Bu bir **generate_images=false** denetimidir.

- GitHub Secret varlık kontrolü: iki değer de tanımlı.
- Cloudflare model katalog bağlantısı: **doğrulandı**, model erişimi HTTP200.
- Ücretsiz plan abonelik kontrolü: **HTTP403**, doğrulanamadı.
- Mevcut kota: plan kontrolü başarısız olduğu için sorgulanmadı/doğrulanamadı.
  10.000 Neuron resmî günlük tahsistir; hesapta kalan miktar olarak sunulmuyor.
- Inference istek sayısı: **0**; iki sahne üretilmedi.
- Görsel kalite/yüz/renk/kıyafet/kamyon karşılaştırması: henüz değerlendirilemez.
- 14 odaklı çevrimdışı GitHub testi başarılı; yalnız gerçek hesap denetimi güvenli
  biçimde durduğu için workflow sonucu failure. Pollinations job'u skipped.
- Artifact yükleme başarılı: `cloudflare-flux-test-43046808053`, ID 13868065751,
  512 bayt, süresi dolmamış rapor ZIP'i. Bu denemede görüntü dosyası yoktur.

[Artifact](https://github.com/akaradag88/minomasal-automation/actions/runs/43046808053/artifacts/13868065751)
· [Kalıcı anahtarsız rapor](docs/adim_10_9_7/cloudflare-connection-report.json)

403, token'ın bu abonelik kaynağına erişemediğini gösterir; model erişimi başarılı
olsa da Billing Read izni/hesap kapsamı ayrıca kontrol edilmelidir. Ödeme veya
Paid plana geçiş gerekmez. Hesap kota sorgusu için Account Analytics Read de
hazır olmalıdır. Bu izinler doğrulanmadan üretim düğmesi/guard'ı atlanmamalıdır.

Kullanıcının yapacağı işlem: Cloudflare token ayarlarında yalnız ilgili hesap
kaynağı için Workers AI Read/Edit, Billing Read ve Account Analytics Read
izinlerini doğrulamak; token yenilenirse GitHub'daki mevcut CLOUDFLARE_API_TOKEN
Secret'ını güncellemek. Anahtar sohbet veya loglarda paylaşılmamalıdır.

Sonrasında PR dalı seçilerek manuel test tekrar çalıştırılabilir. Default dalda
kayıtlı salt okunur test girişinde `cloudflare_test=true`, ücretsiz doğrulamadan
sonra iki sahne için `generate_images=true` kullanılır. Ücretsiz plan veya kota
kontrolü yine başarısızsa hiçbir görsel isteği yapılmaz.

## PR ve canlı hazırlık durumu

PR #4 taslak/açık bırakıldı. Yeni manuel workflow, ortak ücretsiz-plan doğrulaması,
kota kontrolü, iki sabit karakter/kamyon sahnesi, artifact kaydı ve hata yönlendirmesi
aynı dalda tamamlandı. `approved_for_automation=[]` korunuyor; gerçek Cloudflare
görsel testi yapılmadan otomasyon kalite onayı verilmiyor. Main birleştirilmedi.
Canlı yayın workflow'u başlatılmadı; video, ses veya sosyal medya yayını yapılmadı.
