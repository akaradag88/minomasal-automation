# Sabit varlıklarla sahne hazırlama

Üretim kataloğu kasıtlı olarak boş. Bu PR'da gerçek, kullanıcı tarafından
onaylanmış masal karakteri yoktur. Testlerdeki geometrik proxy'ler yalnız
`test-fixture` kapsamındadır; üretimde ve yerel görsel devrinde reddedilir.
Eksik varlık/görünüş için sessiz model üretimi veya sağlayıcı fallback'i yok.

## Dosyalar ve onay kaydı

`profile-templates.json` yeniden kullanılabilir tilki/kamyon fiziksel özellik
şablonlarını içerir. Her profil `kind`, `traits` ve tek kanonik `reference`
görseliyle tanımlanır. `catalog.json` içindeki `profiles` sözlüğüne onaylı
kaynağınızın kaydını ekleyin. Kaynak dosya hash'i ve kimlik incelemesi gerekir.
Şablonlardaki boş yollar/onaylar çalışır üretim varlığı değildir.

`assets` sözlüğü her poz/görünüş için ayrı bir RGBA PNG kaydı tutar:

```json
{
  "profile": "fox",
  "view": "front",
  "path": "fox-front.png",
  "sha256": "DOSYANIN_SHA256_DEGERI",
  "reference_sha256": "KANONIK_REFERANS_SHA256",
  "profile_sha256": "FIZIKSEL_PROFIL_OZETI",
  "mirror_approved": false,
  "approval": {
    "status": "pending",
    "scope": "production",
    "reviewed_by": "",
    "reviewed_at": "",
    "reviewed_record_sha256": "",
    "checks": {"identity": false, "single_entity": false, "edges": false, "no_text_logo": false}
  }
}
```

`front`, `side`, `back` ayrı dosyalar ve ayrı incelemelerdir. Bir görünüş yoksa
front'a düşülmez veya yeni poz çizilmez. Yatay aynalama varsayılan kapalıdır;
asimetrik detaylar için uygunluğu ayrıca onaylanmalıdır. Boyut tek oranla
değişir; x/y bağımsız esnetilmez. `height` PNG tuvalinin piksel yüksekliği,
x/y sol üst koordinatıdır; saydam kenar payını da kapsar.

Varlık 32–4096 piksel kenarlı, en çok 16 milyon pikselli gerçek RGBA PNG
olmalı; görünür kısım dosya kenarından en az iki piksel içeride kalmalıdır.
Referans, PNG dosyası ve metadata hash'leri denetlenir. `digest(path)`,
`character_profile_fingerprint(profile)` ve `record_fingerprint(record)`
yardımcıları `minomasal_asset_compositor` modülündedir; sonuncusu `approval`
alanı dışındaki dosya/görünüş/profil metadata'sını bağlar. Yalnız hash üretmek
insan incelemesinin yerine geçmez. İnceleme sonrası doğru kayıt özeti,
inceleyen ve ISO tarih ile `approved` durumu kaydedilir; kod bunu kendi
kendine yapmaz. Fiziksel özellik veya görünüş metadata'sı değişince onay düşer.

`backgrounds` kayıtlarında dosya yolu/hash'i ve ayrıca `empty_scene` ile
`no_text_logo` incelemeleri gerekir. Arka planda görünür karakter/araç bulunması,
katman sayısı doğru olsa bile gerçek toplamı bozabilir. Gerçek model çıktısı
önce `pending` kalır; otomatik olarak boş/onaylı kabul edilmez.

## Sahne planı ve kompozisyon

```json
[
  {
    "background": "forest_1",
    "inventory": {"fox": 1, "truck": 1},
    "layers": [
      {"profile":"fox", "asset":"fox_front", "view":"front", "x":160, "y":950, "height":480, "flip_x":false},
      {"profile":"truck", "asset":"truck_front", "view":"front", "x":600, "y":1280, "height":180, "flip_x":false}
    ]
  }
]
```

```bash
python minomasal_asset_compositor.py compose --catalog visual_assets/catalog.json --scenes scenes.json --output reviewed-frames
```

