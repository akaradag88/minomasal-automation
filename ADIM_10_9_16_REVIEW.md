# Adım 10.9.16 — karakter profili, sayım planı ve kırpmasız kadraj

11 Kasım 2026 (Türkiye), başlangıç commit'i 6679a8c, mevcut taslak PR #4.
Main birleştirmesi, günlük yayın workflow'u, sosyal yayın veya ödeme yok.

## Önceki iki görselin analizi

Adım 10.9.15'in orijinalleri ve üretim raporu incelendi. FLUX isteği yalnız
prompt içeriyordu; seed/width/height/steps gönderilmiyordu. Kaynaklar 1024×1024.
İlkinde tek tilki/kamyon fakat Mino yazısı, ikincide iki kamyon ve farklı yüz,
atkı ve kamyon tasarımı vardı. Eski ikinci sahne promptu aranan kamyonu hem
arama hedefi hem ayrı bir görünür nesne gibi tekrar tarif ediyordu. Bu olası
katkıdır, modelin içsel nedenselliğini kanıtlamaz. Adın promptta geçmesi de
istenmeyen yazıyla uyumludur; kesin neden olduğu iddia edilmez.
Eski 9:16 merkez kırpma görüntünün yanlarını kesiyordu.

## Uygulanan mimari

`minomasal_flux_quality_profile.json` pilot masalın ortak profilini ve iki
açık sahne envanterini içerir. Tilki: turuncu kürk, beyaz yanak/göğüs/kuyruk
ucu, koyu kulak uçları, yuvarlak baş, kısa beyaz oval ağız, küçük siyah burun,
badem biçimli zümrüt yeşil gözler, kısa yuvarlak gövde ve küçük turuncu patiler.
Kıyafet: tek düz kobalt mavisi atkı, basit düğüm, iki kısa düz uç; başka aksesuar
yok. Kamyon: tek kırmızı köşeli oyuncak damperli, kırmızı düz tavan/kasa,
açık mavi camlar, iki sarı yuvarlak far, iki yatay çizgili gri ızgara, dört
siyah lastik/koyu gri jant, boyu tilkinin üçte biri. Yüzeyler işaretsiz.

`minomasal_visual_profile.py` şema/sürüm, tüm zorunlu fiziksel özellikler,
her varlık için görünür sayı ve azami sayıyı doğrular. İki sahne de tam
**1 tilki + 1 kamyon** ister. Eksik/negatif/fazla/bool veya bilinmeyen varlık
sayısı API'den önce reddedilir. Aynı kimlik bloğu iki promptta aynen kullanılır;
yalnız eylem değişir. Anahtar sırasından bağımsız profil özeti/prompt üretilir.
Prompt uzunluğu 1439/1508 karakter; 2048 üstünde sessiz kesme yerine durulur.

Yeni prompt bir ad yazdırmaya teşvik etmez; sayım, sabit tasarım, eylem, kadraj,
tek araç ve yazı/logo/filigran/etiket/ek nesne kısıtlarını ayrı bloklarda verir.
Bu kısıtlar prompt metnidir; desteklenmeyen negative_prompt API alanı eklenmez.
Arama sahnesi artık tek aracın konumu ve tilkinin farklı yöne bakışıyla tarif
edilir. Karakter gövdesi ve araç tamamen görünür, her kenarda %12 boşluk istenir.

Mevcut make_images arayüzü korunur. İsteğe bağlı story.visual_profile ve
scene.visual_inventory sağlanırsa bütün sahne promptları API'den önce kurulur
ve doğrulanır; profil/inceleme sözleşmesi manifest'e bağlanır. Genel masal
üreticisi bu alanları henüz kendiliğinden doldurmaz. Mevcut hikâyeler için
eski karakter açıklaması yolu korunur; pilot tilki bütün masallara uygulanmaz.
Profilün normal üretim planına taşınması da canlıya geçiş öncesi değerlendirilmelidir.

Cloudflare kare kaynakları artık **contain** ile 1080×1920 tuvale bütün olarak
yerleştirilir: 1024² kaynak için içerik kutusu x=54,y=474,w=972,h=972.
Dış tuvalde %5 koruma payı ve düz koyu yeşil mat dolgu vardır. Mevcut renderer
%2–8 merkez zoom uygular; 5% dış pay, kaynak köşelerini maksimum zoom'un
görünür alanı içinde tutar. Bu geometri MP4 oluşturmadan test edilir; video
ayarları değiştirilmez. Kaynak kenarı kesilmez; yeni arka plan
veya bulanık kopya karakter üretilmez. Bu native 9:16 üretim/outpainting değildir;
kare görselin dikey tuvale kayıpsız kadrajla yerleşimidir, mat alanlar bir
tasarım ödünleşimidir. Diğer sağlayıcıların/yerel yolun mevcut crop davranışı
korunur. Önbellek kimliği güncellendi; eski kırpılmış çıktı yeni profil/kadraj
sonucu gibi tekrar kullanılmaz, önceki denemeler silinmez.

