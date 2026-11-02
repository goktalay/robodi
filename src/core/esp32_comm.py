"""
ESP32-S3 ile UART haberleşme.
Göz LED matrix ve ağız animasyonu kontrolü.
"""
import asyncio
import json
import logging
import serial

logger = logging.getLogger("robodi.esp32")

EXPRESSION_MAP = {
    "idle":      {"eyes": "neutral", "mouth": "flat",    "color": [0, 100, 255]},
    "happy":     {"eyes": "happy",   "mouth": "smile",   "color": [0, 255, 100]},
    "sad":       {"eyes": "sad",     "mouth": "frown",   "color": [100, 100, 255]},
    "angry":     {"eyes": "angry",   "mouth": "frown",   "color": [255, 50, 0]},
    "surprised": {"eyes": "wide",    "mouth": "open",    "color": [255, 200, 0]},
    "thinking":  {"eyes": "squint",  "mouth": "hmm",     "color": [150, 0, 255]},
    "listening": {"eyes": "neutral", "mouth": "flat",    "color": [0, 255, 255]},
    "speaking":  {"eyes": "happy",   "mouth": "talking", "color": [0, 200, 255]},
}


class ESP32Comm:
    def __init__(self, config: dict):
        self.port     = config.get("port", "/dev/ttyAMA0")
        self.baud     = config.get("baud_rate", 115200)
        self._serial: serial.Serial | None = None
        self._lock    = asyncio.Lock()
        self._current_expression = "idle"

    async def connect(self):
        try:
            self._serial = serial.Serial(
                self.port, self.baud, timeout=1
            )
            logger.info(f"ESP32 bağlandı: {self.port} @ {self.baud}")
            await asyncio.sleep(0.5)  # ESP32 boot süresi
            await self._send({"cmd": "INIT", "version": "1.0"})
        except serial.SerialException as e:
            logger.warning(f"ESP32 bağlantısı kurulamadı (simülasyon modu): {e}")
            self._serial = None

    async def disconnect(self):
        if self._serial and self._serial.is_open:
            await self._send({"cmd": "SLEEP"})
            self._serial.close()

    def set_expression(self, name: str):
        """Yüz ifadesi ayarla (non-blocking)."""
        if name not in EXPRESSION_MAP:
            logger.warning(f"Bilinmeyen ifade: {name}")
            return
        if name == self._current_expression:
            return
        self._current_expression = name
        asyncio.create_task(self._send_expression(name))

    async def _send_expression(self, name: str):
        expr = EXPRESSION_MAP[name]
        await self._send({
            "cmd": "EXPRESSION",
            "eyes":  expr["eyes"],
            "mouth": expr["mouth"],
            "color": expr["color"],
        })

    async def _send(self, data: dict):
        if not self._serial or not self._serial.is_open:
            logger.debug(f"[SIM] ESP32 → {data}")
            return
        async with self._lock:
            try:
                msg = json.dumps(data) + "\n"
                self._serial.write(msg.encode())
            except Exception as e:
                logger.error(f"ESP32 gönderim hatası: {e}")
