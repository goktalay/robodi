"""
ReSpeaker v2.0 (TLV320AIC3104) 3.5 mm çıkışı → PAM8403 amfi → hoparlörler.
TTS, ses efektleri ve ses seviyesi (amfide düğme yok, ALSA mikserinden).
"""
import asyncio
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("robodi.audio.speaker")

SOUND_EFFECTS = {
    "beep_start":  "assets/sounds/beep_start.wav",
    "beep_end":    "assets/sounds/beep_end.wav",
    "startup":     "assets/sounds/startup.wav",
    "error":       "assets/sounds/error.wav",
}


class Speaker:
    def __init__(self, config: dict):
        self.language   = config.get("language", "tr-TR")
        self.tts_engine = config.get("tts_engine", "pyttsx3")
        self.mixer_card = config.get("mixer_card", "seeed2micvoicec")
        self.mixer_controls = config.get("mixer_controls", ["PCM"])
        self.volume     = int(config.get("volume", 80))
        self._tts       = None
        self._lock      = asyncio.Lock()
        self._init_tts()

    def _init_tts(self):
        if self.tts_engine == "pyttsx3":
            try:
                import pyttsx3
                self._tts = pyttsx3.init()
                self._tts.setProperty("rate", 150)
                self._tts.setProperty("volume", 0.9)
                # Türkçe ses varsa seç
                for voice in self._tts.getProperty("voices"):
                    if "tr" in voice.id.lower():
                        self._tts.setProperty("voice", voice.id)
                        break
                logger.info("pyttsx3 TTS başlatıldı.")
            except Exception as e:
                logger.warning(f"pyttsx3 başlatılamadı: {e}")
                self._tts = None

    async def say(self, text: str):
        """Metni seslendir."""
        async with self._lock:
            logger.info(f"TTS: '{text[:50]}...' " if len(text) > 50 else f"TTS: '{text}'")

            if self.tts_engine == "edge-tts":
                await self._say_edge_tts(text)
            elif self._tts:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._say_pyttsx3, text
                )
            else:
                # Simülasyon: sadece logla
                logger.info(f"[SIM SPEAKER] {text}")
                await asyncio.sleep(len(text) * 0.05)

    def _say_pyttsx3(self, text: str):
        try:
            self._tts.say(text)
            self._tts.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 hata: {e}")

    async def _say_edge_tts(self, text: str):
        """Microsoft Edge TTS (ücretsiz, yüksek kalite)."""
        try:
            import edge_tts
            voice = "tr-TR-AhmetNeural"   # Türkçe erkek sesi
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save("/tmp/robodi_tts.mp3")
            proc = await asyncio.create_subprocess_exec(
                "mpg123", "-q", "/tmp/robodi_tts.mp3"
            )
            await proc.wait()   # konuşma bitmeden dinlemeye geçilmesin
        except Exception as e:
            logger.error(f"Edge TTS hata: {e}")

    async def set_volume(self, percent: int) -> bool:
        """Ses seviyesini ayarla (0-100). amixer yoksa yalnızca değeri saklar."""
        self.volume = max(0, min(100, int(percent)))
        ok = True
        for control in self.mixer_controls:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "amixer", "-q", "-c", self.mixer_card, "sset", control, f"{self.volume}%",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                ok = (await proc.wait()) == 0 and ok
            except (FileNotFoundError, OSError):
                ok = False
        if not ok:
            logger.debug(f"[SIM SPEAKER] Ses seviyesi: %{self.volume}")
        return ok

    async def play_sound(self, name: str):
        """Ses efekti çal."""
        path = SOUND_EFFECTS.get(name)
        if not path or not Path(path).exists():
            logger.debug(f"Ses efekti bulunamadı: {name}")
            return
        try:
            proc = await asyncio.create_subprocess_exec(
                "aplay", "-q", path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception as e:
            logger.error(f"Ses efekti hatası: {e}")
