#!/bin/bash
# ROBODİ Kurulum Scripti - Raspberry Pi 5

set -e
echo "=== ROBODİ Kurulum Başlıyor ==="

# Sistem güncellemesi
sudo apt update && sudo apt upgrade -y

# Sistem bağımlılıkları
sudo apt install -y \
  python3-pip python3-venv python3-dev \
  cmake build-essential \
  libportaudio2 portaudio19-dev \
  libopencv-dev python3-opencv \
  libboost-all-dev \
  espeak espeak-data \
  flac ffmpeg \
  git

# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate

# Python paketleri
pip install --upgrade pip
pip install -r requirements.txt

# dlib önceden derlenmiş versiyon (Pi için hızlı)
pip install dlib

# Veri klasörleri
mkdir -p data logs models

# .env dosyası
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  .env dosyasını düzenleyin: nano .env"
fi

# Systemd servisleri
sudo cp robodi.service /etc/systemd/system/
sudo cp robodi-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable robodi.service
sudo systemctl enable robodi-web.service

echo ""
echo "=== Kurulum Tamamlandı ==="
echo ""
echo "Sonraki adımlar:"
echo "1. nano .env   → API anahtarlarınızı girin"
echo "2. Gmail kurulumu için: python3 -m core.gmail_reader"
echo "3. Yüz kaydı için web paneli: http://$(hostname -I | cut -d' ' -f1):5000"
echo "4. Başlatmak için: sudo systemctl start robodi"
echo ""
