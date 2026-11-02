"""
ROBODİ - Text-to-Speech Modülü
pyttsx3 (offline) veya ElevenLabs (online)
"""
import logging
import threading
from core.config import TTS_ENGINE, TTS_RATE, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

logger = logging.getLogger(__name__)


class TextToSpeech:
    def __init__(self):
        self.engine_type = TTS_ENGINE
        self._engine = None
        self._lock = threading.Lock()
        self._init_engine()

    def _init_engine(self):
        if self.engine_type == "elevenlabs" and ELEVENLABS_API_KEY:
            self._init_elevenlabs()
        else:
            self._init_pyttsx3()

    def _init_pyttsx3(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", TTS_RATE)
            # Türkçe ses seç (varsa)
            voices = self._engine.getProperty("voices")
            for voice in voices:
                if "tr" in voice.id.lower() or "turkish" in voice.name.lower():
                    self._engine.setProperty("voice", voice.id)
                    logger.info(f"Türkçe ses bulundu: {voice.name}")
                    break
            logger.info("pyttsx3 TTS hazır")
            self.engine_type = "pyttsx3"
        except Exception as e:
            logger.error(f"pyttsx3 başlatılamadı: {e}")
            self._engine = None

    def _init_elevenlabs(self):
        try:
            from elevenlabs.client import ElevenLabs
            self._engine = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            logger.info("ElevenLabs TTS hazır")
            self.engine_type = "elevenlabs"
        except ImportError:
            logger.warning("elevenlabs paketi yok, pyttsx3'e geçiliyor")
            self._init_pyttsx3()

    def speak(self, text: str, blocking: bool = True):
        """Metni seslendir"""
        if not text:
            return

        logger.info(f"TTS: '{text[:50]}...' " if len(text) > 50 else f"TTS: '{text}'")

        if blocking:
            self._speak_sync(text)
        else:
            t = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
            t.start()

    def _speak_sync(self, text: str):
        with self._lock:
            if self.engine_type == "elevenlabs":
                self._speak_elevenlabs(text)
            elif self.engine_type == "pyttsx3":
                self._speak_pyttsx3(text)
            else:
                logger.error("TTS motoru başlatılmadı")

    def _speak_pyttsx3(self, text: str):
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 hatası: {e}")

    def _speak_elevenlabs(self, text: str):
        try:
            import pygame
            import io

            audio = self._engine.text_to_speech.convert(
                text=text,
                voice_id=ELEVENLABS_VOICE_ID,
                model_id="eleven_multilingual_v2"
            )

            audio_data = b"".join(audio)

            pygame.mixer.init()
            sound = pygame.mixer.Sound(io.BytesIO(audio_data))
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(100)
        except Exception as e:
            logger.error(f"ElevenLabs hatası: {e}")
            self._speak_pyttsx3(text)  # fallback

    def stop(self):
        if self.engine_type == "pyttsx3" and self._engine:
            self._engine.stop()
