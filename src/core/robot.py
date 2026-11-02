"""
ROBODİ - Ana Robot Kontrol Modülü
Tüm alt sistemleri yönetir ve koordine eder.
"""
import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

from ..ai.agent import AIAgent
from ..audio.listener import AudioListener
from ..audio.speaker import Speaker
from ..display.screen import Display
from ..servo.controller import ServoController
from ..services.gmail import GmailReader
from ..vision.camera import Camera
from ..vision.face_id import FaceIdentifier
from .esp32_comm import ESP32Comm
from .state_machine import RobodiState, StateMachine

logger = logging.getLogger("robodi.core")

EXIT_WORDS = ("tamam", "görüşürüz", "bay bay", "yeter", "kapat")


class Robodi:
    """ROBODİ ana robot sınıfı."""

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.state = StateMachine(initial=RobodiState.IDLE)
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: list = []
        self._stopped = False

        conv_cfg = self.config.get("conversation", {})
        self.max_turns = conv_cfg.get("max_turns", 5)
        self._turns = 0
        self._last_command = ""
        self._last_response = ""

        vision_cfg = self.config["vision"]
        self.face_id_interval = vision_cfg.get("face_id_interval", 2.0)
        self._last_face_id = 0.0
        self.current_user: Optional[str] = None
        self.current_user_info: dict = {}

        # Alt sistemler
        self.audio    = AudioListener(self.config["audio"])
        self.speaker  = Speaker(self.config["audio"])
        self.camera   = Camera(vision_cfg)
        self.face_id  = FaceIdentifier(vision_cfg.get("face_id", {}))
        self.servos   = ServoController(self.config["gpio"]["servo"])
        self.display  = Display(self.config["display"])
        self.esp32    = ESP32Comm(self.config["esp32"])
        self.ai       = AIAgent(self.config.get("ai", {}))
        self.gmail    = GmailReader(self.config.get("gmail", {}))

        logger.info("ROBODİ sistemi başlatıldı ✓")

    @staticmethod
    def _load_config(path: str) -> dict:
        cfg_file = Path(path)
        if not cfg_file.exists():
            raise FileNotFoundError(f"Config bulunamadı: {path}")
        with open(cfg_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # settings.yaml'da "robodi:" başlığı sadece meta bilgi içeriyor;
        # donanım/ai bölümleri en üst seviyede.
        return data

    # ── Başlatma / Durdurma ──────────────────────────────────────

    async def start(self):
        """Tüm sistemleri başlat."""
        logger.info("ROBODİ başlatılıyor...")
        self.running = True
        self._loop = asyncio.get_running_loop()

        await asyncio.gather(
            self.esp32.connect(),
            self.display.init(),
            self.servos.center_all(),
        )

        self._set_face("happy")
        await self.speaker.say("Merhaba! Ben ROBODİ. Size nasıl yardımcı olabilirim?")
        self._set_face("idle")

        self._tasks = [
            asyncio.create_task(self._morning_summary_loop()),
            asyncio.create_task(self._joke_loop()),
        ]
        await self._main_loop()

    async def stop(self):
        """Sistemleri güvenli şekilde kapat."""
        if self._stopped:
            return
        self._stopped = True
        logger.info("ROBODİ kapatılıyor...")
        self.running = False
        for t in self._tasks:
            t.cancel()
        self._tasks = []
        await self.servos.center_all()
        self.display.show_face("idle")
        await self.esp32.disconnect()
        self.audio.stop()
        self.camera.stop()
        logger.info("ROBODİ kapatıldı.")

    # ── Ana Döngü ────────────────────────────────────────────────

    async def _main_loop(self):
        logger.info("Ana döngü başladı.")
        handlers = {
            RobodiState.IDLE:       self._idle_loop,
            RobodiState.LISTENING:  self._listening_loop,
            RobodiState.PROCESSING: self._processing_loop,
            RobodiState.SPEAKING:   self._speaking_loop,
        }
        while self.running:
            try:
                handler = handlers.get(self.state.current)
                if handler:
                    await handler()
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ana döngü hatası: {e}", exc_info=True)
                self.state.force(RobodiState.IDLE)
                await asyncio.sleep(1)

    async def _idle_loop(self):
        """Bekleme modu: yüz takip/tanıma + wake word."""
        frame = await self.camera.get_frame()
        if frame is not None:
            face = await self.camera.detect_face(frame)
            if face is not None:
                await self._track_face(face)
                await self._maybe_identify(frame)

        if await self.audio.listen_for_wake_word():
            logger.info("Wake word algılandı!")
            await self._greet()
            self._turns = 0
            self.state.transition(RobodiState.LISTENING)

    async def _greet(self):
        self._set_face("surprised")
        if self.current_user and self.face_id.is_authorized(self.current_user):
            text = self.current_user_info.get("greeting", f"Evet, {self.current_user}?")
        else:
            text = "Evet? Sizi tanıyamadım ama yardımcı olmaya çalışacağım."
        await self.speaker.say(text)

    async def _listening_loop(self):
        """Kullanıcı komutunu al."""
        self._set_face("listening")
        await self.speaker.play_sound("beep_start")

        text = await self.audio.listen_command(timeout=8.0)
        if not text:
            logger.info("Komut alınamadı, boşta beklemeye dön.")
            self._end_conversation()
            return

        logger.info(f"Kullanıcı: '{text}'")
        if any(w in text.lower() for w in EXIT_WORDS):
            self._set_face("happy")
            await self.speaker.say("Tamam, görüşürüz!")
            self._end_conversation()
            return

        self._last_command = text
        self.state.transition(RobodiState.PROCESSING)

    async def _processing_loop(self):
        """Komutu işle, yanıt üret."""
        self._set_face("thinking")
        self._last_response = await self.ai.chat(self._last_command)
        self.state.transition(RobodiState.SPEAKING)

    async def _speaking_loop(self):
        """Yanıtı seslendir; tur hakkı varsa dinlemeye devam et."""
        self._set_face("speaking")
        await self.speaker.say(self._last_response)
        self._turns += 1
        if self._turns < self.max_turns:
            self.state.transition(RobodiState.LISTENING)
        else:
            self._end_conversation()

    def _end_conversation(self):
        self._turns = 0
        self._set_face("idle")
        self.state.transition(RobodiState.IDLE)

    def _set_face(self, expression: str):
        self.display.show_face(expression)
        self.esp32.set_expression(expression)

    # ── Panel için durum özeti ───────────────────────────────────

    def status(self) -> dict:
        """Web panelinin gösterdiği alt sistem durumları."""
        cam_mode = getattr(self.camera, "_mode", "sim")
        serial_port = getattr(self.esp32, "_serial", None)
        if getattr(self.ai, "_claude", None):
            ai = f"Claude ({self.ai.claude_model})"
        else:
            ai = f"Ollama ({self.ai.ollama_model})"
        return {
            "state":        self.state.current.name,
            "running":      self.running,
            "current_user": self.current_user_info.get("name") or self.current_user,
            "conversation": self.state.current != RobodiState.IDLE,
            "camera":       {"picamera2": "IMX500", "opencv": "USB/OpenCV"}.get(cam_mode, "Simülasyon"),
            "microphone":   "Hazır" if getattr(self.audio, "_pa", None) else "Simülasyon",
            "wake_word":    self.audio.ww_model_name if getattr(self.audio, "_oww", None) else "Kapalı",
            "esp32":        "Bağlı" if serial_port is not None and serial_port.is_open else "Simülasyon",
            "ai":           ai,
            "gmail":        "Hazır" if self.gmail.is_ready() else "Kapalı",
            "servos":       dict(getattr(self.servos, "_positions", {})),
        }

    # ── Yüz Takip / Tanıma ───────────────────────────────────────

    async def _track_face(self, face_bbox):
        """Kafa servolarını yüze çevir."""
        x, y, w, h = face_bbox
        frame_w, frame_h = self.config["vision"]["resolution"]
        cx = (x + w / 2) / frame_w - 0.5   # -0.5 .. +0.5
        cy = (y + h / 2) / frame_h - 0.5
        if abs(cx) > 0.05:
            await self.servos.move_relative("head_pan",  -cx * 30)
        if abs(cy) > 0.05:
            await self.servos.move_relative("head_tilt",  cy * 20)

    async def _maybe_identify(self, frame):
        now = time.monotonic()
        if now - self._last_face_id < self.face_id_interval:
            return
        self._last_face_id = now
        username, info = await asyncio.get_running_loop().run_in_executor(
            None, self.face_id.identify, frame
        )
        if username and username != self.current_user:
            self.current_user = username
            self.current_user_info = info or {}
            self.ai.set_user(username, self.current_user_info)
            logger.info(f"Kullanıcı tanındı: {username}")

    # ── Zamanlanmış Görevler ─────────────────────────────────────

    async def _announce(self, text_coro):
        """Robot boştaysa kendiliğinden konuş (şaka, sabah özeti)."""
        if self.state.current != RobodiState.IDLE:
            text_coro.close()
            return
        text = await text_coro
        if self.state.current != RobodiState.IDLE:
            return
        self._set_face("happy")
        await self.speaker.say(text)
        self._set_face("idle")

    async def _morning_summary_loop(self):
        hour = self.config.get("schedule", {}).get("morning_summary_hour", 9)
        while self.running:
            now = datetime.now()
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            if not self.current_user:
                logger.info("Sabah özeti atlandı: tanınan kullanıcı yok.")
                continue
            try:
                summary = await asyncio.get_running_loop().run_in_executor(
                    None, self.gmail.get_summary_text, 12
                ) if self.gmail.is_ready() else ""
                await self._announce(self.ai.get_morning_greeting(summary))
            except Exception as e:
                logger.error(f"Sabah özeti hatası: {e}")

    async def _joke_loop(self):
        sched = self.config.get("schedule", {})
        lo = sched.get("joke_interval_min", 60)
        hi = sched.get("joke_interval_max", 120)
        if lo <= 0:
            return  # şakalar kapalı
        while self.running:
            await asyncio.sleep(random.randint(lo, hi) * 60)
            try:
                await self._announce(self.ai.get_joke())
            except Exception as e:
                logger.error(f"Şaka hatası: {e}")
