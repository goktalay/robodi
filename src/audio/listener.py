"""
ReSpeaker 2-Mics ile ses dinleme ve wake word algılama.
"""
import asyncio
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("robodi.audio.listener")


class AudioListener:
    def __init__(self, config: dict):
        self.sample_rate   = config.get("sample_rate", 16000)
        self.channels      = config.get("channels", 2)
        self.chunk_size    = config.get("chunk_size", 1024)
        self.vad_threshold = config.get("vad_threshold", 0.5)
        self.wake_word     = config.get("wake_word", "robodi").lower()
        self._stream       = None
        self._running      = False

        self._init_audio()

    def _init_audio(self):
        try:
            import pyaudio
            self._pa = pyaudio.PyAudio()
            # ReSpeaker'ı bul
            for i in range(self._pa.get_device_count()):
                info = self._pa.get_device_info_by_index(i)
                if "respeaker" in info["name"].lower():
                    self._device_index = i
                    logger.info(f"ReSpeaker bulundu: device {i}")
                    break
            else:
                self._device_index = None
                logger.warning("ReSpeaker bulunamadı, varsayılan mikrofon kullanılacak.")
        except ImportError:
            logger.warning("PyAudio kurulu değil, simülasyon modunda çalışılıyor.")
            self._pa = None

    async def listen_for_wake_word(self) -> bool:
        """
        Wake word ('robodi') için dinle.
        Döner: True = wake word algılandı.
        """
        if self._pa is None:
            await asyncio.sleep(1)
            return False

        try:
            import vosk
            # Vosk küçük Türkçe model ile wake word algılama
            # Model: vosk-model-small-tr
            # Gerçek implementasyon burada vosk.KaldiRecognizer kullanır
            # Şimdilik placeholder:
            await asyncio.sleep(0.1)
            return False
        except ImportError:
            await asyncio.sleep(0.1)
            return False

    async def listen_command(self, timeout: float = 8.0) -> Optional[str]:
        """
        Kullanıcı komutunu al, STT ile metne çevir.
        Döner: Tanınan metin veya None.
        """
        if self._pa is None:
            await asyncio.sleep(1)
            return None

        try:
            import vosk, json as _json
            model = vosk.Model("models/vosk-model-small-tr")
            rec   = vosk.KaldiRecognizer(model, self.sample_rate)

            stream = self._pa.open(
                format=self._pa.get_format_from_width(2),
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=self.chunk_size,
            )

            logger.info("Komut dinleniyor...")
            silence_count = 0
            max_silence   = int(timeout * self.sample_rate / self.chunk_size)

            while silence_count < max_silence:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    result = _json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if text:
                        stream.stop_stream()
                        stream.close()
                        return text
                else:
                    # VAD: sessizlik sayacı
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    rms = np.sqrt(np.mean(audio_array.astype(float)**2))
                    if rms < 200:
                        silence_count += 1
                    else:
                        silence_count = 0
                await asyncio.sleep(0)

            stream.stop_stream()
            stream.close()
            return None

        except Exception as e:
            logger.error(f"STT hatası: {e}")
            return None

    def stop(self):
        self._running = False
        if self._pa:
            self._pa.terminate()
