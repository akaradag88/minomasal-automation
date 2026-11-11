# Adım 10.9.8 — Cloudflare 403 ve en az yetki analizi

11 Kasım 2026, PR #4. Bu adımda Cloudflare hesabına yeni istek veya workflow
çalıştırması yapılmadı. Önceki temizlenmiş rapor, kod ve güncel resmî belgeler
incelendi. Üretim, ödeme, Secret değişikliği veya main birleştirmesi yok.

## 403'ün kesin yeri

Önceki çalışma: [43046808053](https://github.com/akaradag88/minomasal-automation/actions/runs/43046808053).
Rapor: [cloudflare-connection-report.json](docs/adim_10_9_7/cloudflare-connection-report.json).

İstek sırası:

1. `GET https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search`
   — HTTP200, istenen model katalogda bulundu.
2. `GET https://api.cloudflare.com/client/v4/accounts/{account_id}/subscriptions`
   — **HTTP403**, `blocked_at=free_plan`.
3. `POST https://api.cloudflare.com/client/v4/graphql`
   — **çalışmadı**; Neuron kullanım sorgusuna geçilmedi.
4. `POST .../ai/run/@cf/black-forest-labs/flux-1-schnell`
   — çalışmadı; hiçbir görsel üretilmedi.

Dolayısıyla gözlenen hata bir **abonelik okuma yetkisi** engelidir. Kota
endpoint'inin 403 döndürdüğüne veya hesabın ücretli olduğuna dair kanıt yoktur.
Token'ın tam izin listesi okunmadı. Eksik Billing Read veya hesap kaynağı/hesap
rolü kısıtı olasıdır; HTTP403 tek başına bunlardan hangisini kanıtlamaz.

Yeni teşhis çıktısı yalnız HTTP metodunu, **hesap kimliği içermeyen yol şablonunu**
ve endpoint'in belgelenmiş minimum iznini yazar. Anahtar/ham hata gövdesi yazılmaz.

## Endpoint bazında minimum izin

| Amaç / istek | API referansındaki kabul | En az yetki / panel karşılığı |
|---|---|---|
| Model arama: GET ai/models/search | Workers AI Read **veya** Workers AI Write | **Account → Workers AI → Read** |
| Görsel/model çalıştırma: POST ai/run/{model_name} | Workers AI Read **veya** Workers AI Write; en az biri | **Account → Workers AI → Read** belgelenmiş minimumdur. Write/Edit otomatik eklenmemeli. |
| Abonelik okuma: GET accounts/{id}/subscriptions | Billing Read **veya** Billing Write; en az biri | Otomatik abonelik denetimi seçilirse **Account → Billing → Read**. Billing Write/Edit gerekmez. |
| GraphQL kullanım analizi: POST /graphql | GraphQL Analytics kimlik doğrulama rehberi Account Analytics Read tarif eder | Otomatik kullanım sorgusu seçilirse **Account → Account Analytics → Read**. Billing izni bu sorgunun gereği değildir. |

Panelde **Account Resources → Include → Specific account** ile yalnız ilgili
hesap seçilmeli. Global API Key, All Accounts veya hesap yönetimi/yazma izinleri
bu iş için önerilmiyor. API referansındaki “Write”, panelde “Edit” adıyla
görünebilir. Yeni izin eklemeden önce mevcut token kaynağı/hesap kapsamı kontrol
edilmeli; anahtar sohbet veya loglara kopyalanmamalı.

### Workers AI Read yeterli mi?

Endpoint'e özgü güncel API referansı hem model aramada hem `POST ai/run` için
Accepted Permissions altında **en az biri** koşuluyla Read/Write listeler.
Buna göre görsel inference için belgelenmiş minimum **Workers AI Read**'dir.

Başlangıç REST rehberi ise custom token için Read ve Edit birlikte diyor. Bu
belge tutarsızlığıdır. Önceki PR raporundaki “ikisi de zorunlu” ifadesi minimum
yetki sonucu olarak düzeltilmiştir: endpoint sözleşmesi esas alınır. Gerçek
Read-only token ile görsel çalıştırma bu adımda sınanmadı; üretim yasağı korundu.

“Read” adı, bu endpoint'te yalnız katalog okuma veya sıfır maliyet anlamına gelmez:
inference yetkisiyle kota tüketilebilir. Token izni, ücretsiz kullanım kanıtından
ayrı değerlendirilmelidir.

Kaynaklar:

- [Run a Workers AI model, Accepted Permissions](https://developers.cloudflare.com/api/resources/ai/methods/run/)
- [Model Search, Accepted Permissions](https://developers.cloudflare.com/api/resources/ai/subresources/models/methods/list/)
- [List Subscriptions, Accepted Permissions](https://developers.cloudflare.com/api/resources/accounts/subresources/subscriptions/methods/get/)
- [REST başlangıç rehberi, farklı Read/Edit önerisi](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)
- [Account Analytics Read panel ayarı](https://developers.cloudflare.com/analytics/graphql-api/getting-started/authentication/api-token-auth/)
- [Account/User/Zone izin kategorileri ve panel adları](https://developers.cloudflare.com/fundamentals/api/reference/permissions/)

## Billing / Analytics olmadan hangi doğrulama güvenilir?

Üç farklı bilgi birbirinden ayrılmalı:

- **Model çağırma yetkisi:** Workers AI Read ile belgelenmiş erişim. Billing ve
  Analytics bunun zorunlu izinleri değildir.
- **Ücretsiz planın kanıtı:** Workers Free olup aşımın faturalanmadığının kontrolü.
- **Şu an kalan ücretsiz Neuron:** Hesabın o UTC günündeki diğer kullanımları da
  hesaba katılmalıdır. Genel 10.000/gün tahsisi, kalan 10.000 demek değildir.

Resmî Workers AI API katalog ve kota/fiyat belgelerinde, yalnız Workers AI Read
ile **hem ücretsiz planı hem güncel kalan Neuron'u birlikte** doğrulayan
belgelenmiş bağımsız bir endpoint bulunamadı. Bu bir dokümantasyon araştırması
sonucudur; bütün özel/dahili Cloudflare uçları için yokluk iddiası değildir.

### Seçenek 1 — Ek API izni vermeden panelden doğrulama

Hesap sahibi Cloudflare panelindeki Workers/Workers AI plan ve kullanım ekranında
Workers Free planını, bugünkü Neuron tüketimini ve uygun ücretsiz model erişimini
kontrol edebilir. Böylece üretim token'ına Billing/Analytics eklenmez. Fiyat
belgesi kullanımın Workers AI dashboard'dan izlenebildiğini belirtir.

Bu, kontrol anı için insan tarafından yapılan doğrulamadır. Araya başka kullanım,
plan değişikliği veya kota reseti girerse gözetimsiz günlük otomasyon için güncel
kanıt sayılmaz. Bir ortam bayrağı, “kart yok” bilgisi veya yerel 10-görsel sayacı
tek başına yeterli değildir. Bu PR'daki otomatik güvenlik kapıları bu analizle
kaldırılmadı ve panel onayını taklit eden bir otomatik geçiş eklenmedi.

### Seçenek 2 — Otomatik denetim gerekiyorsa token'ları ayırmak

Önerilen en az yetki mimarisi:

- Üretim token'ı: sadece ilgili hesapta **Workers AI Read**.
- Ayrı, salt okunur denetim token'ı: yalnız ihtiyaç duyulan **Billing Read** ve
  **Account Analytics Read**, ilgili hesapla sınırlı. Üretim endpoint'i yetkisi
  bu token'a eklenmez; üretim job'una geçirilmez.
- Denetim yalnız şablon/sayı/zaman içeren temiz sonuç üretir. İleride bu sonucun
  tazeliği ve doğru hesaba bağlanması ayrıca uygulanmadan bir bayrak gibi
  kullanılamaz. Bu adımda böyle bir token yaratılmadı, istenmedi veya kullanılmadı.

Billing/Analytics izinleri inference token'ının çalışması için değil, **seçilen
otomatik denetim yönteminin** gereğidir. Mevcut tek-token test kodu bu ayrımı
henüz uygulamadığından, kullanıcı bu yöntemi seçmeden üretim token'ına otomatik
olarak daha geniş izinler eklememeli.

### Araştırılan ama kalan kotanın yerine geçmeyen yollar

- `GET /accounts/{id}/entitlements`: resmî belge **Account Read** ister ve özellik
  tahsislerini döndürür. Güncel tüketim/kalan günlük kota sözleşmesi yoktur;
  mevcut doğrulamayı bununla değiştirmek veya daha az yetkili saymak doğru değil.
- Model katalog/şema GET'i: model erişimini gösterir; Free planı veya kalan
  Neuron'u kanıtlamaz.
- Yerel istek sayacı: aynı hesabın başka uygulamalardaki kullanımını kapsamaz.
- Deneme inference isteği veya istek sonrası usage bilgisi: üretimden **önce**
  ücretsiz kullanım kanıtı değildir. Bu adımda böyle bir istek yapılmadı.
- Sadece kota dolunca durma: Workers Paid üzerinde aşım faturalanabilir; plan
  doğrulanmadan kabul edilmez.

GraphQL'den hesaplanan kalan değer de `10.000 - bildirilen kullanım` tahminidir;
resmî ve anlık “remaining quota” cevabı değildir. Analytics gecikebilir/örneklenebilir.
Çıktıya `authoritative_remaining_quota=false` eklenerek bu sınır açıklaştırıldı.

Kaynaklar:

- [Workers AI ücretsiz tahsis ve Paid aşımı](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Workers AI limits, hız sınırları](https://developers.cloudflare.com/workers-ai/platform/limits/)
- [Account entitlements: tahsisler ve Account Read izni](https://developers.cloudflare.com/api/resources/accounts/subresources/entitlements/methods/list/)

## Bu adımın teslimi

PR #4'e bu rapor, doğru endpoint/metot/minimum izin teşhisi ve regresyon testleri
eklendi. Plan/kota kapıları, varsayılan kalite kapısı ve yayın güvenliği korunur.
Cloudflare'a yeni hesap/inference isteği, workflow tetiklemesi, Secret değişikliği,
ödeme veya canlı yayın yapılmadı. Main'e birleştirilmedi.
