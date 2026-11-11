# Adım 10.9.17 — test altyapısı ve sabit varlık kompozisyonu

Başlangıç commit'i **4dc2966**, mevcut taslak PR #4. Bu adımda günlük yayın
workflow'u tetiklenmedi; sosyal medya yüklemesi, ödeme, plan yükseltmesi veya
main birleştirmesi yapılmadı. Üretim otomasyon onayı kapalıdır.

## 1. startup_failure ve yapılan düzeltme

Önceki iki çalışma 43095434289 ve 43097046412 `startup_failure`, `jobs=[]`
ile tamamlanmıştı. API cevabı, koşullu olarak kullanılmasa bile referans
verilen `minomasal-dependencies-test.yml` reusable workflow'unu gösteriyordu.
Dispatch kabul edilmiş, doğru PR ref/commit seçilmiş; henüz runner işi,
paket kurulumu veya Cloudflare çağrısı oluşmamıştı. Check-run açıklamaları
boştu. YAML/actionlint kontrolü hem önce hem sonra temizdi.

Depo Actions politika/izin ayarını okuma isteği entegrasyon yetkisi nedeniyle
HTTP403 döndürdü; bu **Cloudflare token hatası değildir**. Yeni geniş yetki
istenmedi. Runner Ubuntu24, Python3.11 ve sabit Node24 action sürümleri korundu.
İzin, runner kapasitesi veya GitHub altyapısını kesin neden olarak kanıtlayan
ek veri yok. **Tarihsel kök neden tek bir ayara kesin bağlanamadı.**

Çalışan test yolu için:

- Kayıtlı manuel test köprüsünden reusable workflow çağrısı kaldırıldı;
  bağımlılık testi aynı adımlarla doğrudan job oldu. Kullanılmayan callee'nin
  başlangıçta çözülmesi artık bu akışın bağımlılığı değil.
- Testler mode/ref temelli concurrency ile ayrıldı. Günlük workflow'un
  concurrency'si, cron'u ve yayın kilidi değiştirilmedi.
- Ayrı `minomasal-assets-test.yml` yalnız manuel çalışır. Main'de henüz
  kayıtlı olmadığı için PR ref'indeki kayıtlı test dosyasının `asset_test`
  seçeneği **aynı doğrudan adımları** çalıştırır; workflow_call yapılmaz.
- Pollinations, eski CF karakter-prompt testi ve dependency job'ları asset
  modunda atlanır. Varsayılan görsel üretim girdisi false'tur. Secrets yalnız
  açıkça seçilmiş iki arka plan adımında bulunur; önce tam offline paket çalışır.

Bu sadeleşmeyle dört ayrı sürümde gerçek runner testi başarılı oldu; aynı
başlatma hatasında sınırsız tekrar yapılmadı. Reusable çözümlemesi/concurrency
değişikliği çalışan bir **düzeltme yolu** sağladı; tarihsel hatanın tek nedenini
kanıtlamak için kontrolsüz eski workflow tekrarları yapılmadı.

## 2. Gerçek runner doğrulaması

