#!/bin/bash
# ROBODİ Kurulum Scripti - Raspberry Pi 5
set -e
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ROBODİ Kurulum Scripti"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Sistem bağımlılıkları
sudo apt-get update -qq
sudo apt-get install -y \
  python3-pip python3-venv \
  libportaudio2 libportaudio-dev \
  portaudio19-dev \
  mpg123 alsa-utils \
  libatlas-base-dev \
  libopenblas-dev \
  python3-opencv \
  i2c-tools \
  libgpiod2

# SPI ve UART etkinleştir
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_serial_hw 0
sudo raspi-config nonint do_serial_cons 1

# Python bağımlılıkları
pip install -r requirements.txt --break-system-packages

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

# Log ve assets klasörleri
mkdir -p logs assets/sounds assets/faces

# Systemd servis
sudo tee /etc/systemd/system/robodi.service > /dev/null <<EOF
[Unit]
Description=ROBODİ Robot Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/robodi/main.py
WorkingDirectory=/home/pi/robodi
Restart=on-failure
User=pi
Environment=PYTHONPATH=/home/pi/robodi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable robodi

echo ""
echo "✅ Kurulum tamamlandı!"
echo "Başlatmak için: sudo systemctl start robodi"
echo "Web arayüzü:    http://$(hostname -I | cut -d' ' -f1):8080"
