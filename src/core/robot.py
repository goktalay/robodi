"""
ROBODİ - Ana Robot Kontrol Modülü
Tüm alt sistemleri yönetir ve koordine eder.
"""
import asyncio
import logging
import yaml
from pathlib import Path
from typing import Optional

from ..audio.listener import AudioListener
from ..audio.speaker import Speaker
from ..vision.camera import Camera
from ..servo.controller import ServoController
from ..display.screen import Display
from .state_machine import RobodiState, StateMachine
from .esp32_comm import ESP32Comm

logger = logging.getLogger("robodi.core")


class Robodi:
    """ROBODİ ana robot sınıfı."""

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = self._load_config(config_path)
        self.state = StateMachine(initial=RobodiState.IDLE)
        self.running = False

        # Alt sistemler
        self.audio    = AudioListener(self.config["audio"])
        self.speaker  = Speaker(self.config["audio"])
        self.camera   = Camera(self.config["vision"])
        self.servos   = ServoController(self.config["gpio"]["servo"])
        self.display  = Display(self.config["display"])
        self.esp32    = ESP32Comm(self.config["esp32"])

        logger.info("ROBODİ sistemi başlatıldı ✓")

    def _load_config(self, path: str) -> dict:
        cfg_file = Path(path)
        if not cfg_file.exists():
            raise FileNotFoundError(f"Config bulunamadı: {path}")
        with open(cfg_file) as f:
            data = yaml.safe_load(f)
        return data.get("robodi", data)

    # ── Başlatma / Durdurma ──────────────────────────────────────

    async def start(self):
        """Tüm sistemleri başlat."""
        logger.info("ROBODİ başlatılıyor...")
        self.running = True

        await asyncio.gather(
            self.esp32.connect(),
            self.display.init(),
            self.servos.center_all(),
        )

        self.display.show_face("idle")
        await self.speaker.say("Merhaba! Ben ROBODİ. Size nasıl yardımcı olabilirim?")
        self.state.transition(RobodiState.IDLE)

        # Ana döngüyü başlat
        await self._main_loop()

    async def stop(self):
        """Sistemleri güvenli şekilde kapat."""
        logger.info("ROBODİ kapatılıyor...")
        self.running = False
        await self.servos.center_all()
        self.display.show_face("idle")
        await self.esp32.disconnect()
        self.audio.stop()
        logger.info("ROBODİ kapatıldı.")

    # ── Ana Döngü ────────────────────────────────────────────────

    async def _main_loop(self):
        """Ana kontrol döngüsü."""
        logger.info("Ana döngü başladı.")

        while self.running:
            try:
                current = self.state.current

                if current == RobodiState.IDLE:
                    await self._idle_loop()

                elif current == RobodiState.LISTENING:
                    await self._listening_loop()

                elif current == RobodiState.PROCESSING:
                    await self._processing_loop()

                elif current == RobodiState.SPEAKING:
                    await self._speaking_loop()

                await asyncio.sleep(0.05)  # 20 Hz döngü

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ana döngü hatası: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _idle_loop(self):
        """Bekleme modu - wake word dinle, yüz tanı."""
        # Kamerada yüz var mı?
        face = await self.camera.detect_face()
        if face:
            await self._track_face(face)
            self.esp32.set_expression("idle")

        # Ses dinle (wake word)
        detected = await self.audio.listen_for_wake_word()
        if detected:
            logger.info("Wake word algılandı!")
            self.state.transition(RobodiState.LISTENING)

    async def _listening_loop(self):
        """Kullanıcı komutunu al."""
        self.display.show_face("listening")
        self.esp32.set_expression("listening")
        await self.speaker.play_sound("beep_start")

        text = await self.audio.listen_command(timeout=8.0)

        if text:
            logger.info(f"Komut alındı: '{text}'")
            self._last_command = text
            self.state.transition(RobodiState.PROCESSING)
        else:
            logger.info("Komut alınamadı, boşta beklemeye dön.")
            self.state.transition(RobodiState.IDLE)

    async def _processing_loop(self):
        """Komutu işle, yanıt üret."""
        self.display.show_face("thinking")
        self.esp32.set_expression("thinking")

        response = await self._get_ai_response(self._last_command)
        self._last_response = response
        self.state.transition(RobodiState.SPEAKING)

    async def _speaking_loop(self):
        """Yanıtı seslendir ve yüz animasyonu oynat."""
        self.display.show_face("speaking")
        self.esp32.set_expression("happy")

        await self.speaker.say(self._last_response)

        self.state.transition(RobodiState.IDLE)

    # ── Yüz Takip ───────────────────────────────────────────────

    async def _track_face(self, face_bbox: tuple):
        """Kafa servolarını yüze çevir."""
        x, y, w, h = face_bbox
        frame_w, frame_h = self.config["vision"]["resolution"]

        # Merkez offset
        cx = (x + w / 2) / frame_w - 0.5   # -0.5 .. +0.5
        cy = (y + h / 2) / frame_h - 0.5

        # Servo açısına çevir (deadband uygula)
        if abs(cx) > 0.05:
            await self.servos.move_relative("head_pan",  -cx * 30)
        if abs(cy) > 0.05:
            await self.servos.move_relative("head_tilt",  cy * 20)

    # ── AI Yanıt ────────────────────────────────────────────────

    async def _get_ai_response(self, text: str) -> str:
        """LLM'den yanıt al (Ollama veya OpenAI)."""
        try:
            import httpx
            ai_cfg = self.config.get("ai", {})
            provider = ai_cfg.get("provider", "ollama")

            if provider == "ollama":
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": ai_cfg.get("model", "llama3.2:3b"),
                            "prompt": f"{ai_cfg.get('system_prompt','')}\n\nKullanıcı: {text}\nROBODİ:",
                            "stream": False,
                            "options": {
                                "temperature": ai_cfg.get("temperature", 0.7),
                                "num_predict": ai_cfg.get("max_tokens", 256),
                            }
                        }
                    )
                    data = resp.json()
                    return data.get("response", "Anlayamadım, tekrar söyler misiniz?").strip()

        except Exception as e:
            logger.error(f"AI yanıt hatası: {e}")
            return "Şu an düşünemiyorum, biraz sonra tekrar deneyin."