Çıktı RGB JPEG 1080×1920'dir. Arka plan tuvali dolduracak biçimde yerleşir;
bu yüzden boş arka plan onayı önemlidir. Karakter/nesneler kesilmez, %5 dış
güvenli pay içinde kalır. Bu pay mevcut %8 maksimum video zoom'una uygundur.
Saydam RGB verisinin beyaz kenar yaratmaması için ölçekleme premultiplied alpha
ile yapılır. Üç kattan fazla büyütme, yanlış boyut ve %15'ten fazla örtülme
reddedilir. Tüm sahneler doğrulanmadan başarılı bir çıktı paketi açılmaz.
Mevcut çıktı/varlık dosyaları üzerine yazılmaz.

`--preview` yalnız inceleme için pending kayıtları kullanabilir; yapısal
bozukluk, kesilme veya şüpheli beyaz kenar kontrollerini atlamaz. Preview ve
test varlıkları üretim kabulü değildir. Kod ağ/model/yayın istemcisi içermez.

## Arka plan kaldırma ve OCR

```bash
python minomasal_asset_compositor.py remove-uniform-background --source known-key-source.png --output candidate.png --key-rgb 0,255,0
```

Bu yalnız bilinen düz renkli, sınırları en az %98 aynı olan fonlar içindir.
Sınıra bağlı renk alanı kaldırılır; içteki benzer renkli ayrık alanlar otomatik
silinmez. Orman/fotoğraf arka planı genel segmentasyon gibi işlenmez. Model
veya ağırlık indirilmez. Çıktı her zaman pending aday ve `.review.json` üretir;
kaybolan kürk/parça, maske, kenar ve kimlik insan incelemesi ister.

Bağlantısız önemli alfa parçaları ve yarı saydam beyaz kenarlar heuristikle
işaretlenir. Bunlar gerçek nesne algılama değildir; beyaz kürk gibi meşru bir
detay da işaretlenebilir. `white_fringe_reviewed` / `disconnected_parts_reviewed`
ek insan incelemeleri olmadan üretim varlığı kabul edilmez.

Yerel Tesseract varsa metin taranır. En az iki alfanümerik karakterli ve
OCR skoru en az 85 olan bulgular durdurur; 60–85 arası şüpheli kutular ayrıca
manuel inceleme ister. Bu skor doğruluk olasılığı değildir. Tanınan metin/ham
stderr yazdırılmaz; kutu ve skor raporlanır. Tesseract yoksa/hata verirse bu açıkça raporlanır,
başarılı metin kontrolü gibi sunulmaz. Test workflow'u gerçek motoru doğrulamak
için Tesseract/İngilizce OCR paketini sınırlı APT ile kurar; günlük workflow'a
bu bağımlılık eklenmedi. Logolar, küçük/stilize yazılar, opak beyaz halolar,
gerçek nesne kimliği, kamuflaj/zemine uyum, altyazı yerleşimi ve anlatımla uyum
insan incelemesi gerektirir. Şüpheli OCR kutusu bulunan kompozit, hash bağlı
nihai sahne onayı olmadan yerel üretim akışına devredilemez.

## Yerel görsel akışına devir

Kompozisyon manifest'i başlangıçta `manual_scene_review_required=true`,
`automation_quality_approved=false` taşır. Mevcut `make_images(..., local=...)`
yolu composition.json bulunan klasörde preview/test/onaysız varlıkları
reddeder. Üretim kapsamındaki varlıklar hazır olsa bile aşağıdaki sahne
incelemesi ve birebir dosya hash'leri olmadan devir durur:

```json
{
  "manual_scene_review": {
    "status": "pending",
    "scope": "production",
    "reviewed_by": "",
    "reviewed_at": "",
    "checks": {"identity":false, "counts":false, "text_logos":false, "scene_action":false},
    "reviewed_output_hashes": []
  }
}
```

Onay yalnız gerçek sahneler incelendikten sonra kaydedilmelidir. Normal yerel
görsel klasörlerinin eski davranışı korunur. Kompozitler günlük otomasyona
bağlanmadı; `approved_for_automation=[]` değişmedi. Bu araç YouTube/Instagram,
seslendirme, yayın defteri, günlük kilit veya canlı workflow çalıştırmaz.
