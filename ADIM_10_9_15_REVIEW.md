# Adım 10.9.15 — gerçek runner ve yeniden FLUX doğrulaması

11 Kasım 2026, PR #4, başlangıç commit'i d3a9653. Main'e birleştirme,
günlük yayın workflow'u, sosyal medya yayını, ödeme veya ücretli API yok.

## HTTP400 incelemesi

Önceki başarısız çalışmanın raporu yalnız HTTP400 / request_failed saklıyor;
orijinal API hata kodu ve ham mesaj saklanmamış. Tam kod/mesaj geri alınamadı.
Bu nedenle 400'ün kesin olarak seed kaynaklı olduğu söylenemez. Testlerdeki
10000/Authentication error örneği bir **sahte test verisidir**, gerçek hesaptan
alınmış hata değildir. Eski gövdeyi yeniden göndererek fazladan inference
yapılmadı; hata üretmek için eski kusurlu istek geri getirilmedi.

[Güncel resmî model belgesi](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/)
yeniden kontrol edildi: prompt:string zorunlu, uzunluk 1–2048; steps:int
opsiyonel, varsayılan 4, üst sınır 8. Seed örneklerde var fakat parametre
listesinde yok; width/height tanımlı değil. Mevcut düzeltme korunur:
`{"prompt":"ortak karakter tanımı ve sahne"}`; steps/seed/width/height yok.
HTTP400 tekrar edilmez. Yeni bir hata olursa sayısal API kodu ve sabit
kanonik açıklama kaydedilir; bilinmeyen ham mesaj, Authorization, Secret veya
hesap ID'si dökülmez. Bu adımda Cloudflare sağlayıcı kodunu tekrar değiştirmek
gerekmedi; iki yeni inference isteği de başarılı oldu, yeni HTTP400/kodu yok.

## Bağımsız gerçek runner testi

Yeni `.github/workflows/minomasal-dependencies-test.yml` yalnız manuel veya
manuel PR çağrısından reusable çalışır; schedule/push/pull_request tetikleyicisi
yok. Yetki contents:read, checkout kimlik bilgileri saklanmaz, API Secret almaz.
Üretim, model yükleme, ses/video oluşturma veya yayın kodu çağırmaz.

Yeni workflow main'de henüz kayıtlı olmadığı için mevcut kayıtlı manuel test
workflow'unun yalnız PR ref'indeki `dependency_test=true` seçeneği bu ayrı
workflow'u çağırır. Bu seçimde Pollinations ve Cloudflare job'ları atlanır.
Günlük yayın workflow'una veya main'e kayıt eklenmedi.

