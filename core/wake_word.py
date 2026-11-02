"""
ROBODİ - Wake Word Algılama
"hey robodi" sesini dinler
"""
import logging
import threading
import queue
import numpy as np
import sounddevice as sd
from core.config import WAKE_WORD, WAKE_WORD_SENSITIVITY, SAMPLE_RATE, CHANNELS, CHUNK_SIZE

logger = logging.getLogger(__name__)


class WakeWordDetector:
    def __init__(self, callback):
        self.callback = callback  # wake word algılandığında çağrılır
        self.is_running = False
        self.audio_queue = queue.Queue()
        self._thread = None
        self._init_detector()

    def _init_detector(self):
        """openWakeWord modelini yükle"""
        try:
            import openwakeword
            from openwakeword.model import Model
            # Özel "hey robodi" modeli veya en yakın model
            self.model = Model(
                wakeword_models=["hey_jarvis"],  # Başlangıç için; özel model eklenecek
                inference_framework="onnx"
            )
            self.use_oww = True
            logger.info("openWakeWord yüklendi")
        except ImportError:
            logger.warning("openWakeWord bulunamadı, pocketsphinx deneniyor...")
            self._init_pocketsphinx()

    def _init_pocketsphinx(self):
        """Fallback: pocketsphinx"""
        try:
            from pocketsphinx import LiveSpeech
            self.use_oww = False
            logger.info("pocketsphinx yüklendi")
        except ImportError:
            logger.error("Ne openWakeWord ne de pocketsphinx bulunamadı!")
            self.use_oww = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            logger.warning(f"Ses durumu: {status}")
        self.audio_queue.put(indata.copy())

    def _detection_loop(self):
        """Sürekli dinleme döngüsü"""
        logger.info(f"'{WAKE_WORD}' bekleniyor...")
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=CHUNK_SIZE,
            dtype=np.int16,
            callback=self._audio_callback
        ):
            while self.is_running:
                if self.use_oww:
                    self._detect_oww()
                else:
                    self._detect_pocketsphinx()

    def _detect_oww(self):
        """openWakeWord ile algılama"""
        try:
            audio_chunk = self.audio_queue.get(timeout=0.1)
            audio_array = audio_chunk.flatten()
            prediction = self.model.predict(audio_array)

            for wake_word, score in prediction.items():
                if score >= WAKE_WORD_SENSITIVITY:
                    logger.info(f"Wake word algılandı! Skor: {score:.2f}")
                    self.callback()
                    # Buffer temizle
                    while not self.audio_queue.empty():
                        self.audio_queue.get()
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Wake word algılama hatası: {e}")

    def _detect_pocketsphinx(self):
        """Basit keyword spotting fallback"""
        try:
            # pocketsphinx implementasyonu
            pass
        except Exception as e:
            logger.error(f"pocketsphinx hatası: {e}")

    def start(self):
        self.is_running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()
        logger.info("Wake word detector başlatıldı")

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Wake word detector durduruldu")
