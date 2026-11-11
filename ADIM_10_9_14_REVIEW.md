# Adım 10.9.14 — bağımlılık kurulumunu sınırlandırma

11 Kasım 2026, mevcut taslak PR #4 üzerinde. Canlı veya başka bir workflow
tetiklenmedi; main'e birleştirme, gerçek video üretimi ve yayın yapılmadı.

## #48 incelemesi ve kanıt sınırı

[Daily YouTube Instagram #48](https://github.com/akaradag88/minomasal-automation/actions/runs/43055108164),
main commit `2f111aecc70d5409d4251aecec4b01535e2d445f`.
Job 16:07:15–17:44:14 UTC arasında **96 dakika 59 saniye** sürdü, sonuç cancelled.
Checkout ve Python kurulumu tamamlanmış; GitHub son aktif adımı Install
dependencies gösteriyor. Günlük slot kontrolü, üretim, kilit alma ve yayın
adımları pending kalmış; bu çalışma yayın aşamasına ulaşmamış.

`gh run view --log` sıfır satır döndürüyor. Ham run-log endpoint'i başarılı
yanıtla **22 baytlık boş ZIP** (sıfır kayıt) döndürdü. Job-log endpoint'inden
log alınamadı; bağlayıcının log çağrısı da sonuç vermedi. Adım metadata'sında
başlangıç/bitiş zamanları yok; son adım in_progress olarak kalmış.

Bu nedenle **kesin takılan alt komut veya dış altyapı kök nedeni belirlenemedi**.
Pip resolver, paket indirme, APT aynası/kilidi, ağ veya runner kaynak problemi
olduğunu kanıtlayan log yok. Runner CPU/RAM/disk ölçümü ve o çalışmanın
seçtiği gerçek paket sürümleri de yok. Bunlardan biri kesin nedenmiş gibi
raporlanmıyor. Kaynak kodunda doğrulanan sorun: APT update/install ve iki pip
çözümlemesi aynı adımda, cache ve ayrı süre sınırları olmadan çalışıyordu.
Job'da zaten 120 dakika sınırı vardı; yaklaşık 97 dakikada kullanıcı iptal
ettiği için bu sınır henüz dolmamıştı.

## Bağımlılık kullanım kontrolü

Hiçbir paket kaldırılmadı, mevcut sürüm kısıtları değiştirilmedi.

| Bağımlılık | Kullanım |
|---|---|
| edge-tts | minomasal.py modül import'u ve mevcut TTS işlevleri |
| Pillow / numpy / requests | Görseller, ses örnekleri, HTTP ve kalite işlemleri |
| google-genai | Hikâye üretimi ve Sami TTS / hizalama modülleri |
| google-api-python-client / google-auth / google-auth-httplib2 | minomasal.py::upload_youtube ve Google istemcisinin yetkilendirmesi |
| faster-whisper | minomasal_sami_hizalama_v2.py::WhisperModel; günlük V3 stage bu hizalamayı kullanır |
| FFmpeg / ffprobe / DejaVu fontları | Video render, medya doğrulaması ve ASS altyazı |

Mevcut ek günlük paketler requirements-minomasal-daily.txt dosyasına taşındı;
bu dosya requirements-minomasal.txt'yi de içerir. İki ayrı pip çözümlemesi
yerine tek kurulum yapılır. Google paketlerinin önceki sürümsüz hali korunur;
bu değişiklik tam bir transitive lock dosyası iddiasında değildir.

## Uygulanan düzeltmeler

- setup-python pip indirme/wheel cache'i açıldı. Anahtar iki requirements
  dosyasına bağlı; action'ın OS/Python/requirements anahtarlaması kullanılır.
  Secret, üretim dosyası, yayın defteri veya sanal ortam cache'lenmez.
- Mevcut FFmpeg, ffprobe ve DejaVu varsa gereksiz APT yenilemesi atlanır;
  araç/font yoksa aynı paketler kurulur. Son aşamada import, ffprobe ve ASS
  filtresi ayrıca doğrulanır. Whisper modeli oluşturulmaz veya indirilmez.
- APT update komutu en fazla 2 dakika; install en fazla 5 dakika.
  HTTP/HTTPS bekleme 30 saniye, retry 2, dpkg kilit bekleme 60 saniye;
  sudo ve paket yönetimi etkileşimsizdir.
- Pip bağlantı/okuma beklemesi 30 saniye, retry 2; paket kurulumu toplam
  en fazla 8 dakika. `--prefer-binary` mevcut wheel'i tercih eder;
  `--no-input`, kapalı sürüm kontrolü ve pip check uygulanır.
- GNU timeout TERM sonrası en fazla 15 saniye bekleyip KILL uygular.
  Kurulum hatası veya zaman aşımı sonraki komutlara/üretime geçmez.
- Actions adım sınırları: setup/cache 5, kaynak teşhisi 1, APT 8, pip 10,
  doğrulama 2 dakika. Toplam üretim-yayın job sınırı **90 dakika** oldu.
  GitHub Actions'ta bu iş için workflow düzeyinde timeout alanı yoktur;
  günlük workflow'un tek job'u bu sınırla korunur.
- Gelecek çalışmalarda APT ve pip ayrı adımlar/log başlıklarıyla görülecek.
  Disk/RAM teşhisi ve Python/pip sürümleri yazılır; environment/pip config
  veya Secret değerleri dökülmez.

## Çevrimdışı doğrulama

` .venv-readiness/bin/python run_readiness_tests.py`: **118 test başarılı**,
yaklaşık **3,15 saniye**. Altı yeni test:

1. Sahte pip ile hızlı başarılı kurulum, tek resolver, retry/timeout bayrakları
   ve kurulum sonrası pip check.
2. Pip hata kodunda hemen durma, sonraki doğrulamaya geçmeme.
3. Sahte takılan pip'i gerçek GNU timeout ile kısa test süresinde öldürme;
   exit 124, tekrar istek ve sonraki komut yok.
4. APT update hatasında install komutuna geçmeme; APT ağ/kilit sınırları.
5. Cache girdileri, Actions/job süre sınırları ve yayın güvenlik koşulları.
6. Önceki günlük bağımlılık kümesinin aynen korunması.

Testler gerçek APT/pip indirmesi veya paket kurulumu yapmaz; yalnız izole
sahte komutlarla script'in kontrol akışını ve gerçek deadline davranışını
çalıştırır. **Gerçek GitHub runner'da kurulumun kaç dakika süreceği çevrimdışı
testle ölçülemez; üretim kurulum süresi doğrulandı denmiyor.** Bu adımda
workflow tetiklenmedi. `bash -n` ve `git diff --check` başarılı.

YAML karşılaştırmasıyla günlük slot kontrolünden job sonuna kadar tüm
adımların, cron'un ve concurrency ayarlarının önceki PR başıyla aynı olduğu
doğrulandı. Defter/kilit/çift yayın kodları ve Cloudflare prompt-only HTTP400
düzeltmeleri değişmedi. PR #4 açık ve taslak; main'e birleştirilmedi.
