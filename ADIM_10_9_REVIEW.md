# Adım 10.9 — Ücretsiz görsel sistemi, 10 Kasım 2026

**Sonuç:** Modüler sağlayıcılar ve sıfır ücret politikası hazırlandı. OVH SDXL ile
iki gerçek görsel ücretsiz üretildi; ancak karakter/sahne tutarlılığı kalite
onayını geçmedi. Yeni sağlayıcılar otomatik yayın için onaylanmadı. Bu dalı
birleştirmek, tek başına güvenilir ücretsiz günlük yayın sağlamaz. Main
birleştirilmedi; canlı yayın workflow'u veya sosyal medya API'si çalıştırılmadı.

## Güncel resmî belgelerden karşılaştırma

| Servis | Ücretsiz erişim ve günlük 10 görsel | GitHub Actions / sürdürülebilirlik | Ticari kullanım / tutarlılık |
|---|---|---|---|
| Cloudflare Workers AI, FLUX.1 schnell | Yenilenen 10.000 Neuron/gün; deneme kredisi değil. 1024² çıktı ve 4 adım varsayımıyla yaklaşık 57,6 Neuron/görsel, 10 görsel ≈576 Neuron. Diğer hesap kullanımları da kotayı tüketir. | REST ile hosted runner'da kullanılabilir. **Workers Free** kota bitince durur; Workers Paid aşım ücretlendirebilir ve bu adaptörde kabul edilmez. Hesap/anahtar olmadan gerçek test yapılmadı. | FLUX.1 schnell Apache-2.0; servis koşulları ayrıca geçerli. Metinden karakter kimliği garanti değil. Dokümante edilen bu API'de referans karakter/LoRA kontrolü yok. En güçlü kota adayı, kalite kazananı olduğu gösterilmedi. |
| OVHcloud SDXL | Güncel model kataloğu **Free**. Anonim erişim belgelenmiş: IP/model başına 2 istek/dakika; erişim anahtarıyla proje/model başına 400. Genel doküman ayrıca günlük toplam limit tanımlamıyor. Bu, gelecekte değişmeyecek bir taahhüt değil. | İki anonim gerçek istek başarılı. Adaptör hiçbir OVH hesabı/anahtarı göndermez. Katalog her paket öncesi tekrar kontrol edilir. Paylaşılan runner IP'si hız sınırına takılabilir; 10 görsel yaklaşık 5+ dakika planlanmalı, SLA/10 sahne testi yok. | SDXL Open RAIL++ koşulları ve kullanım sınırlamaları geçerli; ticari kullanım salt “açık kaynak” ifadesinden değil bu lisans/servis koşullarından değerlendirilir. İki sahnede kimlik ve nesne rengi kaydı; otomasyon onayı verilmedi. |
| ComfyUI, yerel SDXL/açık ağırlıklar | Yazılım ve yerel API ücretsiz; sürekli açık donanım, elektrik ve bakım ücretsiz değil. Comfy Cloud/partner API'leri ücretsiz alternatif sayılmadı. | Yerel GPU veya self-hosted runner/tünel gerekir. GitHub hosted runner'ın localhost'u kullanıcının laptop'u değildir. CPU modu daha yavaştır. Bu oturumda GPU/model/sunucu olmadığından gerçek test yok. | ComfyUI GPL-3.0; model/LoRA lisansları ayrıdır. Yerelde referans/IP-Adapter/LoRA ile daha güçlü kimlik kontrolü mümkün; bu PR güvenilirliği kanıtlanmamış custom node kurmaz. Uygulanan adaptör yalnız core SDXL düğümleri ve sabit seed kullanır. |
| Hugging Face Inference Providers | Güncel resmî fiyat sayfasında Free Users için aylık kredi **None**. PRO/Team abonelik kredisi ücretsiz hesap kotası değildir. | Bu hedef için kalıcı ücretsiz API kabul edilmedi; adaptör/gerçek çağrı eklenmedi. | Lisans ve görüntü kalitesi seçilen modele bağlı; ödeme olmadan kıyas testi yapılmadı. |
| Pollinations | Pozitif toplam bakiye, ücretsiz kredi kanıtı değildir. Önceki hesap incelemesinde bakiye HTTP403 nedeniyle okunamamıştı. | Mevcut anahtar korundu; bu adımda gerçek görüntü çağrısı yapılmadı. Varsayılan olarak devre dışı. | Yalnız doğrulanmış ücretsiz kredi, sıfır satın alınmış bakiye ve sınırlı anahtar bütçesiyle aday olabilir. Belirsiz fiyat/şema/izin durumunda durur. |

