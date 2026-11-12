# Yayını yeniden açmak için iş sırası

12 Kasım kurtarma devamı. Yayın kapalıdır; bu belge onay yerine geçmez.

| Sıra | İş | Tamamlanan | Kalan / kim yapabilir? |
|---|---|---|---|
| 1 | Defter ve tekrar yayın kontrolü | #45/#46 ve 10 Kasım skipped korundu; aday #47; Instagram okuma başarılı | YouTube hesabı sahibi mevcut yükleme iznine `youtube.readonly` ekler. Sonrasında asistan yeniden salt okunur doğrular. |
| 2 | Doğru hikâye ve profil | Mevcut 89 kelimelik / 10 sahnelik Tonton hikâyesi ve süreklilik planı bulundu; tilki taslağı geri çekildi | Metin hazırdır; final sahnelerle anlatım uyumu henüz doğrulanamaz. Yeni hikâye API çağrısı gerekmez. |
| 3 | Ücretsiz ve tutarlı görseller | Cloudflare ücretsiz hesap ve model erişimi doğrulanmış; onaysız üretim/yayın kapalı; gerçek referans incelendi | Mevcut 3B Tonton'u koruyan tam, temiz maskeli varlıklar/pozlar gerekiyor. Kaynak sağ/alt kenarda kesik ve opak. Schnell referans düzenlemeyi desteklemiyor. Eksik parçalar otomatik tamamlanmış kabul edilmez. Yeni tasarım ancak ayrıca görsel incelemeye sunulabilir. |
| 4 | Sesin ücretsiz kullanım koşulu | Mevcut Sami model/ayarları korundu; model kataloğu erişimi başarılı | Hesap sahibi ilgili Google AI Studio projesinde modelin ücretsiz kullanım/kota durumunu doğrular. API anahtarı, model listesi veya Cloudflare bakiyesi bunu kanıtlamaz. Ücretli projede deneme yapılmaz. |
| 5 | Ses, sahne ve MP4 üretimi | Doğru anlatım dosyası ve sahne durumları paketlendi | 1–4 tamamlanınca asistan üretir; ses kelime hizalama, süreler, 9:16, tam decode, eksik kare/görsel ve dosya kontrollerini yürütür. Görsel kalite insan incelemesi ister. |
| 6 | Belirli videoya yayın onayı | Defter rezervasyonu/yayın işaretleme yapılmadı; manuel onay korunuyor | Hazır MP4 ve rapor sunulduktan sonra kullanıcı onay verir. Önceden genel yayın izniyle yeni video yüklenmez. |
| 7 | Platform yayını ve ertesi gün | Cron 19:07 TR, concurrency ve günlük kilit korunuyor; otomatik üretim/yayın beklemede | Asistan onaylanan aynı dosyayı yayımlar, platform sonuçlarını ayrı kaydeder; başarılı platformu tekrar yüklemez. Günlük otomatik yayın için ayrıca açık onay ve sürdürülebilir kalite yolu gerekir. |

## Hazırlanan dosyalar

- `minomasal_recovery_package.py`: mevcut hikâye, plan, referans, anlatım ve eksik kontrolleri **ağsız** bir inceleme paketine kopyalar. Kaynaklar/defter özetlerle bağlanır. #47 sıradaki aday değilse durur; dosya üzerine yazmaz. Paket MP4, üretim makbuzu veya rezervasyon değildir.
- `docs/recovery/story-47-draft.json`: mevcut Tonton kaynağına bağlı taslak; yeni tilki masalı değildir.
- `docs/recovery/story-47-fox-withdrawn.json`: önceki yanlış taslak silinmeden geri çekildi.
- Günlük workflow ücretli servisi çağırmadan bu inceleme paketini artifact'e koyabilir. Üretim/yayın adımları kapalı kalır; günlük workflow manuel tetiklenmedi.
- `scripts/minomasal_youtube_reauthorize.py`: laptopta mevcut Google OAuth istemcisiyle izin ekleme yardımcısı. OAuth state + PKCE kullanır; yalnız localhost dinler; refresh tokenı yazdırmadan özel, üzerine yazılmayan dosyaya kaydeder. Kanal okumasını doğrulamadan sonuç kaydetmez. YouTube veya Instagram'a yükleme yapmaz.

## Laptopta YouTube iznini tamamlama

1. Mevcut YouTube bağlantısının **aynı Google OAuth istemcisine** ait istemci JSON'unu Google Cloud Console'dan kendi laptopunuza indirin. Yeni istemci oluşturup mevcut GitHub istemci değerleriyle karıştırmayın. Bu dosyayı veya içeriğini sohbete, repoya veya artifact'e yüklemeyin.
2. Web türü istemcide yetkili yönlendirme adreslerine `http://127.0.0.1:8765/` eklenmesi gerekebilir. Desktop türü istemci loopback akışını destekler. Consent ekranında mevcut kanalın sahibi hesabı seçin.
3. Repo güncelken laptopta çalıştırın (Python 3.10+; ek paket gerekmez):

```bash
python scripts/minomasal_youtube_reauthorize.py --client-file /yerel/yol/client_secret.json
```

