# Yayına dönüş — zorunlu hesap işlemleri

Bu adım yalnız YouTube OAuth ve Gemini ses hesabını doğrular. Yayın, video
üretimi, ledger değişikliği, #45/#46/#47 durum güncellemesi ve token iptali yapmaz.
Main ve PR #4/#5 birleştirilmez.

## YouTube: kullanıcıdan gereken kesin işlem

1. Google Cloud Console → aynı proje → Google Auth Platform / Clients (eski
   arayüzde APIs & Services → Credentials). **GitHub'daki mevcut
   YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET çiftine ait aynı OAuth istemcisinin**
   JSON'unu laptopa indirin. Yeni OAuth istemcisi oluşturmayın. JSON'u GitHub'a,
   sohbete veya artifact'e koymayın.
2. Mevcut istemci Web Application ise yetkili redirect URI listesinde
   `http://127.0.0.1:8765/` bulunmalı. Desktop istemcisi loopback akışını destekler.
   OAuth consent ekranında YouTube `youtube.upload` ve `youtube.readonly` kapsamları
   kullanılabilmeli; uygulama Testing ise kendi hesap erişimini ve uzun süreli
   otomasyon için Google'ın token yaşam süresi koşullarını kontrol edin.
3. PR #5 dalının güncel tam repo kopyasında laptop terminalinden çalıştırın:

```bash
python scripts/minomasal_youtube_reauthorize.py --client-file /yerel/yol/client_secret.json
```

Tarayıcıda MinoMasal kanalının sahibi hesabı / doğru Brand Account kanalını seçin,
hem video yükleme hem YouTube hesabını okuma kapsamını onaylayın. Yardımcı OAuth
state/PKCE kullanır; yeni refresh tokenı ayrıca yenileme isteğiyle test eder ve
kanalı ledger'daki son iki yayımlanmış videonun gerçek `channelId` değerleriyle
karşılaştırır. Kanal yanlışsa veya kapsam eksikse token kaydedilmez. Hiç video
yüklenmez. Token/Authorization/kod/kanal kimliği ekrana yazılmaz.

4. Başarılıysa token özel `youtube-refresh-token.private` dosyasına yazılır.
   GitHub repo → Settings → Secrets and variables → Actions → **New repository
   secret**: `YOUTUBE_REFRESH_TOKEN_CANDIDATE`. İçeriğini yalnız bu özel dosyadan
   GitHub'ın Secret giriş alanına aktarın. Mevcut `YOUTUBE_REFRESH_TOKEN` değerine
   henüz dokunmayın. Laptopta GitHub CLI zaten oturum açmışsa 3. adımdaki komuta
   `--stage-github-candidate` eklenmesi bu aday Secret yazımını stdin üzerinden
   otomatik yapar; token komut argümanına veya çıktısına konmaz.
5. Bana yalnız **“aday YouTube Secret hazır”** deyin. Hesap-only test, adayı
   GitHub'daki **mevcut** istemci Secret'larıyla doğrular. Bu, yanlış istemci JSON'u
   seçilmesine karşı ikinci kontroldür. Rapor `candidate_youtube.status=verified`,
   iki kapsam ve `channel_matches_ledger=true` olmadan asıl Secret değiştirilmez.
6. Doğrulanınca aynı özel dosyadan yalnız `YOUTUBE_REFRESH_TOKEN` Secret'ını
   güncelleyin. CLI kullanıyorsanız dosya/stdin yöntemi:

```bash
gh secret set YOUTUBE_REFRESH_TOKEN --repo akaradag88/minomasal-automation < youtube-refresh-token.private
```

Eski token için **revoke / erişimi kaldır** işlemi yapmayın; kod iptal endpoint'i
çağırmaz. Güncellenmiş asıl Secret da hesap testiyle doğrulandıktan sonra aday
Secret ve geçici yerel dosya kaldırılabilir. Client ID/secret ve diğer hizmet
Secret'ları değişmez. Token değerini, parçasını veya hash'ini sohbete göndermeyin.

## Gemini: değişkeni açmak için gereken kanıt

- API key ile `GET /v1beta/models` başarıyla okunabilir ve mevcut TTS modelinin
  listede olması kontrol edilir. Bu, **billing planını veya kalan kotayı kanıtlamaz**.
- Hesap sahibi [AI Studio API keys](https://aistudio.google.com/api-keys) ve
  [Usage / Rate limits](https://aistudio.google.com/usage) ekranlarında **mevcut
  GEMINI_API_KEY'in bağlı olduğu aynı projeyi** seçmeli. Plan **Free tier** olmalı;
  `gemini-3.8-flash-tts` için kısa bir test isteğine yeterli kullanılabilir
  istek/token kotası bulunmalı. Tier 1/paid, modelin yalnız listelenmesi veya
  Cloudflare bakiyesi bu onay yerine geçmez. Ödeme/billing etkinleştirmeyin.
- Ancak bu iki koşul doğrulanınca GitHub → Settings → Secrets and variables →
  Actions → **Variables** altında `MINOMASAL_GEMINI_FREE_TIER_CONFIRMED=true`
  ayarlayın. Bu bir API anahtarı değil, hesap sahibinin ücretsiz proje/kota
  doğrulamasıdır. Test raporu bu beyanı API ile ölçülmüş kalan bakiye diye sunmaz.
- Sonra hesap-only test en fazla **bir** kısa Türkçe Sami WAV isteği yapar,
  süre/başlığı denetler ve `minomasal-accounts-<run_id>` artifact'ine koyar.
  Doğrulama yoksa çağrı yapılmaz. Ücretli modele veya farklı sese geçilmez.
- Yeni Gemini Secret gerekmez; mevcut `GEMINI_API_KEY` korunur. Proje/key
  değiştirilirse ücretsiz hesap onayı yeniden kontrol edilmelidir.

Resmî fiyat sayfası mevcut model için Free tier girdi/çıktıyı ücretsiz listeliyor;
API ek şartları profesyonel/ticari kullanım ve üretilen içerik hükümlerini açıklıyor.
Bu, hesabın planını veya her kullanımın hak uygunluğunu otomatik kanıtlamaz.

Kaynaklar:
- https://ai.google.dev/gemini-api/docs/pricing#gemini-3.8-flash-tts
- https://ai.google.dev/gemini-api/terms
- https://developers.google.com/youtube/v3/docs/channels/list
- https://developers.google.com/identity/protocols/oauth2/web-server

Mevcut yedek değerlendirmesi: Piper'ın güncel Türkçe DFKI model kartı veri için
CC BY-NC-SA 4.0 bağlantısı veriyor; ticari uygunluğu doğrulanamadığından otomatik
kullanılmıyor. Edge TTS istemcisinin açık kaynak olması, Microsoft ses hizmetinin
ücretsiz/ticari kullanım lisansını kanıtlamıyor. Onaylanmış, lisansı ve Türkçe
kalitesi doğrulanmış başka otomatik yedek henüz yok; ses klonlama yapılmıyor.
