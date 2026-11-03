# ROBODİ — Proje Bağlamı (Claude Code için)

Raspberry Pi 5 tabanlı, Türkçe konuşan, masaüstü arkadaş robotu. Sahibi: Muhammed Kaderoğlu.
Konuşma dili ve kod yorumları **Türkçe**.

## Mevcut durum (2026-11-03)

- Donanım satın alındı, henüz monte edilmedi; kod **simülasyon modunda** çalışabilmeli (servokit,
  PyAudio, Picamera2, pyserial yoksa modüller loglayıp devam eder — bu davranışı koru).
- Donanım kararları ve malzeme listesi teslim dosyasında (tasarım/elektronik/yazılım):
  https://claude.ai/artifact/8TQMM8cfHA8NmkyNqxhXDY
- `core/` → `src/` birleştirmesi yapıldı (2026-11-03): tek giriş noktası `main.py`, tek systemd
  servisi (`robodi.service` → `main.py`), web paneli aynı süreçte (port 8080). `core/` silindi.
  Birleştirme kuralının kalan kısmı için "Açık işler"e bak.
- Tek kurulum betiği `scripts/setup.sh`: sistem Python'u + `pip --break-system-packages` (venv yok).
  `robodi.service` depoda dosya olarak tutulmaz; betik tee ile depo dizini/kullanıcıyla yazar.

## Mimari

- Durum makinesi: `IDLE → LISTENING → PROCESSING → SPEAKING → MOVING → ERROR`
  (`src/core/state_machine.py`). Geçişler `TRANSITIONS` sözlüğünde; yeni durum eklerken orayı güncelle.
- `src/core/robot.py` orkestratör. Bloklayan I/O her zaman `run_in_executor` ile.
- Flask ayrı thread'de; asyncio döngüsüne `asyncio.run_coroutine_threadsafe` ile köprü.
- Servolar PCA9685 üzerinden (`src/servo/controller.py`, `adafruit-circuitpython-servokit`), I2C 0x40.
  Kanal, açı sınırı, offset, darbe aralığı ve yön `settings.yaml → servos.channels`'ta. Beş servo:
  `head_pan`, `head_tilt`, `left_arm`, `right_arm`, `waist` (gövde ±90°). Yüz takibinde kafa
  `servos.waist_handoff` derecesini geçince gövde kişiye döner, kafa geri gelir (`Robodi._waist_handoff`).
- ESP32 ekran kartları USB ile (`src/core/esp32_comm.py`): eyes, mouth, chest. `esp32.boards: auto` ise
  portlar `{"cmd":"WHO"}` ile taranır. 115200, satır sonlu JSON; her karta yalnızca kendi alanı gider.
  Komutlar: WHO, INIT, EXPRESSION, BLINK, BRIGHTNESS, SLEEP. Yeni komut eklenirse hem
  `src/core/esp32_comm.py` hem ilgili `esp32/*/*.ino` güncellenir (bkz. `esp32/README.md`).
- Ses seviyesi: PAM8403'te düğme yok; `Speaker.set_volume` → `amixer` (ReSpeaker WM8960 mikseri).
- Wake word: openWakeWord (`src/audio/listener.py`, şimdilik `hey_jarvis` modeli).
  STT: Vosk offline (`models/vosk-model-small-tr`). TTS: pyttsx3 (offline) / edge-tts `tr-TR-AhmetNeural`.
- LLM (`src/ai/agent.py`): `ai.provider: claude` ise Claude API (`ANTHROPIC_API_KEY` gerekir),
  ulaşılamazsa Ollama `llama3.2:3b` (`POST localhost:11434/api/chat`) yedek; `provider: ollama` sadece yerel.
- Yüz kimliği `src/vision/face_id.py` (Camera karesini kullanır, kendi kamerasını açmaz);
  Gmail özeti `src/services/gmail.py` (ilk yetki: `python -m src.services.gmail`).
- Web paneli girişi zorunlu: şifre `ROBODI_ADMIN_PASSWORD` (tanımsızsa giriş kapalı), oturum anahtarı
  `ROBODI_SECRET_KEY` (yedek: `web.secret_key`). Kullanıcı ekleme robotun kamerasından kare alır
  (`/api/users/add` → `FaceIdentifier.add_user`). Testler: `python -m pytest tests/` (Flask, numpy, pytest yeterli).