4. Tarayıcıda hem yükleme hem salt okunur YouTube iznini verin. Yardımcı kanal okuması başarılı olursa `youtube-refresh-token.private` oluşturur; tokenı terminale yazdırmaz. Dosya içeriğini **yalnız** GitHub repo → Settings → Secrets and variables → Actions → `YOUTUBE_REFRESH_TOKEN` alanında güncelleyin. `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` aynı istemciye ait kalmalıdır. Dosyayı paylaşmayın/commitlemeyin; güncellemeden sonra yerel özel dosyaları işletim sisteminizin güvenli silme yöntemiyle kaldırın.
5. Bana yalnız **“YouTube okuma izni eklendi”** deyin. Anahtar, token, kod, URL veya özet göndermeyin. Sonraki API denetimini ben yaparım. Kullanıcı kanalını okumak ödeme veya yükleme değildir.

## Görsel varlık ihtiyacı: somut teslim

Mevcut `tonton_referans.png` kimliği korunacak: mavi gövde/kasa, yeşil cam gözleri, turuncu jantlar/üç tepe lambası, siyah lastikler, gümüş tampon. Tilki veya kırmızı kamyon istenmiyor. Tek araç ve yazısız/logosuz sahneler gerekir.

Sahne 1–8'de kasa kumlu; 9'da kendi kasası kalkmış ve kumu boşaltıyor; 10'da kasa boş. Üç farklı yol sahne 3'te; kırmızı köprü sahne 1–7'de görünmez, 8–10'da görünür. Aynı sabit boş kamyon PNG'sini bütün sahnelere koymak hikâyeyi karşılamaz. Kesik tekerlek veya eksik kasa, yeşil/beyaz kenar, yeniden çizilmiş yüz veya yanlış nesne sayısı onaylanamaz. Kaynak referans bunların hepsini sağlamıyor; basit maskeleme bu sorunu çözmez.

Tam varlıklar zaten varsa kullanıcı bunları sağlayabilir. Yoksa ücretsiz alternatif bir çizim stiline geçiş bir kalite kararıdır: mevcut referansla aynı tasarım olduğu ileri sürülmeden önce taslakların ayrıca incelenmesi gerekir. Gerçek görüntü ve video hazır olmadan kullanıcıdan yayın onayı istenmez.

## Tamamlanan takip doğrulaması ve gerçek görsel testi

- Main tabanındaki sınırlı kurtarma paketi: **81 test geçti**. Kod commit'i `20ad8d4` main'e aktarıldı. Ledger/kanal/ses/kilit implementasyonları değişmedi.
- PR #4 tam çevrimdışı paket: **189 test geçti**. Önceki tam gerçek-runner denetiminde **185 test geçti**: [43298216748](https://github.com/akaradag88/minomasal-automation/actions/runs/43298216748). Bu çalışmanın `minomasal-assets-43298216748` artifact'i `recovery/review_package/review.html` ve mevcut Tonton hikâyesi/referansı/anlatımı/kalite raporunu içerir. MP4 içermez.
- Ücretsiz hesap ve yeterli kota yeniden doğrulandıktan sonra ayrı manuel [43299090697](https://github.com/akaradag88/minomasal-automation/actions/runs/43299090697) çalışmasında **yalnız iki** Tonton adayı üretildi. Bildirilen başlangıç kapasitesi 10.000 Neuron; iki 1024×1024 / varsayılan 4-adım görsel için tahmini 115,2 Neuron. Sonraki ölçülen bakiye doğrulanmadı; analitik gecikebilir. Ücretli plan/kullanım etkinleştirilmedi.
- İki aday **REDDİLDİ**: ikinci adayda kanonik yeşil gözler kayboldu; kum kasanın arkasından değil ön tampondan dökülüyor. Tasarım hem referanstan hem birbirinden farklı. Düz olmayan arka plan nedeniyle iki otomatik maske de reddedildi. Görüntüler [PR #4 teşhis klasöründe](https://github.com/akaradag88/minomasal-automation/tree/feat/adim-10-9-free-image-providers/docs/recovery/tonton-rejected-trial) yalnız teşhis için saklanır, onaylı kataloğa girmez. Bu adayları onaylamanız istenmiyor.
- Dolayısıyla görsel kalitesini onaylanmış sayıp MP4 üretmek veya yayın istemek doğru değil. Daha fazla gerçek görsel denemesi yapılmadı. PR #4 taslak ve birleştirilmemiş durumda.

Kullanıcıya kalan kararlar: YouTube OAuth okuma izni; mevcut Sami projesinde ücretsiz kullanım/kota kanıtı; görsel yolunun seçimi. Mevcut 3B Tonton aynen korunacaksa eksiksiz sahne/poz varlıkları veya bu kimliği koruyan yerel bir referans üretim yöntemi gerekir. Alternatif, farklı ve sabit bir çizim tasarımının önce incelemeye sunulmasıdır; bu tasarım değişikliği kullanıcı kararı olmadan üretime alınmaz. Sonraki ses/kompozisyon/MP4 kontrolleri ve platform işlemleri asistanın işidir; kullanıcıdan kod düzeltmesi veya sıradan test çalıştırması istenmez.
