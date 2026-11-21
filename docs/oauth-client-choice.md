# Mevcut YouTube OAuth istemcisini adlandırma

## Şu an kanıtlanan / kanıtlanmayan

- GitHub Secrets API, Secret değerini döndürmez. Bu entegrasyonun
  `YOUTUBE_CLIENT_ID` metadata isteği de HTTP 403 verdi; değer doğrudan okunmadı.
- 14 Kasım hesap denetiminde mevcut `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`
  ve `YOUTUBE_REFRESH_TOKEN` ile Google token endpoint'i HTTP 200 döndürdü:
  [run 43614676035](https://github.com/akaradag88/minomasal-automation/actions/runs/43614676035).
  Bu, mevcut refresh token/istemci çiftinin geçerli olduğunun kanıtıdır; Google
  Cloud Console'daki dahili görünen istemci adını söylemez.
- Analytics ve Colab adları, ortak sayısal başlangıç ve Colab'ın 14 Kasım kullanım
  tarihi tek başına eşleşme kanıtı değildir. **Henüz ikisinden biri seçilmedi.**

## Kullanıcının tek işlemi

`tools/minomasal-oauth-client-kontrol.html` dosyasını laptopa indirip güncel
Chrome/Edge'de yerel olarak açın. Google Cloud'daki **MinoMasal Analytics Client**
ve **MinoMasal Colab Client** kartlarından tam **Client ID** değerlerini kendi
adlarıyla işaretli iki alana yapıştırın, **Güvenli kontrol dosyasını indir**
düğmesine basın ve yalnız oluşan **minomasal-client-check.json** dosyasını
sohbete ekleyin.

OAuth JSON dosyası indirmek/paylaşmak, Client Secret veya token girmek, yeni
refresh token üretmek, GitHub CLI kurmak veya Secret değiştirmek gerekmez.

## Yerel dosya ve Actions arasındaki işlem

- HTML'de dış kaynak/kütüphane/telemetri yok. CSP `connect-src 'none'` ile ağ
  isteklerini kapatır. Tam ID'ler yalnız kullanıcının tarayıcı belleğinde kalır.
- Her paket oluşturulduğunda rastgele 32 bayt nonce üretilir. Paket yalnız sürüm,
  nonce ve iki **aday OAuth Client ID** için nonce'a bağlı HMAC eşitlik kanıtları
  içerir; tam kimlikler, tokenlar, Client Secret veya API anahtarı içermez.
  API anahtarı, access/refresh tokenı veya Client Secret için hash/özet üretilmez.
- Paket bir OAuth giriş/kullanım yetkisi sağlamaz; sadece iki adaydan hangisinin
  kayıtlı istemciyle aynı olduğunu sormaya yarar. Bir kimlik için kalıcı parmak
  izi oluşturmak yerine her oluşturma işleminde yeni nonce kullanılır.
- Asistan paketi **yerelde `parse_packet` ile doğruladıktan sonra** PR #5'in
  kayıtlı manuel test workflow'unu yalnız `client_id_challenge` girdisiyle
  çalıştırır; tüm diğer modlar false kalır. Ham kimlik/credential JSON'u yanlışlıkla
  verilmişse API'ye göndermeden reddedilir.
- Actions mevcut Secret kimliğinin karşılaştırma değerini sadece bellekte hesaplar;
  bu değer veya kimliğin kendisi log/artifact'e yazılmaz. Çıktıda yalnız eşleşen
  adayın adı yer alır.
- Tek bir aday eşleşirse mevcut refresh token/Client Secret/Client ID ile Google
  token endpoint'ine **bir** doğrulama isteği yapılır. Ancak HTTP 200 ve geçerli
  access-token yanıtı varsa `confirmed_choice` kesin istemci adıyla doldurulur.
  Token yanıtı veya değerleri kaydedilmez. İsim eşleşse bile refresh başarısızsa
  bağlı istemci doğrulanmış ilan edilmez.
- Secret yazma/iptal endpoint'i, YouTube upload veya yayın çağrısı yoktur. Yeni
  token üretilmez; mevcut token refresh edilmesi mevcut Secret değerini değiştirmez.

## Test kanıtı

244 çevrimdışı regresyon testi geçti. Yeni 7 test; iki adayın ayrı eşleşmesini,
ortak başlangıcın yeterli olmamasını, Google hatasında yanlış doğrulamayı,
geçersiz/credential içeren paketin reddini ve Secret değerleri/özetlerinin
çıktıya sızmamasını kontrol ediyor.

Gerçek headless Chromium ile sayfa, nonce/HMAC Python uyumu, dosya indirme,
girdilerin temizlenmesi, aynı iki kimliğin reddi ve sıfır dış ağ isteği doğrulandı.
Yönetilen Cloud tarayıcısı file:// erişimini yönetici politikasıyla engellediği
için aynı dosya localhost üzerinden test edildi; politika değiştirilmedi.
Normal yerel tarayıcıda dosya açılırken kurum politikası izin vermiyorsa bunu
başarılı bir dosya-açma testi gibi sunmuyoruz.

**Gerçek kullanıcı paketi henüz gelmedi. Eşleşme workflow'u gerçek adaylarla
çalıştırılmadı; Analytics/Colab adı henüz kanıtlanmadı.**
