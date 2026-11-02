"""
ROBODİ - Speech-to-Text (Whisper)
NPU üzerinde offline STT
"""
import logging
import queue
import threading
import numpy as np
import sounddevice as sd
from core.config import SAMPLE_RATE, CHANNELS, WHISPER_MODEL, WHISPER_LANGUAGE

logger = logging.getLogger(__name__)


class SpeechToText:
    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        """Whisper modelini yükle"""
        try:
            import whisper
            logger.info(f"Whisper '{WHISPER_MODEL}' modeli yükleniyor...")
            self.model = whisper.load_model(WHISPER_MODEL)
            logger.info("Whisper hazır")
        except ImportError:
            logger.error("whisper paketi bulunamadı: pip install openai-whisper")
            raise

    def listen(self, duration: float = 5.0, silence_threshold: float = 0.01) -> np.ndarray:
        """
        Mikrofonu dinle, sessizlik algılandığında dur
        Döndürür: ses verisi (numpy array)
        """
        logger.info(f"Dinleniyor... (max {duration}s)")

        audio_chunks = []
        silence_counter = 0
        silence_limit = int(SAMPLE_RATE * 1.0 / 1024)  # 1 saniye sessizlik

        audio_q = queue.Queue()

        def callback(indata, frames, time, status):
            audio_q.put(indata.copy())

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=1024,
            dtype=np.float32,
            callback=callback
        ):
            max_chunks = int(SAMPLE_RATE * duration / 1024)

            for _ in range(max_chunks):
                try:
                    chunk = audio_q.get(timeout=0.5)
                    audio_chunks.append(chunk)

                    # Sessizlik kontrolü
                    rms = np.sqrt(np.mean(chunk ** 2))
                    if rms < silence_threshold:
                        silence_counter += 1
                        if silence_counter >= silence_limit and len(audio_chunks) > 10:
                            logger.debug("Sessizlik algılandı, duruyorum")
                            break
                    else:
                        silence_counter = 0
                except queue.Empty:
                    break

        if not audio_chunks:
            return np.array([])

        return np.concatenate(audio_chunks).flatten()

    def transcribe(self, audio: np.ndarray) -> str:
        """Ses verisini metne çevir"""
        if audio is None or len(audio) == 0:
            return ""

        try:
            result = self.model.transcribe(
                audio,
                language=WHISPER_LANGUAGE,
                fp16=False,
                task="transcribe"
            )
            text = result["text"].strip()
            logger.info(f"Transkripsiyon: '{text}'")
            return text
        except Exception as e:
            logger.error(f"Transkripsiyon hatası: {e}")
            return ""

    def listen_and_transcribe(self, duration: float = 5.0) -> str:
        """Dinle ve metne çevir (tek adım)"""
        audio = self.listen(duration=duration)
        return self.transcribe(audio)
