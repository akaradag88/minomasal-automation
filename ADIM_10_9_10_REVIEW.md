# Adım 10.9.10 — ayrı denetim tokenı ve güvenli kota kontrolü

11 Kasım 2026, PR #4. Main'e birleştirme, LIVE workflow, ödeme veya video yayını yok.

## Gerçek denetim sonucu

[Manuel çalışma 43057001400](https://github.com/akaradag88/minomasal-automation/actions/runs/43057001400)
yalnız `cloudflare_test=true`, `generate_images=false` ile PR dalında çalıştırıldı.
Üç Secret da mevcut; ancak üretim ve denetim tokenları eşit bulundu.
`usage_token_must_be_distinct` koruması HTTP isteğinden önce durdurdu.
Bu çalışmada Cloudflare istek sayısı **0**, inference sayısı **0**, görsel sayısı **0**.
Önceki model kataloğu HTTP200 sonucu geçerli tarihsel kanıttır; önceki abonelik
HTTP403 sorununun giderildiği bu çalışmayla doğrulanamadı. Kalan kota bilinmiyor.
Güvenli rapor: [cloudflare-audit-report.json](docs/adim_10_9_10/cloudflare-audit-report.json).
Actions artifact: `cloudflare-flux-test-43057001400` (yalnız rapor).

## Uygulanan değişiklikler

- Üretim tokenı yalnız model kataloğu/inference için kullanılır. Ayrı
  `CLOUDFLARE_USAGE_TOKEN` abonelik GET ve kullanım GraphQL POST isteklerini yapar.
- Eksik/eşit token, bilinmeyen veya ücretli abonelik, doğrulanamayan kullanım ya da
  yetersiz kota üretimi durdurur. Panelden elle verilen Free onayı bu kontrolleri atlatamaz.
- Ortak kullanım modülü UTC günündeki tüm model tüketimini sorgular. Analytics
  gecikebilir: kalan değer tahmindir, yetkili bir bakiye garantisi olarak sunulmaz.
- İki sahnede aynı turuncu tilki, yeşil göz, mavi atkı ve tamamen kırmızı oyuncak
  kamyon tanımı kullanılır. İstenen seed 1234, steps 4; en fazla iki inference
  isteği, inference tekrar denemesi yok. Her görsel öncesi gün/kota tekrar kontrol edilir.
- Üretim sağlayıcısı da ayrı tokenla plan/kota ön kontrolünü uygular. Otomasyon
  onayı `approved_for_automation=[]` olarak korunur; kalite kanıtı olmadan açılmaz.
- Abonelik API'sinde opsiyonel `result_info` alanının yokluğu tek başına hata
  sayılmaz; metadata varsa eksik sayfa/yanlış toplam reddedilir.

Defter, günlük kilit, ses, render, YouTube ve Instagram kodu bu adımda değişmedi.
Yayın workflow'una yalnız ayrı denetim Secret ortam değişkeni eklendi; tetiklenmedi.

## Kota ve kullanım koşulları

[Resmî fiyatlandırma](https://developers.cloudflare.com/workers-ai/platform/pricing/):
Free planda günde 10.000 Neuron; limit aşımında durur. Paid planda aşım ücretlidir,
bu yüzden ücretli/bilinmeyen plan reddedilir. Sıfırlama 00:00 UTC.
FLUX.1 schnell: 512 piksel karo başına 4,8 ve adım başına 9,6 Neuron.
1024×1024 ve 4 adım varsayımıyla yaklaşık 57,6/görsel, 576/10 görsel.
Bu kapasite hesabıdır; hesabın gerçek kalan kotası veya kesintisiz hizmet garantisi değildir.
Üretimde retry/kalite yeniden üretimleri için daha yüksek güvenlik rezervi kullanılır.

[Model belgesi](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/)
ve [model lisansı](https://huggingface.co/black-forest-labs/FLUX.1-schnell):
Apache-2.0 model lisansı ticari kullanıma izin verir; Cloudflare hizmet koşulları da geçerlidir.
İki gerçek görsel üretilmediğinden yüz/göz/atkı/kamyon tutarlılığı değerlendirilemedi.
Seed gönderilmesi tek başına karakter kimliğini garanti etmez.

## Testler ve gereken kullanıcı işlemi

` .venv-readiness/bin/python run_readiness_tests.py`: **107 test başarılı**.
Actions Ubuntu üzerinde odaklı **16 test başarılı**; ardından token ayrımı kapısı
beklendiği gibi çalışmayı durdurdu. Gerçek video üretimi/canlı yayın yok.
HTTP402/429/500, bozuk/eksik görsel, yayın kilidi, çift yayın ve numara koruması
mevcut çevrimdışı regresyon paketinde korunur.

Cloudflare panelinde yeni ve farklı bir denetim tokenı oluşturulmalı:
Account → Billing → Read ve Account → Account Analytics → Read;
Account Resources yalnız ilgili hesap. Bu değeri GitHub'da yalnız
`CLOUDFLARE_USAGE_TOKEN` Secret'ına kaydedin. Üretim tokenı
`CLOUDFLARE_API_TOKEN` ayrı kalmalı (Workers AI Read endpoint için belgelenmiş minimum).
Anahtarı sohbete göndermeyin. Sonrasında önce metadata denetimi, başarılıysa tek
bir en-fazla-iki-görsellik test yapılabilir. Bu adımda üretim testi başlatılmadı.

PR #4 taslak ve açık tutuldu. Teknik birleştirme çakışması yok; kota doğrulaması
ve gerçek karakter kalite değerlendirmesi tamamlanmadığı için canlıya hazır değil.
