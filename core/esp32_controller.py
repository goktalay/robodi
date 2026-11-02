"""
ROBODİ - ESP32 Animasyon Kontrolü
Göz (kırpma) ve ağız animasyonlarını WiFi üzerinden kontrol eder
"""
import logging
import socket
import json
import threading
import time
from core.config import ESP32_EYES_HOST, ESP32_MOUTH_HOST, ESP32_PORT

logger = logging.getLogger(__name__)


class ESP32Controller:
    def __init__(self):
        self.eyes_host = ESP32_EYES_HOST
        self.mouth_host = ESP32_MOUTH_HOST
        self.port = ESP32_PORT
        self._blink_thread = None
        self._blink_running = False

    def _send_command(self, host: str, command: dict) -> bool:
        """ESP32'ye JSON komutu gönder"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((host, self.port))
                data = json.dumps(command).encode() + b"\n"
                s.sendall(data)
                return True
        except Exception as e:
            logger.warning(f"ESP32 bağlantı hatası ({host}): {e}")
            return False

    # === GÖZ ANİMASYONLARI ===

    def eyes_idle(self):
        """Gözler normal/bekleme modu"""
        self._send_command(self.eyes_host, {"anim": "idle"})

    def eyes_blink(self):
        """Tek göz kırpma"""
        self._send_command(self.eyes_host, {"anim": "blink"})

    def eyes_happy(self):
        """Mutlu göz ifadesi"""
        self._send_command(self.eyes_host, {"anim": "happy"})

    def eyes_thinking(self):
        """Düşünüyor - dönen animasyon"""
        self._send_command(self.eyes_host, {"anim": "thinking"})

    def eyes_surprised(self):
        """Şaşırmış gözler"""
        self._send_command(self.eyes_host, {"anim": "surprised"})

    def eyes_sleepy(self):
        """Uyukluyor"""
        self._send_command(self.eyes_host, {"anim": "sleepy"})

    def eyes_angry(self):
        """Kızgın"""
        self._send_command(self.eyes_host, {"anim": "angry"})

    def start_auto_blink(self, interval_min: float = 3.0, interval_max: float = 7.0):
        """Otomatik düzenli göz kırpma başlat"""
        import random
        self._blink_running = True

        def _blink_loop():
            while self._blink_running:
                interval = random.uniform(interval_min, interval_max)
                time.sleep(interval)
                if self._blink_running:
                    self.eyes_blink()

        self._blink_thread = threading.Thread(target=_blink_loop, daemon=True)
        self._blink_thread.start()
        logger.info("Otomatik göz kırpma başlatıldı")

    def stop_auto_blink(self):
        self._blink_running = False

    # === AĞIZ ANİMASYONLARI ===

    def mouth_idle(self):
        """Ağız kapalı/nötr"""
        self._send_command(self.mouth_host, {"anim": "idle"})

    def mouth_speaking(self):
        """Konuşuyor animasyonu"""
        self._send_command(self.mouth_host, {"anim": "speaking"})

    def mouth_smile(self):
        """Gülümse"""
        self._send_command(self.mouth_host, {"anim": "smile"})

    def mouth_surprised(self):
        """Şaşırmış ağız"""
        self._send_command(self.mouth_host, {"anim": "surprised"})

    def mouth_thinking(self):
        """Düşünüyor"""
        self._send_command(self.mouth_host, {"anim": "thinking"})

    # === KOMBINASYON DURUMLAR ===

    def state_listening(self):
        """Dinleme durumu"""
        self.eyes_idle()
        self.mouth_idle()

    def state_processing(self):
        """İşleme/düşünme durumu"""
        self.eyes_thinking()
        self.mouth_thinking()

    def state_speaking(self):
        """Konuşma durumu"""
        self.eyes_happy()
        self.mouth_speaking()

    def state_greeting(self):
        """Selamlama"""
        self.eyes_happy()
        self.mouth_smile()

    def state_wake_word(self):
        """Wake word algılandı"""
        self.eyes_surprised()
        self.mouth_idle()

    def state_idle(self):
        """Bekleme modu"""
        self.eyes_idle()
        self.mouth_idle()

    def speak_animation(self, duration: float):
        """Konuşma süresi boyunca ağız animasyonu"""
        self.mouth_speaking()
        time.sleep(duration)
        self.mouth_idle()
