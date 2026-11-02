"""
ReSpeaker 2-Mics ile ses dinleme: wake word (openWakeWord) + komut STT (Vosk).
"""
import asyncio
import json
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("robodi.audio.listener")

OWW_FRAME = 1280  # openWakeWord 80 ms @ 16 kHz bekler


class AudioListener:
    def __init__(self, config: dict):
        self.sample_rate    = config.get("sample_rate", 16000)
        self.chunk_size     = config.get("chunk_size", 1024)
        self.ww_model_name  = config.get("wake_word_model", "hey_jarvis")
        self.ww_threshold   = config.get("wake_word_threshold", 0.5)
        self.ww_window      = config.get("wake_word_window", 0.5)   # her çağrıda dinlenecek süre (sn)
        self.vosk_model_dir = config.get("vosk_model", "models/vosk-model-small-tr")
        self.silence_rms    = config.get("silence_rms", 200)

        self._pa = None
        self._device_index = None
        self._ww_stream = None
        self._oww = None
        self._vosk_model = None

        self._init_audio()
        self._init_wake_word()

    # ── Başlatma ────────────────────────────────────────────────

    def _init_audio(self):
        try:
            import pyaudio
            self._pa = pyaudio.PyAudio()
            for i in range(self._pa.get_device_count()):
                info = self._pa.get_device_info_by_index(i)
                if "respeaker" in info["name"].lower() or "seeed" in info["name"].lower():
                    self._device_index = i
                    logger.info(f"ReSpeaker bulundu: device {i}")
                    break
            else:
                logger.warning("ReSpeaker bulunamadı, varsayılan mikrofon kullanılacak.")
        except ImportError:
            logger.warning("PyAudio kurulu değil, simülasyon modunda çalışılıyor.")

    def _init_wake_word(self):
        try:
            import openwakeword
            from openwakeword.model import Model
            try:
                openwakeword.utils.download_models([self.ww_model_name])
            except Exception as e:
                logger.debug(f"openWakeWord model indirme atlandı: {e}")
            self._oww = Model(wakeword_models=[self.ww_model_name], inference_framework="onnx")
            logger.info(f"openWakeWord hazır (model: {self.ww_model_name}).")
        except ImportError:
            logger.error("openwakeword kurulu değil; wake word çalışmayacak.")
        except Exception as e:
            logger.error(f"openWakeWord yüklenemedi: {e}")

    def _open_stream(self, frames: int):
        import pyaudio
        return self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=self._device_index,
            frames_per_buffer=frames,
        )

    def _close_ww_stream(self):
        if self._ww_stream is not None:
            try:
                self._ww_stream.stop_stream()
                self._ww_stream.close()
            except Exception:
                pass
            self._ww_stream = None

    # ── Wake word ───────────────────────────────────────────────

    async def listen_for_wake_word(self) -> bool:
        """
        ~ww_window saniye dinler. True = wake word algılandı.
        Ana döngünün kamerayı da kontrol edebilmesi için kısa pencerelerle çalışır.
        """
        if self._pa is None or self._oww is None:
            await asyncio.sleep(self.ww_window)
            return False
        return await asyncio.get_running_loop().run_in_executor(None, self._detect_wake_word)

    def _detect_wake_word(self) -> bool:
        try:
            if self._ww_stream is None:
                self._ww_stream = self._open_stream(OWW_FRAME)
            n_frames = max(1, int(self.ww_window * self.sample_rate / OWW_FRAME))
            for _ in range(n_frames):
                data = self._ww_stream.read(OWW_FRAME, exception_on_overflow=False)
                scores = self._oww.predict(np.frombuffer(data, dtype=np.int16))
                for name, score in scores.items():
                    if score >= self.ww_threshold:
                        logger.info(f"Wake word '{name}' skor={score:.2f}")
                        self._oww.reset()
                        self._close_ww_stream()   # mikrofonu komut dinlemeye bırak
                        return True
            return False
        except Exception as e:
            logger.error(f"Wake word hatası: {e}")
            self._close_ww_stream()
            return False

    # ── Komut (STT) ─────────────────────────────────────────────

    async def listen_command(self, timeout: float = 8.0) -> Optional[str]:
        """Kullanıcı komutunu al, Vosk ile metne çevir. Döner: metin veya None."""
        if self._pa is None:
            await asyncio.sleep(1)
            return None
        return await asyncio.get_running_loop().run_in_executor(None, self._transcribe, timeout)

    def _transcribe(self, timeout: float) -> Optional[str]:
        stream = None
        try:
            import vosk
            if self._vosk_model is None:
                self._vosk_model = vosk.Model(self.vosk_model_dir)
            rec = vosk.KaldiRecognizer(self._vosk_model, self.sample_rate)

            self._close_ww_stream()
            stream = self._open_stream(self.chunk_size)
            logger.info("Komut dinleniyor...")

            silence_count = 0
            max_silence = int(timeout * self.sample_rate / self.chunk_size)
            while silence_count < max_silence:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    text = json.loads(rec.Result()).get("text", "").strip()
                    if text:
                        return text
                else:
                    audio = np.frombuffer(data, dtype=np.int16).astype(float)
                    rms = np.sqrt(np.mean(audio ** 2))
                    silence_count = silence_count + 1 if rms < self.silence_rms else 0

            text = json.loads(rec.FinalResult()).get("text", "").strip()
            return text or None
        except Exception as e:
            logger.error(f"STT hatası: {e}")
            return None
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()

    def stop(self):
        self._close_ww_stream()
        if self._pa:
            self._pa.terminate()
            self._pa = None