## FLUX referans ve seed sınırı

[Resmî Cloudflare FLUX.1 schnell belgesi](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/)
Text-to-Image, prompt ve opsiyonel steps tanımlar; referans görüntü, image,
image_url, strength, mask veya image-to-image girdisi belgelemiyor. Bu yüzden
bu endpoint'e bu alanlar gönderilmez; referans güdümlü üretim desteği olduğu
iddia edilmez. Bu sonuç Cloudflare servisinin bu model arayüzüne aittir;
yerel açık ağırlıklarla farklı araçların yapabilecekleriyle karıştırılmaz.

Seed örnek kodda var, parametre listesinde yok; mevcut minimum istekte
gönderilmez. Seed destekleyen başka bir motorda dahi aynı seed değişen prompt,
poz veya arka planda yüz/nesne kimliğini sabitlemez. Tekrarlanabilirlik model
sürümü, sampler ve diğer parametrelere de bağlıdır. Seed referans görüntünün
yerini tutmaz; karakter tutarlılığı garantisi olarak raporlanmaz.

## Alternatiflerin karşılaştırması

| Yöntem | Kimlik/kalite | API maliyeti ve ücretsiz kota | Otomasyon / sınırlama |
|---|---|---|---|
| Tek referansla doğrudan sahne üretimi | Uygun kimlik koşullandırma ile potansiyel olarak güçlü; garanti değil | Cloudflare bu endpoint'te belgelenmiyor; başka servis/yerel motorun kota/lisansı ayrıca doğrulanmalı | Bu PR'da mevcut özellik değil; ücretli servise otomatik geçilmez |
| Sabit profil + yapılandırılmış prompt | Stil/renk ve tek nesne niyetini güçlendirir; piksel kimliği ve sayım garantisi yok | Mevcut 1024²/4 varsayılan adımla ~57,6 Neuron/sahne, ~576/10 sahne | Uygulanan ilk aşama; API kolay, semantik inceleme gerekli |
| Arka planı karakterden ayrı üretme | Nesne sayısı ve yerleşim yerel kompozitte denetlenebilir; ışık/perspektif uyumu gerekir | Karakter her sahnede yeniden üretilirse maliyet artar ve kimlik yine değişebilir; onaylı karakter tekrar kullanılırsa yalnız arka plan maliyeti | Maskeleme, katmanlama ve gölge/örtüşme tasarımı gerektirir; henüz uygulanmadı |
| Aynı onaylı karakter ve kamyon kesitini sahnelere yerleştirme | Aynı asset piksel kimliğini en güçlü korur; poz/ifade çeşitliliği sınırlı | Aynı asset'i yapıştırmak API kotası tüketmez; ilk asset ve 10 arka plan yaklaşık 1+10 görsel kapasitesi; elektrik/insan emeği sıfır değildir | Önerilen sonraki sıkı kimlik aşaması. Onaylı alfa maskesi/poz seti, boyut/konum ve arka plan temizliği doğrulanmalı |

Bu adımda alternatif referans/segmentasyon/kompozit yolları gerçek API ile
test edilmedi; yeni model veya servis entegre edilmiş gibi sunulmaz.
Yerel ComfyUI referans workflow'u ayrıca uygun model/eklenti/lisans ve GPU
doğrulaması ister; mevcut text-to-image adaptörü otomatik olarak bu desteği kazanmaz.

## Otomatik kontrolün sınırı

Otomatik: profil ve plan şeması, planlanan sayım, prompt uzunluğu, dosya
bütünlüğü, asgari boyut/tek renk reddi, hash ve tuval geometrisi. Sentetik
köşe renkleriyle bütün kaynak köşelerinin korunduğu test edilir.

**Otomatik değil:** gerçek nesne/karakter sayımı, yüz ve kamyon kimliği, yazı/
logo/filigran tespiti, pozun anlatıma uygunluğu veya kaynağın kendi içinde
zaten kırpılmış olup olmadığı. OCR/nesne algılama/kimlik modeli kurulmadı;
profilde sayı 1 olmasının görselde sayı 1 olduğunu kanıtlamadığı rapora yazılır.
quality_review sözleşmesi bu alanları insan incelemesine bırakır; hiçbir
şema/renk testi otomasyon onayını kendiliğinden açmaz.

## Gerçek testin sonucu ve kota

