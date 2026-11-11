# Adım 10.9.13 — ilk iki başarılı Cloudflare FLUX görseli

11 Kasım 2026, mevcut taslak PR #4. Main'e birleştirme, canlı workflow,
YouTube/Instagram yayını, ödeme veya plan yükseltmesi yapılmadı.

## HTTP400 hakkında kesin bilinenler

Önceki [43059736058](https://github.com/akaradag88/minomasal-automation/actions/runs/43059736058)
çalışmasındaki HTTP400 gövdesi/kodu önceki kod tarafından saklanmadı; artifact
yalnız `request_failed`, HTTP400 ve endpoint şablonu içeriyor. Bu yüzden o
yanıtın API hata kodu veya mesajı geriye dönük çıkarılamıyor. Bilinmeyen bir
mesaj varmış gibi yazılmadı; tek bir parametrenin kesin kök neden olduğu
iddia edilmiyor. Önceki gönderim prompt:string, steps:4 ve seed:1234 idi;
width/height zaten gönderilmiyordu.

[Güncel model belgesi](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/)
parametre şemasında zorunlu prompt (1–2048 karakter) ve opsiyonel integer steps
(varsayılan 4, en fazla 8) tanımlar. Seed örnek kodda görünse de parametre
listesinde yoktur; destek konusunda belge tutarsızlığı vardır. Width/height
bu şemada bulunmaz. Bu kanıt seed'in tek başına HTTP400'e yol açtığını kanıtlamaz.

En küçük şemaya uygun istek uygulandı:

```json
{"prompt": "ortak karakter tanımı ve sahne açıklaması"}
```

`requests` JSON serileştirmesi `Content-Type: application/json` gönderir.
Opsiyonel steps ve belirsiz seed gönderilmez; width/height eklenmez.
Cloudflare artık deterministik seed desteği varmış gibi manifest'e yazmaz.
Eski config alanı cloudflare_steps uyumluluk için okunur, minimum istekte
gönderilmez; kota rezervi gerçek model varsayılanı olan 4 adımla hesaplanır.
Bu değişiklikle aynı hesap/modelde iki gerçek istek de **başarılı** oldu.
İlk 400'ü tek parametreye ayırmak için ek inference/A-B isteği yapılmadı.

Yeni hata teşhisi API'nin sayısal hata kodunu ve yerel sabitlerden güvenli
açıklamayı kaydeder (ör. 10000 → Authentication error). Mesaj **kanonik
açıklamadır**, ham yanıt alıntısı değildir. Bilinmeyen mesajlar gizlenir;
yalnız sabit prompt/steps/seed/width/height alanlarından hangisinin anıldığı
raporlanabilir. Secret parçası, Authorization, hesap ID'si, prompt/URL veya
ham upstream metni rapora alınmaz. HTTP400 tekrar denenmez.
Yeni çalışmada hata olmadığı için raporlanabilecek yeni bir API hata kodu yoktur.

## Gerçek test ve ücretsiz kota

[Başarılı çalışma 43066478666](https://github.com/akaradag88/minomasal-automation/actions/runs/43066478666)
yalnız PR dalında manuel CF-only test olarak çalıştırıldı; Pollinations job'u atlandı.
Token ayrımı, model erişimi, denetim tokenıyla abonelik ve Analytics kontrolleri
geçti. Abonelik listesi boş (`unbilled_account`), raporlanan kullanım 0,
günlük tahsis/kalan 10.000 Neuron. Analytics gecikmeli olabilir; bu anlık
kesin bakiye değildir. Her görsel öncesi aynı UTC gün ve en az 1.000 Neuron
rezervi tekrar kontrol edildi. Ücretli veya bilinmeyen plan reddi korunur.

**Tam iki inference isteği, tam iki başarılı görsel**; yeniden üretim yok.
İlk görselin dosya/boyut doğrulaması ve dikey dönüşümü başarılı olduktan sonra
ikinci istek gönderildi. Her iki kaynak 1024×1024, çıktı 1080×1920 JPEG.
Ölçülen istek+dönüşüm süreleri 2,09 ve 2,12 saniye. Gerçek video/ses üretilmedi.

[Artifact: cloudflare-flux-test-43066478666](https://github.com/akaradag88/minomasal-automation/actions/runs/43066478666/artifacts/13875617861)
iki orijinali, iki dikey çıktıyı ve güvenli raporu içerir (14 gün).
Kalıcı kopyalar ve manuel değerlendirme:
[docs/adim_10_9_13/cloudflare](docs/adim_10_9_13/cloudflare).
İndirilen orijinallerin SHA256 değerleri Actions raporuyla doğrulandı.

| Kontrol | Sonuç |
|---|---|
| Turuncu kürk, beyaz ağız çevresi, yeşil göz | İki görselde de mevcut |
| Mavi atkı rengi | Korundu |
| Atkı tasarımı | İlkinde düz, ikincide desenli; aynı tasarım korunmadı |
| Yüz kimliği/stil | Genel benzerlik var; yüz oranları, yanak ve çizim stili değişiyor |
| Kamyon | İkisi de kırmızı damperli; kabin/ızgara/kasa/jant ve oranları değişiyor |
| Ek karakter | İki orijinalde de görülmedi; tek tilki var |
| Dikey kompozisyon | Mevcut merkez kırpma kamyonu ve kulak kenarlarını kesiyor |

Sonuç: API bağlantısı ve ilk iki üretim başarılı; otomatik seri masalda
karakter/nesne kimliği ve dikey kadraj henüz yeterli değil. Bu yüzden
`approved_for_automation=[]` korundu. Yeni görsel üretimi yapılmadan incelendi;
dosya doğrulamasının semantik kalite onayı olmadığı açıkça ayrıldı.

[Resmî fiyatlandırma](https://developers.cloudflare.com/workers-ai/platform/pricing/):
1024×1024 = dört 512×512 karo; 4×4,8 + 4×9,6 = **57,6 Neuron/görsel**.
İki görsel yaklaşık 115,2, on görsel yaklaşık 576 Neuron. Aynı anda başka
tüketim yoksa teorik kalan 9.884,8; bu gerçek son bakiye ölçümü değildir.
Free planda 10.000/gün kapasite günlük on görsele yeterlidir, ancak kalite
yeniden üretimleri ve hesapta başka işler toplamı etkiler. Ücretsiz kota
ertesi UTC gününde sıfırlanır; ücretli aşım/otomatik yükseltme kullanılmadı.

## Test ve PR durumu

` .venv-readiness/bin/python run_readiness_tests.py`: **112 test başarılı**.
Gerçek Actions çalışmasında ayrıca **17 odaklı çevrimdışı test başarılı**.
Yeni testler prompt-only gövdeyi, prompt tür/uzunluğunu, HTTP400'ün tek istekle
durmasını, hata raporunun Secret parçası sızdırmamasını, ilk hata sonrası ikinci
sahnenin başlamamasını ve varsayılan adımla kota rezervini kapsar.

Bu adımda yalnız görsel sağlayıcı/test/teşhis ve raporlar değişti; defter, günlük
kilit, seslendirme, video render, YouTube/Instagram ve yayın workflow'ları korunur.
PR taslak/açık, main'e birleştirilmedi. Entegrasyon teknik incelemeye hazırdır;
canlı otomasyon onayı için tutarlı karakter/kamyon ve güvenli dikey kadraj
çözülmeli. Eski 400'ün kesin upstream mesajı tarihsel veri yokluğu nedeniyle
belirlenememiştir; minimum istekle üretim engeli fiilen giderilmiştir.
