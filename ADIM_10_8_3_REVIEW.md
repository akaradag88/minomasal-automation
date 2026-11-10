# Adım 10.8.3 — 11 Kasım 2026 hazırlığı

## Yayın sırası ve günlük kilit

- İncelenen main: dd0f259a43bbaa5df2ec5cf2c5fbc113ed40293b.
- GitHub Daily LIVE run #47, ID 42851346811, 10 Kasım 19:07 Türkiye saati:
  success. Read-only daily preflight başarılı; generation, reservation, publication
  ve finish adımlarının tamamı skipped. Çalışma yeniden başlatılmadı.
- 2026-11-10.json kaydı status=skipped olarak aynen korundu. Yayın defteri,
  mevcut dosyalar ve 45/46 kayıtları değiştirilmedi.
- Defterin sıradaki normal içeriği #47: Kaybolan Oyuncak Kamyon. 45/46 için
  üretim ve yayın engeli korunuyor; numaralar yeniden kullanılmıyor.
- Gerçek defter/kilit dosyalarını kullanan bellekteki FakeContentsAPI ile:
  10 Kasım tekrar atlanır; 11 Kasım preflight=true; #47 tek kez reserved olur;
  ikinci rezervasyon reddedilir. Bu kontroller GitHub'a dosya yazmadı.
- İstanbul gece yarısı UTC 21:00'da gün değiştirir. 11 Kasım reserved kalırsa
  12 Kasım'ın da güvenli biçimde durduğu doğrulandı. Önceki skipped kaydı
  belirsiz rezervasyon sayılmadığı için 11 Kasım'ı engellemez.

## HTTP 402

- Mevcut make_images kodu değiştirilmedi. Mock HTTP 402 tek çağrıdan sonra
  bakiye/kredi hatası verir; bekleme, ses üretimi, render, tamam.json ve MP4 yok.
- Staging hata aldığında metadata ve GITHUB_OUTPUT number değeri yazmaz;
  sonraki rezervasyon/yayın workflow koşulları sağlanmaz.
- 429 ve 500 için mevcut 3 çağrı / 3 ve 6 saniye bekleme testleri tekrar geçti.
- Pollinations bakiyesi bu incelemede sorgulanmadı. 11 Kasım'da bakiye yetersizse
  üretim kontrollü olarak hata verir ve yayın yapılmaz.

## Actions ve Ubuntu

Resmî kaynaklardan 10 Kasım 2026 tarihinde doğrulanan kararlı sürümler:

- checkout v7.0.1: 3d3c42e5aac5ba805825da76410c181273ba90b1
- setup-python v7.1.0: 6d4fd22b20465ccc0f7354476588e8df7c9ca0e0

İki action'ın action.yml dosyası da node24 kullanıyor. Tam commit SHA ile
sabitlendi. Node24 en az Actions Runner 2.327.1 gerektirir; workflow'lar GitHub
hosted runner kullanır. checkout'un persist-credentials girdisi desteklenir;
kimlik bilgileri RUNNER_TEMP altında tutulur. Mevcut git fetch/commit/push akışı
normal shell adımlarında çalıştığı için Docker action'a özgü gereksinim yoktur.

ubuntu-latest etiketi 19 Ekim–19 Kasım arasında Ubuntu 26.04'e geçiriliyor.
51 workflow ubuntu-24.04'e sabitlendi; 11 Kasım öncesinde habersiz OS değişimi
önlendi. Python sürümü 3.11 olarak korundu. Resmî python-versions manifestinde
3.11.18 için hem Ubuntu 24.04 hem 26.04 x64 paketleri bulunuyor.

Yerel Python 3.11.17 ortamında requirements-minomasal.txt kuruldu; canlı
workflow'un ek YouTube ve faster-whisper bağımlılıkları dry-run ile çözümlendi.
Yerel ffmpeg/ffprobe varlığı, ass/zoompan/sidechaincompress/amix/alimiter
filtreleri, libx264/AAC encoder ve DejaVu Sans fontu salt okunur denetlendi.
Bu ortam Debian 13'tür; gerçek Ubuntu runner, Node action execution veya tam
render testi yapılmadı. Yeni Ubuntu 26.04'e tam uyumluluk iddiası yoktur;
24.04 sabitlemesi bu geçişi kontrollü bir sonraki çalışmaya bırakır.

Kaynaklar:
- https://github.com/actions/checkout/releases/tag/v7.0.1
- https://github.com/actions/setup-python/releases/tag/v7.1.0
- https://github.com/actions/runner-images/issues/14748
- https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md
- https://github.com/actions/python-versions/blob/main/versions-manifest.json

## Doğrulama ve yayın sınırı

```
uv venv .venv-readiness --python 3.11
uv pip install --python .venv-readiness/bin/python -r requirements-minomasal.txt PyYAML
.venv-readiness/bin/python run_readiness_tests.py
.venv-readiness/bin/python minomasal_ledger.py --mode check
git diff --check
```

55 test geçti. Test çalıştırıcısı socket bağlantılarını ve ffmpeg çalıştırmayı
engeller; eski sentetik MP4 entegrasyon testi özellikle kapsam dışıdır.
Gerçek veya sentetik video üretilmedi; sosyal medya/üretim API'si çağrılmadı.
YAML dosyaları parse edildi ve main ile karşılaştırılarak yalnızca iki action
referansı ile runner etiketinin değiştiği doğrulandı. YouTube/Instagram
komutları, secret referansları, public gizliliği, permissions, concurrency,
main koşulu ve günlük kilit koşulları korundu.

Daily LIVE hâlâ dış cron-job.org workflow_dispatch çağrısı bekler. Bu dış
zamanlayıcının 11 Kasım çağrısını yapacağı bu incelemede doğrulanamaz; ayarları
ve tetikleme yöntemi değiştirilmedi. Hiçbir workflow tetiklenmedi.

Bu dal birleştirilene kadar yalnızca mevcut main korumaları etkindir;
Node24 ve Ubuntu sabitlemesi inceleme dalındadır.
