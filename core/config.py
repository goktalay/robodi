"""
ROBODİ - Merkezi Konfigürasyon
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Wake word
WAKE_WORD = "hey robodi"
WAKE_WORD_SENSITIVITY = 0.5

# Ses ayarları
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024

# Kamera
CAMERA_INDEX = 0
FACE_RECOGNITION_TOLERANCE = 0.5
FACE_ENCODINGS_FILE = BASE_DIR / "data" / "face_encodings.pkl"
AUTHORIZED_USERS_FILE = BASE_DIR / "data" / "authorized_users.json"

# AI Modelleri
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-3-haiku-20240307"
LLAMA_MODEL_PATH = BASE_DIR / "models" / "llama-3.2-3B.gguf"
USE_OFFLINE_FALLBACK = True

# Whisper STT
WHISPER_MODEL = "base"  # tiny, base, small, medium, large
WHISPER_LANGUAGE = "tr"

# TTS
TTS_ENGINE = "pyttsx3"  # pyttsx3 veya elevenlabs
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "your_voice_id"
TTS_RATE = 150  # pyttsx3 için hız

# Gmail
GMAIL_CREDENTIALS_FILE = BASE_DIR / "data" / "gmail_credentials.json"
GMAIL_TOKEN_FILE = BASE_DIR / "data" / "gmail_token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MORNING_SUMMARY_HOUR = 9  # Sabah özeti saati

# ESP32 Bağlantıları
ESP32_EYES_HOST = "192.168.1.101"  # Gözler ESP32 IP
ESP32_MOUTH_HOST = "192.168.1.102"  # Ağız ESP32 IP
ESP32_PORT = 8080

# Web Sunucu
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
WEB_DEBUG = False
SECRET_KEY = os.environ.get("ROBODI_SECRET_KEY", "robodi-secret-2024-change-me")

# Log
LOG_FILE = BASE_DIR / "logs" / "robodi.log"
LOG_LEVEL = "INFO"

# Konuşma hafızası (son N mesaj)
CONVERSATION_HISTORY_SIZE = 10

# Şaka zamanlaması (dakika cinsinden)
JOKE_INTERVAL_MIN = 60
JOKE_INTERVAL_MAX = 120

# Sistem promptu
SYSTEM_PROMPT = """Sen ROBODİ, Muhammed'in masa arkadaşı olan akıllı bir robotsun.
Türkçe konuşuyorsun. Samimi, eğlenceli ve yardımseversin.
Zaman zaman şaka yapıyorsun. Kısa ve öz cevaplar veriyorsun.
Sabahları mail özetleri sunuyorsun. Kullanıcını iyi tanıyorsun."""
