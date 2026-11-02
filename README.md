# 🤖 ROBODİ — Masa Arkadaşı Robot

Raspberry Pi 5 tabanlı, AI destekli akıllı masa robotu.

## Özellikler

- 👁️ **Göz Animasyonları** — ESP32 ekranlarda kırpan, ifadeli gözler
- 👄 **Ağız Animasyonu** — Konuşma sırasında senkronize ağız hareketi
- 🎙️ **Wake Word** — openWakeWord ile aktifleşme (şimdilik "hey jarvis"; özel "hey robodi" modeli eğitilecek)
- 👤 **Yüz Tanıma** — AI Camera ile kullanıcı kimlik doğrulama
- 🧠 **AI Sohbet** — Claude API (online) / Ollama + Llama 3.2 (offline yedek)
- 📧 **Gmail Özeti** — Sabah mail özetleri
- 🎭 **Şakalar** — Gün içi otomatik şakalar
- 🌐 **Web Dashboard** — Yönetim paneli (ayarlar, loglar, kullanıcılar)

## Donanım

| Bileşen | Model |
|---------|-------|
| Ana kart | Raspberry Pi 5 (16GB) |
| AI Hızlandırıcı | Raspberry Pi AI HAT+ 2 (26 TOPS) |
| Kamera | Raspberry Pi AI Camera (Sony IMX500) |
| Mikrofon | ReSpeaker 2-Mics Pi HAT |
| Hoparlör | Waveshare 8R 5W + PAM8403 amp |
| Göz ekranları | ESP32-S3 + 1.69" LCD ×2 |
| Ağız ekranı | ESP32-C3 + 1.47" LCD |

## Kurulum

```bash
git clone https://github.com/goktalay/robodi.git
cd robodi
chmod +x setup.sh
./setup.sh
```

## Yapılandırma

```bash
nano .env
```

Doldurulacak değerler:
- `ANTHROPIC_API_KEY` — Claude API anahtarı (yoksa yerel Ollama kullanılır)
- `ROBODI_ADMIN_PASSWORD` — Web dashboard şifresi

Diğer tüm ayarlar `config/settings.yaml` içinde (donanım pinleri, AI modeli, şaka aralığı, sabah özeti saati, Gmail).

Gmail sabah özeti için bir kez tarayıcıyla yetkilendirin:

```bash
python -m src.services.gmail
```

## Başlatma

```bash
sudo systemctl start robodi
```

Robot ve web paneli tek serviste çalışır. Elle başlatmak için: `python main.py` (`--no-web`, `--web-only`, `--debug` seçenekleri var).

Web paneli: `http://<raspberry-ip>:8080`

## Proje Yapısı

```
robodi/
├── main.py             # Giriş noktası (robot + web paneli)
├── config/settings.yaml # Tüm ayarlar
├── src/
│   ├── core/
│   │   ├── robot.py         # Ana döngü, sohbet, zamanlanmış görevler
│   │   ├── state_machine.py # IDLE / LISTENING / PROCESSING / SPEAKING
│   │   └── esp32_comm.py    # ESP32 UART (göz/ağız ifadeleri)
│   ├── audio/
│   │   ├── listener.py      # Wake word (openWakeWord) + STT (Vosk)
│   │   └── speaker.py       # TTS (pyttsx3 / edge-tts) + ses efektleri
│   ├── vision/
│   │   ├── camera.py        # IMX500 / OpenCV kamera, yüz algılama
│   │   └── face_id.py       # Yüz tanıma, yetkili kullanıcılar
│   ├── ai/agent.py          # Claude + Ollama sohbet ajanı
│   ├── services/gmail.py    # Gmail sabah özeti
│   ├── servo/controller.py  # Kafa pan-tilt servoları
│   └── display/screen.py    # 3.5" TFT yüz ekranı
├── web/                # Flask web dashboard
├── esp32/
│   ├── eyes/eyes.ino   # Göz animasyon firmware
│   └── mouth/mouth.ino # Ağız animasyon firmware
├── data/               # Yüz verileri, kullanıcı listesi, Gmail token
├── logs/               # Log dosyaları
└── models/             # Vosk modeli
```

## ESP32 Kurulumu

Arduino IDE'de gerekli kütüphaneler:
- `TFT_eSPI` — LCD sürücüsü
- `ArduinoJson` — JSON parse
- WiFi (built-in)

`eyes/eyes.ino` ve `mouth/mouth.ino` dosyalarını ilgili ESP32'lere yükleyin.

## Lisans

MIT License — Muhammed Kaderoğlu

## Kafa Pan-Tilt Donanımı

Motorobit "Metal Pan Tilt 2 Eksen" + 2× MG996R (pan: GPIO12, tilt: GPIO13).
MG996R yük altında 1 A'i aşabilir — servo 5V hattını RPi'den değil ayrı 5V/3A DC-DC'den besleyin, GND ortak.