Resmî kaynaklar:

- [Cloudflare fiyat/kota](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Cloudflare FLUX schnell girdi/çıktı sözleşmesi](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/)
- [Cloudflare REST ve token izinleri](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)
- [Cloudflare salt okunur abonelik listesi, Billing Read](https://developers.cloudflare.com/api/resources/accounts/subresources/subscriptions/methods/get/)
- [FLUX.1 schnell model kartı ve Apache-2.0](https://huggingface.co/black-forest-labs/FLUX.1-schnell)
- [OVH SDXL ücretsiz model ve API örnekleri](https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/stable-diffusion-xl/)
- [OVH erişim/hız/toplam limit koşulları](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-capabilities)
- [SDXL Open RAIL++ lisansı](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md)
- [ComfyUI yerel sistem gereksinimleri](https://docs.comfy.org/installation/system_requirements)
- [ComfyUI yerel API](https://docs.comfy.org/development/comfyui-server/comms_routes)
- [ComfyUI yazılım lisansı](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE)
- [Hugging Face güncel fiyatlandırma](https://huggingface.co/docs/inference-providers/pricing)
- [Pollinations hesap/bakiye sözleşmesi](https://github.com/pollinations/pollinations/blob/main/APIDOCS.md#account)

Ücretsiz deneme/promosyon kredileri sürekli ücretsiz hizmet olarak kullanılmadı.
Hiçbir sağlayıcının gelecekteki fiyatı veya kesintisiz hizmeti garanti edilmiyor.

## Gerçek küçük kalite testi

Önce çevrimdışı testler çalıştırıldı. Ardından yalnız OVH SDXL kullanıldı:

- Hesap/anahtar/ödeme olmadan anonim erişim; güncel katalog fiyatı Free doğrulandı.
- Aynı karakter: küçük turuncu tilki, beyaz ağız çevresi, yeşil gözler, mavi tulum,
  kırmızı atkı. İki sahnede bu tanım değiştirilmeden kullanıldı.
- İlk sahne: sarı sulama kabıyla meşe fidanı. Yaklaşık **19,10 saniye**.
- İkinci sahne: aynı fidan yakınında orman yolunda tahta sepet. **24,25 saniye**;
  bu ölçü ikinci istek öncesindeki anonim hız sınırı beklemesini de içerir.
- İki kaynak 1024×1024; teslim edilen video görselleri 1080×1920 RGB JPEG.
- API maliyeti: ücretsiz anonim model, kullanıcı hesabına faturalama yok.
- Cloudflare anahtarı/ücretsiz plan kanıtı bulunmadığından ikinci sağlayıcıda
  gerçek üretim yapılmadı. ComfyUI için donanım/sunucu yok. Toplam **2 görsel**.

Görsel inceleme (otomatik ölçüm veya bilimsel kalite sıralaması değil):

| Kontrol | Gözlem |
|---|---|
| Genel estetik | İki görüntü de renkli masal kitabı görünümünde, teknik bütünlük doğru. |
| Karakter kimliği | İlk sahnede gözler koyu, ikinci sahnede yeşil; yüz oranları ve tulum tonu değişiyor. |
| Kıyafet rengi | Kırmızı atkı ikinci sahnede yeşil olmuş. |
| Sahneye sadakat | İlk sahnede fazladan tilki var; sulama kabı sarı değil ve karakterin elinde değil. |
| Dikey kompozisyon | Merkez kırpma ilk sahnedeki kenar sulama kabını kaybediyor. Kareden dikeye dönüşüm anlamsal kalite garantisi değil. |
| Karar | **Tutarlılık yetersiz; otomasyon için başarısız.** |

[İlk kaynak](docs/adim_10_9/ovhcloud/01.original.png) ·
[İlk dikey çıktı](docs/adim_10_9/ovhcloud/01.vertical.jpg) ·
[İkinci kaynak](docs/adim_10_9/ovhcloud/02.original.png) ·
[İkinci dikey çıktı](docs/adim_10_9/ovhcloud/02.vertical.jpg) ·
[Makine okunur süre/hash sonucu](docs/adim_10_9/ovhcloud/result.json)

Bu test, bütün 10 sahnelik masalın kalite veya servis güvenilirliğini kanıtlamaz.
Diğer sağlayıcılar çalıştırılmadığından ölçülmüş sağlayıcılar arası bir kazanan yok.

## Uygulama ve maliyet politikası

Mevcut make_images imzası korunur; uygulama minomasal_images.py'ye devreder.
Yeni bağımlılık gerekmiyor. Mevcut sahne metinleri ve story.characters içeriğinden
ortak karakter rehberi oluşturulur. Rehber her sahne prompt'unda aynıdır; kıyafet,
renk ve fiziksel özelliklerin değiştirilmemesi istenir. Modelin buna uyduğu
varsayılmaz. OVH/Cloudflare için belgelenmiş seed kontrolü kullanılmadığından
provenance içinde generation_seed=null; ComfyUI/Pollinations'ta seed gönderilir.

minomasal_images.json:

- order: ovhcloud → cloudflare → comfyui → pollinations. İlk ücretsiz erişim
  doğrulaması OVH ile yapıldı; bu sıra kalite üstünlüğü iddiası değildir.
- MINOMASAL_IMAGE_PROVIDERS ortam değişkeniyle sıra değiştirilebilir.
- approved_for_automation: **[]**. Canlı kalite onayı alan sağlayıcı yok.
  Hiçbiri onaylı değilse hikâye API'sine bile gitmeden güvenli durur.
- pollinations_enabled: **false**. Ücretli çağrı/fallback açan bir seçenek yok.
- Yerel operatörün sağladığı görseller sayım, boyut, boşluk ve bütünlük kontrolüyle
  kullanılabilir; üretim servisine gitmez.

Cloudflare için Secrets:

- CLOUDFLARE_ACCOUNT_ID
- CLOUDFLARE_API_TOKEN

Cloudflare token'ı Workers AI Read/Edit ve abonelik kontrolü için **Billing Read**
içermeli; Billing Write gerekmez. Repository variable
MINOMASAL_CLOUDFLARE_FREE_PLAN_CONFIRMED=true ancak Workers Free doğrulandıktan
sonra ayarlanmalı. Bu bayrak tek başına yeterli değildir: API'de tam listelenmiş
boş abonelik hesabı veya tam tanımlı sıfır fiyatlı Workers Free kaydı aranır.
Ücretli, bilinmeyen, kısmi veya okunamayan abonelik kaydı reddedilir. Bu muhafazakâr
kontrol başka aboneliği olan hesapları da reddedebilir; otomatik Paid aşımı yok.
Gerçek test için bu koşullarda bir hesap/anahtar henüz mevcut değil.

OVH adaptörü bilinçli olarak anahtar göndermez; yeni OVH Secret gerekmez.
ComfyUI yalnız loopback self-hosted URL kabul eder. COMFYUI_URL ve
COMFYUI_CHECKPOINT yapılandırılır; yalnız yerel safetensors checkpoint ve core
node'lar vardır. Bulut/partner/ücretli API node'ları yoktur. GPU kiralanmaz veya
kurulmaz. Üretim için model/karakter kalite onayı ayrıca gerekir.

Pollinations ancak ayrı etkinleştirme ve kalite onayından sonra, hesap/key
uçlarında sıfır satın alınmış bakiye, yeterli ücretsiz tier, sonlu anahtar bütçesi
ve yapılandırılmış istek maliyet sınırı doğrulanırsa kullanılabilir. Pozitif
bakiye tek başına kabul edilmez. Belge/yanıt şeması beklenen alanları sağlamazsa
üretim yoktur. pollinations_max_pollen_per_request bir yerel muhafazakâr tahmin
sınırıdır; API'ye fiyat üst sınırı olarak gönderilemez. Asıl sıfır para koruması
satın alınmış kredi olmaması ve anahtar bütçesidir. Bu yol gerçek çağrıyla
onaylanmadığından kapalı tutuldu.

## Hatalar, dosyalar ve yayın güvenliği

- 402/403: ilgili aday bu paket için durur; yeniden denenmez.
- 429/500/502/503/504: en fazla 3 deneme, 3 ve 6 saniye artan bekleme.
- ComfyUI queue POST sonrası belirsiz 5xx tekrar edilmez; iş kuyruğa alınmış
  olabilir. Salt okunur sorgular sınırlı tekrar kullanır.
- Yeni ücretsiz adaya geçerken **bütün sahneler o adayla yeniden üretilir**;
  eski adayın 1–9 görseli pakete karıştırılmaz. Kısmi denemeler silinmez.
- Görsel tamamlanmadan root paket manifest'i yazılmaz. Sağlayıcı, model, karakter
  rehberi ve hash'ler kaydedilir. Bozuk/değiştirilmiş cache durdurulur.
- Girdi min. kısa kenar 512, azami 16MP/20MB; dosya çözümleme, düz renk/boş çıktı,
  sahne sayısı ve 1080×1920 sonuç doğrulanır. Bu kontroller semantik kaliteyi ölçmez.
- Görsel sağlayıcı yapılandırması üretim parmak izine katılır; images.json ayrıca
  mevcut SHA-256 üretim makbuzuna bağlanır.
- Anahtarlar, HTTP yanıt gövdeleri veya ham bağlantı istisnaları loglanmaz.
- Seslendirme, render gövdesi, günlük kilit, defter, skipped 45/46, numara sırası,
  YouTube/Instagram yayın komutları ve saat ayarları değiştirilmedi.
- Bu depoda çalışan renderer FFmpeg; yeni Remotion kurulmadı veya renderer
  değiştirilmedi. Mevcut MP4/ses/görsel makbuzu ve çift yayın engelleri korunur.
- Kapsam görseldir: mevcut hikâye metni üretimi hâlâ Pollinations kullanabilir;
  Gemini TTS de korunur. Bu PR bütün video sürecinin ücretsiz olduğu iddiası taşımaz.

## Test ve teslim

```
.venv-readiness/bin/python run_readiness_tests.py
.venv-readiness/bin/python minomasal_ledger.py --mode check
git diff --check
```

90 çevrimdışı test geçti; ağ ve video render engelli test çalıştırıcısı kullanıldı.
Eski 402/429/500 regresyonları kaldırılmadı: yeni adaptörün HTTP davranışını test
edebilmek için ücretsiz-bütçe/kalite preflight'ı yalnız o testlerde mock edildi.
Üretim maliyet/kalite kapıları ayrı testlerle doğrulandı. Kısmi paket fallback,
cache hash, ücretsiz olmayan hesap/bakiye reddi, secret redaksiyonu, ComfyUI core
node ve yayın öncesi durma kapsandı. Gerçek kalite testi yalnız iki OVH görseli.

Önceki sentetik MP4 entegrasyon testi bu ağsız/render'sız çalıştırıcıda eskisi gibi
kapsam dışı. Gerçek MP4, ses veya sosyal medya gönderisi üretilmedi.

Kalite için sonraki somut adım: ücretsiz Workers Free hesabı ile iki sahnelik
FLUX testi veya yerel referans/LoRA kontrollü bir ComfyUI kurulumu. Bu PR
birleştirilmeden ve kalite doğrulanmadan mevcut main otomasyonu değişmez.