- Panel sayfaları (Panel, Kullanıcılar, Loglar, Ayarlar) hep `base.html`'i genişletir; stiller tek dosyada
  (`web/static/css/style.css`). Panel durumu `Robodi.status()`'tan gelir (`/api/status`). Ayarlar sayfası
  `settings.yaml`'ı metin olarak düzenler: kaydetmeden önce YAML ve zorunlu bölümler doğrulanır, eski hâl
  `.bak` olarak saklanır, yorumlar korunur. werkzeug erişim logları kapalı (panel sorguları logu doldurmasın).
- Kişisel veriler (`data/`: yüz kodlamaları, yetkili kullanıcılar, Gmail token) git'e girmez.
- Tüm ayarlar `config/settings.yaml`; koda sabit pin/port gömme.

## Pin haritası (Raspberry Pi 5, BCM)

| İşlev | GPIO | Not |
|---|---|---|
| I2C SDA / SCL | 2 / 3 | ReSpeaker WM8960 (0x1A) + PCA9685 (0x40) aynı hatta |
| ReSpeaker I2S | 18 / 19 / 20 / 21 | **Başka iş için kullanma** |
| ReSpeaker buton | 17 | |
| ReSpeaker LED (APA102, SPI) | 10 / 11 | |
| AI HAT+ 2 | PCIe, ID EEPROM 0 / 1 | |
| AI Camera / Kamera 3 NoIR | CSI 0 / CSI 1 | 30 cm Pi 5 kabloları |
| ESP32 kartları | USB | eyes, mouth, chest |

PCA9685 kanalları: 0 kafa yatay, 1 kafa dikey, 2 sol kol, 3 sağ kol, 4 gövde.
Servo hattı Pi'den değil Savior 5V 10A kaynaktan (anahtar + 5A sigorta + 1000 µF), GND ortak.
MG996R zorlanınca ~2.5 A çeker; gövde ve kafayı aynı anda hızlı döndürme.

## Donanım listesi

RPi 5 16GB + aktif soğutucu + AI HAT+ 2, ReSpeaker 2-Mics Pi HAT (uzun bacaklı başlıkla AI HAT+ 2 üstünde),
Raspberry Pi AI Camera (IMX500, kafada), Kamera Modül 3 NoIR (gövdede), PAM8403 + 2× 8Ω 5W hoparlör,
Waveshare ESP32-S3 1.28" çift göz, ESP32-C3 1.47" LCD (ağız), ESP32-S3 1.69" dokunmatik (göğüs),
PCA9685, Motorobit metal pan-tilt + 2× MG996R (kafa), 3× MG996R 180° (kollar + gövde), döner bilyalı tabla,
Pi 27W USB-C adaptör, Savior 5V 10A servo güç kaynağı.

## Çalıştırma

```bash
./scripts/setup.sh                # RPi üzerinde tam kurulum (apt + pip + servis)
python main.py --debug            # tam mod
python main.py --web-only         # sadece panel (geliştirme makinesinde)
```

## Açık işler

1. `esp32/*/pins.h` pinleri Waveshare wiki'den doldurulacak; firmware'ler derlenip donanımda denenecek.
2. Servo darbe aralıkları (`min_pulse`/`max_pulse`, şimdilik 500–2500 µs) ve yönleri donanımda kalibre edilecek.
3. Tasarımcının ifade görselleri gelince ESP32 çizimleri onlarla değiştirilecek.
4. Özel "hey robodi" openWakeWord modeli eğitilecek (`audio.wake_word_model`).
5. ReSpeaker overlay adı (`wm8960-soundcard`) ve mikser kontrol adları Pi 5'te doğrulanacak.
6. AI HAT+ 2: yerel yedek modelin kartta çalıştırılması (`src/ai/agent.py`).

## Kurallar

- Küçük, odaklı commit'ler; mesajlar Türkçe.
- Donanım kütüphanesi import'ları her zaman try/except ile, simülasyon fallback'i zorunlu.
- Yeni bağımlılık eklerken `requirements.txt` ve `scripts/setup.sh` birlikte güncellenir.