| Çalışma | Kod / içerik | Sonuç |
|---|---|---|
| [43099587171](https://github.com/akaradag88/minomasal-automation/actions/runs/43099587171) | 32aa5b7, Secret almayan doğrudan smoke, 29 odaklı test | success |
| [43101448456](https://github.com/akaradag88/minomasal-automation/actions/runs/43101448456) | 6530d12, 165 tam offline test + iki ücretsiz arka plan + proxy kompozisyonu | success |
| [43101897788](https://github.com/akaradag88/minomasal-automation/actions/runs/43101897788) | 80bbc63, güçlendirilmiş profil/görünüş onayı, 166 test; API kapalı | success |
| [43103986524](https://github.com/akaradag88/minomasal-automation/actions/runs/43103986524) | 88790fe, gerçek OCR motoru dahil **168 test**; API kapalı | success |

Son çalışma 168 testi 5,398 saniyede çalıştırdı. Gerçek Tesseract testinin
atlanmadan `ok` döndüğü logdan doğrulandı. Son çalışmalarda
`referenced_workflows=[]`. Çalışmalar farklı kod doğrulamalarına aittir;
165+166+168 ayrı benzersiz test sayısı gibi toplanmamalıdır.

[İki arka planlı artifact](https://github.com/akaradag88/minomasal-automation/actions/runs/43101448456/artifacts/13890898551)
orijinalleri, RGBA test varlıklarını, iki sahneyi ve kalite/kota raporlarını içerir.
[Son OCR/168-test artifact'ı](https://github.com/akaradag88/minomasal-automation/actions/runs/43103986524/artifacts/13893476323)
son kodun yalnız offline arka planlarla doğrulamasıdır; **ek API çağrısı yoktur**.
Artifacts 14 gün saklanır; kalıcı kopyalar ve durum kanıtları
[docs/adim_10_9_17](docs/adim_10_9_17) altındadır.

## 3. Sabit karakter sistemi

`minomasal_asset_compositor.py` yalnız yerel dosyalarla çalışır; görüntü
üretimi/yayın istemcisi içermez. Onaylı gerçek referans dosyası, fiziksel
özellik profili ve her görünüşün ayrı RGBA PNG'si katalogda tutulur.
`visual_assets/profile-templates.json` tilki ve oyuncak kamyon için yeniden
kullanılabilir özellik şablonlarıdır. Gerçek üretim kataloğu bilerek boştur:
**Henüz kullanıcı onaylı gerçek masal varlığı sağlanmadı.** Eksik varlık,
referans veya poz için karakter sessizce yeniden üretilmez.

Onay; dosya hash'i, kanonik referans hash'i, fiziksel profil özeti ve
görünüş/ayna metadata'sına bağlanır. Dosya veya tanım değişirse onay geçersiz
olur. Front/side/back ayrı onaylı varlıklar olarak seçilir; eksik görünüşte
front'a düşme veya yeni poz uydurma yoktur. Ayna ancak açıkça onaylanmışsa
kullanılır. x/y konumu, orantılı PNG yüksekliği ve görünüş sahnede açıktır.

Tuval 1080×1920, karakter güvenli bölgesi [54,96,1026,1824]'tür. Bu %5 dış pay
mevcut %8 maksimum zoom'u karşılar; video efektleri değiştirilmedi. Arka plan
tek başına tuvali dolduracak biçimde ölçeklenebilir, foreground kesilmez.
Premultiplied alpha ile resampling, saydam piksellerin gizli beyaz RGB'sinin
kenara sızmasını engeller. Bağımsız x/y esnetme ve üç kattan büyük büyütme yok.

Yalnız bilinen düz renkli fonlar için sınır-bağlantılı chroma-key kaldırma
aracı da eklendi. Sonuç **daima pending adaydır**. Orman gibi karmaşık bir fon
genel segmentasyon varmış gibi silinmez; model/ağırlık indirilmez. Kürk/parça
kaybı ve maske kalitesi insan incelemesi gerektirir. Ayrıntılı şema ve
komutlar: [visual_assets/README.md](visual_assets/README.md).

## 4. Aynı karakter iki sahnede korunuyor mu?

**Mekanik varlık yeniden kullanımı doğrulandı; gerçek masal karakteri onaylanmadı.**
Demo kaynakları açıkça `test-fixture` kapsamındaki geometrik turuncu/yeşil gözlü
karakter ve kırmızı araç proxy'leridir. Bunlar gerçek tilki illüstrasyonu veya
üretim onaylı varlıklar olarak sunulmaz. Her iki sahnede aynı referans, aynı
PNG ve aynı dönüştürülmüş RGBA hash'i kullanıldı; sadece konum/arka plan değişti.
İki varlığın görünürlük oranı 1,0; katman sayısı 1 karakter + 1 araçtır.

Son kodla, **aynı iki önceden üretilmiş arka plan** yerelde tekrar kullanılarak
[birinci](docs/adim_10_9_17/final-code-preview/01.jpg) ve
[ikinci](docs/adim_10_9_17/final-code-preview/02.jpg) önizleme de oluşturuldu.
Bu yeniden birleştirme yeni model isteği değildir. Test proxy'leri iki sahnede
aynıdır; fakat gölge/zemin teması, hikâye pozu ve gerçek illüstrasyon kalitesi
üretim kabulü değildir. Gerçek karakterle nihai kimlik doğrulaması için onaylı
referans ve şeffaf PNG'ler hâlâ gerekir.

## 5. Kalite kontrolleri ve manuel sınır

Otomatik yakalanan durumlar:

- Eksik/onaysız/test-scope varlığın üretimde kullanımı; eski dosya/profil/
  görünüş onayı, kaynak hash uyuşmazlığı ve katalog dışı dosya/URL.
- Bozuk görsel, yanlış format/boyut, RGBA/transparan fon yokluğu, tamamen
  görünmez alfa, dosya sınırına dayanan/kesilmiş sprite.
- Planlanan sayıyla katman sayısının uyuşmaması, bilinmeyen rol, eksik poz,
  onaysız aynalama, geçersiz ölçek/koordinat ve zoom güvenli bölge dışına çıkma.
- Sonraki katmanların önceki karakter/nesneyi %15'ten fazla örtmesi.
- Bağlantısız önemli alfa parçaları ve bazı yarı saydam beyaz kenar şüpheleri.
- Yerel OCR'da skor >=85, en az iki alfanümerik karakterli metin bulgusu.

İlk generatif runner'da Tesseract yoktu; rapor **unavailable** dedi, otomatik
metin kontrolü başarılıymış gibi gösterilmedi. Bu eksikliği kapatmak için son
test workflow'una sınırlı APT ile Tesseract/İngilizce OCR kuruldu ve gerçek
metin örneğiyle test edildi. Günlük workflow'a bağımlılık eklenmedi.

Yerel yeniden birleştirmede yaprak dokuları 61,7–67,4 skorlarında şüpheli
kutular verdi. İlk sert 60 eşiği bu önizlemeyi durdurmuştu; kayıt
`local-ocr-diagnostic.json` dosyasında korundu. Son tasarımda 60<=skor<85
kutuları **manuel inceleme gerektirir**, >=85 üretimi durdurur. Skor bir
doğruluk olasılığı değildir; eşik değişimi otomatik onay vermek için kullanılmaz.
İki gerçek arka planlı son önizlemede de manuel OCR incelemesi açık kaldı.

Gerçek varlık/arka plan onaylı olsa bile kompozitlerin mevcut yerel görüntü
yoluna devri için **nihai görüntü hash'lerine bağlı insan sahne onayı** gerekir.
Preview/test-scope/onaysız çıktılar `make_images(..., local=...)` içinde
reddedilir. Bu yeni koruma normal eski yerel görsel klasörlerini değiştirmez.

Sistem gerçek bir nesne/kimlik veya grafik logo dedektörü değildir. Katman
sayısı doğrulaması, tek varlık ve boş arka planın insan tarafından doğrulandığı
varsayımına dayanır; bir PNG içindeki ek karakteri kesin saymaz. Stilize/küçük
yazı, logo, opak halo, kürk kaybı, kamuflaj, perspektif, altyazı yerleşimi ve
anlatımla uyum manuel inceleme ister. Tesseract yoksa/hata verirse de manuel
inceleme zorunludur. `automation_quality_approved` hiçbir testle kendiliğinden
true olmaz; `approved_for_automation=[]` değişmedi.

## 6. Ücretsiz kota ve tüketim

Kullanıcının izin verdiği **tam iki yeni model isteği yalnız arka plan** içindi;
gerçek karakter modelde üretilmedi. Model `@cf/black-forest-labs/flux-1-schnell`,
minimum gövde yalnız prompt; desteklenmeyen referans/img2img alanları eklenmedi.
Önce ücretsiz abonelik ve kullanım doğrulandı, her görüntü öncesi aynı UTC gün
ve en az 1000 Neuron rezervi tekrar kontrol edildi. İlk görsel dosyası
doğrulanmadan ikinciye geçilmedi; inference tekrar denemesi yoktu.

Test öncesi raporlanan hesap-geneli kullanım **691,20**, kalan **9308,80 /
10.000 Neuron**; ücretli abonelik yok (`unbilled_account`). Analytics gecikebilir,
bu kesin anlık son bakiye değildir. Kota günü API'de UTC'dir; sıfırlama Türkiye
saatiyle 03:00'tır. Kaynaklar 1024², süreler 2,14 / 1,71 saniye.

1024² ve dört belgelenen varsayılan adım hesabıyla **~57,6 Neuron/görsel,
~115,2 Neuron bu test** tahmini. Son bakiye/delta ölçülmediği için gerçekleşmiş
muhasebe değeri diye sunulmaz. Metadata, yerel kompozisyon, OCR ve son üç
API-kapalı doğrulama yeni görsel Neuron'u tüketmez. Günlük on yeni arka plan
yaklaşık 576 Neuron kapasitesi ister; onaylı karakter/nesnelerin tekrar
yerleştirilmesi ilave görüntü API çağrısı gerektirmez.
[Resmî fiyatlandırma](https://developers.cloudflare.com/workers-ai/platform/pricing/).

## 7. Test sonucu

**168 test yerelde ve son gerçek GitHub runner'da başarılı.** Son gerçek
Tesseract testi atlanmadı. Yeni kapsama: onay/ref/profil hash'leri, görünüş/
ayna, alfa/kenar/halolar, katman/örtülme/safe-frame, chroma-key sınırları,
OCR metin ve belirsizlik, preview/test çıktısının üretim devrine reddi,
nihai sahne onay hash'leri ve ağsız demo. Eski HTTP402/429/500, yayın, sıra ve
günlük kilit regresyonları aynı pakette korundu.

Actionlint 1.7.7 ilgili dört workflow'da, `git diff --check` ve korunan dosyalar
için byte karşılaştırması başarılı. Kanıtlar `test-results.txt`,
`final-168-runner-evidence.json`, `protected-settings-check.json` dosyalarında.
Yalnız doküman/örnek şablonlar son CI kodunun üzerine eklenmiştir.

## 8. PR #4 ve canlı öncesi engeller

PR açık/taslak, main'e birleştirilmedi. Günlük workflow, yayın saati,
YouTube/Instagram, seslendirme, yayın defteri/günlük kilit/çift yayın koruması
başlangıç 4dc2966 ile aynı; doğrulama JSON'unda dokuz korunan dosya listelenir.

Canlı öncesi gerekenler: kullanıcı onaylı gerçek referans/şeffaf varlıklar ve
gereken pozlar; gerçek hikâye arka planı/son sahne incelemesi; OCR şüphelerinin
kararı ve anlatı/zemin/gölge/altyazı uyumu; onaylı kompozisyonların günlük
üretim planına kontrollü bağlanması. Bu adım kod ve test altyapısını kurar;
geometrik proxy'leri gerçek karakter diye onaylamaz, otomatik yayını açmaz.
