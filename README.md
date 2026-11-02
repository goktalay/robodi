# 🤖 ROBODİ — Masa Arkadaşı Robot

Raspberry Pi 5 tabanlı, AI destekli akıllı masa robotu.

## Özellikler

- 👁️ **Göz Animasyonları** — ESP32 ekranlarda kırpan, ifadeli gözler
- 👄 **Ağız Animasyonu** — Konuşma sırasında senkronize ağız hareketi
- 🎙️ **Wake Word** — "hey robodi" ile aktifleşme
- 👤 **Yüz Tanıma** — AI Camera ile kullanıcı kimlik doğrulama
- 🧠 **AI Sohbet** — Claude API (online) / Llama 3.2 (offline NPU)
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
git clone https://github.com/mkaderoglu/robodi.git
cd robodi
chmod +x setup.sh
./setup.sh
```

## Yapılandırma

```bash
nano .env
```

Doldurulacak değerler:
- `ANTHROPIC_API_KEY` — Claude API anahtarı
- `ROBODI_ADMIN_PASSWORD` — Web dashboard şifresi
- ESP32 IP adresleri

## Başlatma

```bash
sudo systemctl start robodi
sudo systemctl start robodi-web
```

Web paneli: `http://<raspberry-ip>:5000`

## Proje Yapısı

```
robodi/
├── core/               # Pi 5 ana Python kodu
│   ├── main.py         # Ana döngü
│   ├── wake_word.py    # "hey robodi" algılama
│   ├── face_recognition.py  # Yüz tanıma
│   ├── stt.py          # Konuşmadan metne (Whisper)
│   ├── tts.py          # Metinden konuşmaya
│   ├── ai_agent.py     # Claude / Llama entegrasyonu
│   ├── gmail_reader.py # Gmail API
│   ├── esp32_controller.py  # Animasyon kontrolü
│   └── config.py       # Tüm ayarlar
├── web/                # Flask web dashboard
│   ├── app.py
│   ├── templates/
│   └── static/
├── esp32/
│   ├── eyes/eyes.ino   # Göz animasyon firmware
│   └── mouth/mouth.ino # Ağız animasyon firmware
├── docs/               # Dokümantasyon
├── data/               # Yüz verileri, kullanıcı listesi
├── logs/               # Log dosyaları
└── models/             # Llama model dosyaları
```

## ESP32 Kurulumu

Arduino IDE'de gerekli kütüphaneler:
- `TFT_eSPI` — LCD sürücüsü
- `ArduinoJson` — JSON parse
- WiFi (built-in)

`eyes/eyes.ino` ve `mouth/mouth.ino` dosyalarını ilgili ESP32'lere yükleyin.

## Lisans

MIT License — Muhammed Kaderoğlu

## Kod Yapısı Notu

- `src/` + `main.py` — güncel asyncio tabanlı mimari (durum makinesi, ESP32 UART, Flask kontrol paneli)
- `core/` — önceki iterasyondan kalan modüller (gmail, yüz tanıma, şaka zamanlayıcı); `src/` ile birleştirilecek

## Kafa Pan-Tilt Donanımı

Motorobit "Metal Pan Tilt 2 Eksen" + 2× MG996R (pan: GPIO12, tilt: GPIO13).
MG996R yük altında 1 A'i aşabilir — servo 5V hattını RPi'den değil ayrı 5V/3A DC-DC'den besleyin, GND ortak.
