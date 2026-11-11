#!/bin/bash
# ROBODİ Kurulum Scripti - Raspberry Pi 5
# Kullanım: ./scripts/setup.sh  (depo içinde herhangi bir yerden çalıştırılabilir)
#
# Python yöntemi: sistem Python'u + pip --break-system-packages.
# venv kullanılmaz; picamera2/libcamera RPi OS'ta sistem paketleriyle gelir.
set -e

# Depo kök dizinine geç (betik scripts/ altında)
ROBODI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROBODI_USER="$(id -un)"
cd "$ROBODI_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ROBODİ Kurulum Scripti"
echo "  Dizin: $ROBODI_DIR  Kullanıcı: $ROBODI_USER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Sistem bağımlılıkları
sudo apt-get update -qq
sudo apt-get install -y \
  python3-pip python3-dev \
  libportaudio2 libportaudio-dev \
  portaudio19-dev \
  mpg123 alsa-utils \
  espeak-ng flac ffmpeg \
  libopenblas-dev \
  python3-opencv python3-picamera2 \
  i2c-tools \
  wget unzip curl

# face_recognition → dlib kaynaktan derlenir (Pi 5'te ~15-30 dk sürebilir)
sudo apt-get install -y \
  cmake build-essential \
  libboost-all-dev

# I2C (PCA9685 servo sürücü + ReSpeaker kodeği) ve SPI (ReSpeaker LED'leri) etkinleştir
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0

# ReSpeaker 2-Mics HAT v2.0 (TLV320AIC3104 kodek) ses kartı: "seeed2micvoicec"
# Sürücü seeed-linux-dtoverlays deposundaki respeaker-2mic-v2_0 overlay'i ile kurulur
# (config.txt: dtparam=i2s=on + dtoverlay=respeaker-2mic-v2_0). Betik config.txt'ye dokunmaz.
if ! aplay -l 2>/dev/null | grep -q seeed2micvoicec; then
  echo "⚠️  ReSpeaker ses kartı (seeed2micvoicec) bulunamadı; respeaker-2mic-v2_0 overlay'ini kurun."
fi

# ESP32 kartlarının USB seri portları, I2C (PCA9685) ve ses kartı erişimi
sudo usermod -aG dialout,i2c,audio,video "$ROBODI_USER"

# Python bağımlılıkları
# openwakeword, Linux'ta tflite-runtime ister; onun Python 3.13 sürümü yok. Robot onnx kullandığı için
# openwakeword bağımlılıkları olmadan kurulur, gerekenler ayrıca yüklenir.
grep -v "^openwakeword" requirements.txt > /tmp/robodi-req.txt
pip install -r /tmp/robodi-req.txt --break-system-packages
pip install --no-deps "openwakeword>=0.6" --break-system-packages
pip install onnxruntime scipy scikit-learn tqdm requests --break-system-packages
python3 -c "import openwakeword.utils as u; u.download_models()" || echo "⚠️  openWakeWord modelleri indirilemedi"

# Vosk Türkçe model indir
mkdir -p models
if [ ! -d "models/vosk-model-small-tr" ]; then
  echo "Vosk Türkçe model indiriliyor..."
  wget -q https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip -O /tmp/vosk-tr.zip
  unzip -q /tmp/vosk-tr.zip -d models/
  mv models/vosk-model-small-tr-0.3 models/vosk-model-small-tr
  rm /tmp/vosk-tr.zip
  echo "Vosk model kuruldu ✓"
fi

# Ollama kur (lokal LLM)
if ! command -v ollama &> /dev/null; then
  echo "Ollama kuruluyor..."
  curl -fsSL https://ollama.com/install.sh | sh
  ollama pull llama3.2:3b
fi

# Kişisel veri, log ve assets klasörleri (data/ git'e girmez)
mkdir -p data logs assets/sounds assets/faces

# .env dosyası
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  .env oluşturuldu, API anahtarlarını girin: nano .env"
fi

# Eski ayrı web servisi varsa kaldır (web paneli artık robodi.service içinde)
sudo systemctl disable --now robodi-web.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/robodi-web.service

# Systemd servis
sudo tee /etc/systemd/system/robodi.service > /dev/null <<EOF
[Unit]
Description=ROBODİ - Masa Arkadaşı Robot
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=$ROBODI_USER
Group=$ROBODI_USER
WorkingDirectory=$ROBODI_DIR
Environment=PYTHONPATH=$ROBODI_DIR
EnvironmentFile=-$ROBODI_DIR/.env
ExecStart=/usr/bin/python3 $ROBODI_DIR/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable robodi

echo ""
echo "✅ Kurulum tamamlandı!"
echo ""
echo "Sonraki adımlar:"
echo "1. nano .env                        → API anahtarlarını girin"
echo "2. python3 -m src.services.gmail    → Gmail yetkisi (bir kez, tarayıcıyla)"
echo "3. sudo systemctl start robodi      → başlat"
echo "4. http://$(hostname -I | cut -d' ' -f1):8080  → web paneli (yüz kaydı)"
