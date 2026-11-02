# ROBODİ — Proje Bağlamı (Claude Code için)

Raspberry Pi 5 tabanlı, Türkçe konuşan, masaüstü arkadaş robotu. Sahibi: Muhammed Kaderoğlu.
Konuşma dili ve kod yorumları **Türkçe**.

## Mevcut durum (2026-11-03)

- Donanım henüz tam elde değil; kod **simülasyon modunda** çalışabilmeli (RPi.GPIO, PyAudio,
  Picamera2, pyserial yoksa modüller loglayıp devam eder — bu davranışı koru).
- `core/` → `src/` birleştirmesi yapıldı (2026-11-03): tek giriş noktası `main.py`, tek systemd
  servisi (`robodi.service` → `main.py`), web paneli aynı süreçte (port 8080). `core/` silindi.
  Birleştirme kuralının kalan kısmı için "Açık işler"e bak.

## Mimari

- Durum makinesi: `IDLE → LISTENING → PROCESSING → SPEAKING → MOVING → ERROR`
  (`src/core/state_machine.py`). Geçişler `TRANSITIONS` sözlüğünde; yeni durum eklerken orayı güncelle.
- `src/core/robot.py` orkestratör. Bloklayan I/O her zaman `run_in_executor` ile.
- Flask ayrı thread'de; asyncio döngüsüne `asyncio.run_coroutine_threadsafe` ile köprü.
- ESP32 ile UART `/dev/ttyAMA0` 115200, satır sonlu JSON: `{"cmd":"EXPRESSION","eyes":"happy"}`.
  Komutlar: EXPRESSION, BLINK, BRIGHTNESS, INIT, SLEEP. Yeni komut eklenirse hem
  `src/core/esp32_comm.py` hem `esp32/eyes/eyes.ino` güncellenir.
- Wake word: openWakeWord (`src/audio/listener.py`, şimdilik `hey_jarvis` modeli).
  STT: Vosk offline (`models/vosk-model-small-tr`). TTS: pyttsx3 (offline) / edge-tts `tr-TR-AhmetNeural`.
- LLM (`src/ai/agent.py`): `ai.provider: claude` ise Claude API (`ANTHROPIC_API_KEY` gerekir),
  ulaşılamazsa Ollama `llama3.2:3b` (`POST localhost:11434/api/chat`) yedek; `provider: ollama` sadece yerel.
- Yüz kimliği `src/vision/face_id.py` (Camera karesini kullanır, kendi kamerasını açmaz);
  Gmail özeti `src/services/gmail.py` (ilk yetki: `python -m src.services.gmail`).
- Web paneli girişi zorunlu: şifre `ROBODI_ADMIN_PASSWORD` (tanımsızsa giriş kapalı), oturum anahtarı
  `ROBODI_SECRET_KEY` (yedek: `web.secret_key`). Kullanıcı ekleme robotun kamerasından kare alır
  (`/api/users/add` → `FaceIdentifier.add_user`). Testler: `python -m pytest tests/` (Flask, numpy, pytest yeterli).
- Kişisel veriler (`data/`: yüz kodlamaları, yetkili kullanıcılar, Gmail token) git'e girmez.
- Tüm ayarlar `config/settings.yaml`; koda sabit pin/port gömme.

## Pin haritası (Raspberry Pi 5, BCM)

| İşlev | GPIO | Not |
|---|---|---|
| Kafa pan servo | 12 | PWM0, MG996R (Motorobit metal pan-tilt) |
| Kafa tilt servo | 13 | PWM1, MG996R |
| Sol kol servo | 18 | SG90 |
| Sağ kol servo | 19 | SG90 |
| UART TX → ESP32 RX(16) | 14 | |
| UART RX ← ESP32 TX(17) | 15 | |
| ESP32 reset | 23 | |
| TFT DC / RST | 24 / 25 | SPI0 CE0 (GPIO8), MOSI 10, CLK 11 |
| PAM8403 SD (mute, aktif LOW) | 26 | |
| ReSpeaker 2-Mics HAT | I2S 18/19/20/21, I2C 2/3 | HAT olarak takılı |
| IMX500 AI Camera | CSI | |

ESP32-S3: MAX7219 DIN=5, CLK=18, CS=19; OLED I2C SDA=21, SCL=22.
Servo 5V hattı RPi'den değil ayrı 5V/3A DC-DC'den, GND ortak. MG996R yük altında >1 A çekebilir.

## Donanım listesi

RPi 5, ReSpeaker 2-Mics Pi HAT, Raspberry Pi AI Camera (IMX500), 3.5" ILI9341 SPI TFT,
PAM8403 + hoparlör, ESP32-S3 DevKitC-1, 2× 8×8 MAX7219 LED matrix (gözler), 128×32 SSD1306 OLED (ağız),
Motorobit Metal Pan-Tilt + 2× MG996R (kafa), 2× SG90 (kollar), 18650 2S2P + 5V/5A DC-DC.

## Çalıştırma

```bash
pip install -r requirements.txt --break-system-packages   # RPi üzerinde
python main.py --debug            # tam mod
python main.py --web-only         # sadece panel (geliştirme makinesinde)
```

## Açık işler

1. Birleştirmenin kalanı: tek kurulum betiği (`scripts/setup.sh` esas; kökteki `setup.sh` ile birleştirilecek).
2. `web/templates/logs.html`, `settings.html` eksik; `web/app.py` rotaları var.
3. `assets/faces/*.png` ifade görselleri yok (`src/display/screen.py` metin fallback kullanıyor).
4. MG996R için `src/servo/controller.py` `angle_to_duty` sınırları (2.5–12.5 %) donanımda kalibre edilecek.
5. Özel "hey robodi" openWakeWord modeli eğitilecek (`audio.wake_word_model`).
6. `esp32/mouth/mouth.ino` OLED ağız animasyonu tamamlanacak.

## Kurallar

- Küçük, odaklı commit'ler; mesajlar Türkçe.
- Donanım kütüphanesi import'ları her zaman try/except ile, simülasyon fallback'i zorunlu.
- Yeni bağımlılık eklerken `requirements.txt` ve `scripts/setup.sh` birlikte güncellenir.