İlk manuel çalışma [43095434289](https://github.com/akaradag88/minomasal-automation/actions/runs/43095434289)
Türkiye saatiyle 23:20:23–23:35:07 arasında bekledi ve **startup_failure** ile
bitti; hiçbir job oluşmadı. İptal denemesi kabul edilmedi; çalışma zaten bu
durumda tamamlanmıştı. Yeni zoom korumasını içeren ikinci çalışma
[43097046412](https://github.com/akaradag88/minomasal-automation/actions/runs/43097046412)
23:36:26–23:40:02 arasında yine **startup_failure**, `jobs=[]` ile bitti.
İkinci çalışma, çalışmamış eski kadraj kodunu tekrarlamak için değil, sonradan
bulunan renderer zoom korumasını test etmek için başlatıldı. Başka dispatch yok.

GitHub CLI olası workflow dosyası sorunu diyor; Check Runs/annotation listesi
boş, ayrıntılı neden yok. Resmî upstream sabit sürüm/checksum doğrulamalı
**actionlint 1.7.7** ile ilgili üç test workflow'u doğrulandı; statik hata
bulunmadı. Bu, GitHub'ın başlatma engelinin kesin nedenini belirlemez. Global
kesinti, kaynak sorunu, ücret veya belirli bir YAML satırı olduğu varsayılmadı.
Hiçbir runner job'u başlamadığı için Cloudflare hata kodu/üretim başarısızlığı
olarak da raporlanmıyor. Başlatma sorununun GitHub tarafındaki ayrıntısı
çözülmeden gereksiz tekrar yapılmadı.

**Bu adımda metadata/API isteği 0, yeni FLUX görseli 0, yeni Neuron tüketimi 0.**
Mevcut kalan kota yeniden doğrulanamadı; eski 9.654,40 değeri güncel bakiye gibi
sunulmaz. Ücretsiz plan/kota kapısı aynen korundu; yeterli ve doğrulanmış kota
olmadan herhangi bir üretime geçilmedi. İleride iki 1024² görselin dört
varsayılan adımla tahmini tüketimi ~115,2, günlük on görselinki ~576 Neuron'dur;
bu gerçekleşmiş tüketim değildir.
[Resmî fiyatlandırma](https://developers.cloudflare.com/workers-ai/platform/pricing/).

Runner başlamadığından **yeni Actions artifact oluşmadı**. Yeni profilün yüz,
nesne sayısı, yazı ve kamyon kimliğine etkisi gerçek modelde ölçülemedi;
iyileşmiş gibi raporlanmıyor. `approved_for_automation=[]` korundu.

## Çevrimdışı kadraj karşılaştırması ve testler

Eski iki orijinal yeni normalizer'dan geçirilip görsel olarak incelendi.
[İlk kadraj önizlemesi](docs/adim_10_9_16/framing-preview/scene-1.contain.jpg) ve
[ikinci kadraj önizlemesi](docs/adim_10_9_16/framing-preview/scene-2.contain.jpg)
**yeni FLUX örneği değildir**: karakter/nesne içeriği eski görüntülerle aynıdır.
Eski merkez kırpmada kaybolan kaynak yanları artık görünür; video zoom'u için
dış pay korunur. Eski yazı ve iki kamyon sorunu önizlemelerde hâlâ vardır;
yerel normalizer bunları silmez. Büyük mat alanlar tam ekran native portre
yerine seçilen güvenli kadraj ödünleşimidir.

Tam paket: **137 çevrimdışı test başarılı**. Yeni kalite/probe komutu:
`python -m unittest -v test_minomasal_cloudflare_quality_test test_minomasal_visual_profile`
— **29 test başarılı**. Bunlar yerelde çalıştı; bu adımda Actions'ta testlerin
çalıştığı iddia edilmez. Yeni testler zorunlu fiziksel özellikler, açık sayımlar,
bozuk tipler, uzun promptta durma, sabit kimlik bloğu/hash, API'den önce profil
reddi, isteğe bağlı üretim entegrasyonu, tam kaynak köşeleri ve %8 zoom güvenli
kadrajını kapsar. Yeni API bağımlılığı, OCR veya semantik model eklenmedi.

Yerel doğrulama, prompt uzunlukları, profil/inceleme sözleşmesi ve kota sınırları:
[local-validation-report.json](docs/adim_10_9_16/local-validation-report.json).
GitHub başlatma kanıtları aynı klasörde saklandı. Test komutu her iki manuel
CF workflow'una da eklendi; gerçek çağrıdan önce bu kalite testleri çalışmalıdır.

Günlük yayın saati, yayın workflow'u, yayın defteri, günlük kilit, çift yayın,
seslendirme, YouTube/Instagram kod ve ayarlarında bu adımda fark yok.
PR #4 taslak/açık; main'e birleştirilmedi, canlı workflow veya sosyal yayın yok.

Kalan engeller: GitHub startup_failure ayrıntısının giderilmesi ve iki yeni
örnekle gerçek profil etkisinin ölçülmesi. Sonrasında da yüz/nesne/yazı ve
anlatım uyumu insan incelemesi gerektirir; sıkı kimlik için önerilen onaylı
karakter/kamyon katmanı + ayrı arka plan yaklaşımı bu PR'da uygulanmış veya
test edilmiş gibi sunulmaz. Normal üretimin yapılandırılmış profilü otomatik
hazırlaması ve tam ekran kompozisyon tasarımı ayrıca tamamlanmalıdır.