[Başarılı dependency çalışması 43081108461](https://github.com/akaradag88/minomasal-automation/actions/runs/43081108461)
Ubuntu 24.04 / Python 3.11.18 üzerinde çalıştı; **cache_hit=false**.
Ölçüm script'i üretimdeki installer'ı kullanır. Yalnız testte `system-force`
moduyla mevcut araçlara rağmen APT update/install yolu gerçekten çalıştırıldı;
günlük workflow'un araç varsa APT atlama davranışı değişmedi.

| Aşama | Gerçek süre | Sonuç |
|---|---:|---|
| APT update + FFmpeg/font install yolu | 29,009 sn | exit 0 |
| Python/pip kurulumu, sürüm komutları ve pip check | 17,112 sn | exit 0 |
| Import / ffprobe / ASS / font kontrolü | 1,869 sn | exit 0 |
| Ölçülen üç aşamanın toplamı | 47,990 sn | başarılı |

**Pip 480 saniyelik sınırın altında gerçek runner'da doğrulandı.** 17,112 sn
yalnız pip install ölçümü değil, onu da içeren tüm Python aşamasıdır; bu,
pip install için güvenli bir üst sınırdır. Gerçek tüketim/süre ile tahmin
karıştırılmadı. İlk sistem/Python hatasında benchmark durur, tekrar denemez;
günlük installer'ın içindeki sınırlı bağlantı tekrarları korunur.

Ölçülen sürümler: pip 26.2.2, edge-tts 7.3.1, Pillow 12.3.0, requests 2.34.2,
numpy 2.4.6, google-genai 2.34.0, google-api-python-client 2.202.0,
google-auth 2.62.2, google-auth-httplib2 0.4.4, faster-whisper 1.2.1.
Import doğrulaması ve aynı tam çevrimdışı test paketi gerçek runner'da geçti.
Bu, #48'in eski takılma nedenini kanıtlamaz; #48'in boş log arşivi sınırı sürer.

[Süre artifact'ı](https://github.com/akaradag88/minomasal-automation/actions/runs/43081108461/artifacts/13884676980)
ve kalıcı [dependency-report.json](docs/adim_10_9_15/dependency-report.json).
Job/test adım kanıtı: [runner-evidence.json](docs/adim_10_9_15/runner-evidence.json).

## Ücretsiz FLUX ve kalite sonucu

[Başarılı CF çalışması 43081212802](https://github.com/akaradag88/minomasal-automation/actions/runs/43081212802).
Tokenlar farklı, model erişimi ve denetim tokenıyla abonelik/Analytics sorguları
başarılı. Ücretli abonelik yok (`unbilled_account`). Test başında raporlanan
kullanım **345,600006 Neuron**, kalan **9.654,399994 / 10.000**. Bu gecikmeli
Analytics tahminidir; gerçek zamanlı kesin bakiye değildir. Her görsel öncesi
aynı UTC gün ve en az 1.000 Neuron rezervi tekrar kontrol edildi.

Tam **iki yeni istek, iki yeni görsel**; ilk dosya doğrulandıktan sonra ikinci
istek yapıldı. İstekler tek denemelik; ek/ücretli üretim veya başka sağlayıcıya
geçiş yok. Orijinaller 1024×1024, dikey çıktılar 1080×1920. Süreler 2,00 ve
1,79 saniye. Dört varsayılan adım varsayımıyla yaklaşık 57,6 Neuron/görsel;
bu test yaklaşık 115,2, günlük on görsel yaklaşık 576 Neuron kapasite ister.
Test sonrası kesin bakiye ölçülmüş gibi sunulmuyor.

İki orijinal ve iki dikey çıktı görsel olarak incelendi:

- Her ikisinde turuncu kürk, yeşil göz, mavi atkı; tek tilki, ek karakter yok.
- Yüz oranları, atkı biçimi ve kamyon tasarımı aynı kalmıyor.
- **İkinci sahnede iki kamyon var**; ilkindeki kamyonda istenmeyen Mino yazısı var.
- İkinci kamyonların rengi daha turuncuya kayıyor. Dikey merkez kırpma kamyon
  kenarlarını ve bazı karakter kenarlarını kesiyor.

Bu nedenle otomatik yayın kalite onayı verilmedi; `approved_for_automation=[]`
korundu. Dosya bütünlüğü başarısı semantik karakter/nesne tutarlılığı garantisi
değildir. Yeni görsel istemeden bu iki örnek üzerinden değerlendirme yapıldı.

[Görsel artifact'ı](https://github.com/akaradag88/minomasal-automation/actions/runs/43081212802/artifacts/13885150991)
iki orijinal, iki dikey dosya ve güvenli rapor içerir (14 gün saklanır).
Kalıcı kopyalar, SHA256 ile doğrulanmış orijinaller ve manuel inceleme:
[docs/adim_10_9_15/cloudflare](docs/adim_10_9_15/cloudflare).

## Testler, güvenlik ve kalan engeller

- Yerelde **123 çevrimdışı test başarılı**.
- Aynı 123 testlik tam paket gerçek dependency runner'da başarılı; ayrıca CF
  runner'da **17 odaklı çevrimdışı test başarılı**. İki workflow da success.
- Beş yeni test benchmark süre/başarı kaydını, APT hatasında durmayı, 480 sn
  bütçe aşımını, PR-manuel bağlam kapısını ve Secret/yayın almayan workflow'u kapsar.
- Shell sözdizimi ve diff boşluk kontrolleri başarılı. Eski testler, yayın
  defteri, günlük kilit, çift yayın, ses ve medya korumaları korunur.
- Başlangıç commit'i d3a9653 ile karşılaştırıldığında günlük yayın workflow'u,
  Cloudflare sağlayıcı/probe, defter, günlük kilit ve yayıncı kodlarında fark yok.
- PR #4 açık ve taslak, main'e birleştirilmedi. Hiçbir sosyal yayın yapılmadı.

Kurulum hızı ve API üretimi gerçek ortamda doğrulandı. Canlı otomasyonun kalan
engeli karakter/kamyon kimliği, fazladan nesne/yazı ve dikey kadraj kalitesidir.
Eski HTTP400'ün tam upstream mesajı tarihsel kayıt eksikliği nedeniyle bilinmiyor;
bugünkü minimum istekle hata yeniden oluşmadı. Bu belirsizliği gidermek için
gereksiz ek veya hatalı API çağrısı yapılmadı.
