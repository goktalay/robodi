"""
ROBODİ - Ana Döngü
Tüm sistemleri başlatır ve koordine eder
"""
import logging
import threading
import time
import schedule
from pathlib import Path

# Logging ayarları
from core.config import LOG_FILE, LOG_LEVEL, JOKE_INTERVAL_MIN, JOKE_INTERVAL_MAX

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("robodi.main")

from core.wake_word import WakeWordDetector
from core.face_recognition import FaceRecognizer
from core.stt import SpeechToText
from core.tts import TextToSpeech
from core.ai_agent import AIAgent
from core.gmail_reader import GmailReader
from core.esp32_controller import ESP32Controller
from core.config import FACE_ENCODINGS_FILE, AUTHORIZED_USERS_FILE, MORNING_SUMMARY_HOUR


class Robodi:
    def __init__(self):
        logger.info("=== ROBODİ başlatılıyor ===")

        self.face_rec = FaceRecognizer(FACE_ENCODINGS_FILE, AUTHORIZED_USERS_FILE)
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.ai = AIAgent()
        self.gmail = GmailReader()
        self.esp32 = ESP32Controller()
        self.wake_detector = WakeWordDetector(callback=self._on_wake_word)

        self.is_active = False  # Şu an konuşma var mı
        self.current_user = None
        self._lock = threading.Lock()
        self._setup_scheduler()

        logger.info("ROBODİ hazır!")

    def _setup_scheduler(self):
        """Zamanlanmış görevler"""
        import random

        # Sabah mail özeti
        schedule.every().day.at(f"{MORNING_SUMMARY_HOUR:02d}:00").do(self._morning_summary)

        # Periyodik şakalar
        def schedule_joke():
            wait = random.randint(JOKE_INTERVAL_MIN, JOKE_INTERVAL_MAX) * 60
            timer = threading.Timer(wait, self._tell_joke)
            timer.daemon = True
            timer.start()

        schedule_joke()

    def _on_wake_word(self):
        """Wake word algılandığında çağrılır"""
        with self._lock:
            if self.is_active:
                return
            self.is_active = True

        logger.info("Wake word algılandı!")
        self.esp32.state_wake_word()

        # Kullanıcı yetkisi kontrol et
        user = self.face_rec.current_user
        if user and self.face_rec.is_authorized(user):
            user_info = self.face_rec.authorized_users.get(user, {})
            greeting = user_info.get("greeting", f"Evet, {user}?")
            self._respond(greeting)
        else:
            self._respond("Evet? Sizi tanıyamadım ama yardımcı olmaya çalışacağım.")

        # Kullanıcı sesini dinle
        self._conversation_loop()

    def _conversation_loop(self):
        """Konuşma döngüsü"""
        self.esp32.state_listening()

        max_turns = 5
        for _ in range(max_turns):
            text = self.stt.listen_and_transcribe(duration=6.0)

            if not text:
                self._respond("Sizi duymadım, tekrar eder misiniz?")
                text = self.stt.listen_and_transcribe(duration=6.0)
                if not text:
                    break

            logger.info(f"Kullanıcı: {text}")

            # Çıkış komutları
            exit_words = ["tamam", "görüşürüz", "bay bay", "yeter", "kapat"]
            if any(w in text.lower() for w in exit_words):
                self._respond("Tamam, görüşürüz!")
                break

            # AI yanıtı
            self.esp32.state_processing()
            response = self.ai.chat(text)
            self._respond(response)

            # Devam etmek ister mi?
            self.esp32.state_listening()

        with self._lock:
            self.is_active = False
        self.esp32.state_idle()

    def _respond(self, text: str):
        """Sesli yanıt ver + animasyon"""
        logger.info(f"ROBODİ: {text}")
        self.esp32.state_speaking()
        self.tts.speak(text, blocking=True)
        self.esp32.state_idle()

    def _morning_summary(self):
        """Sabah mail özeti"""
        if not self.current_user:
            return

        logger.info("Sabah özeti hazırlanıyor...")
        email_summary = self.gmail.get_summary_text(hours=12)
        greeting = self.ai.get_morning_greeting(email_summary)
        self._respond(greeting)

    def _tell_joke(self):
        """Şaka yap"""
        if self.is_active:
            return
        joke = self.ai.get_joke()
        self._respond(joke)

        # Sonraki şakayı zamanla
        import random
        wait = random.randint(JOKE_INTERVAL_MIN, JOKE_INTERVAL_MAX) * 60
        timer = threading.Timer(wait, self._tell_joke)
        timer.daemon = True
        timer.start()

    def _on_user_recognized(self, username: str, user_info: dict):
        """Yüz tanıma callback"""
        if username != self.current_user:
            self.current_user = username
            self.ai.set_user(username, user_info)
            logger.info(f"Kullanıcı tanındı: {username}")

    def run(self):
        """Ana çalışma döngüsü"""
        logger.info("ROBODİ çalışıyor...")

        # Yüz tanımayı başlat
        self.face_rec.start_continuous(self._on_user_recognized)

        # Otomatik göz kırpmayı başlat
        self.esp32.start_auto_blink()
        self.esp32.state_idle()

        # Wake word dinleyiciyi başlat
        self.wake_detector.start()

        # Başlangıç mesajı
        self._respond("Merhaba! ROBODİ hazır.")

        # Scheduler döngüsü
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("ROBODİ durduruluyor...")
            self.wake_detector.stop()
            self.face_rec.stop()
            self.esp32.stop_auto_blink()


if __name__ == "__main__":
    robot = Robodi()
    robot.run()
