"""
ESP32 ekran kartlarıyla USB seri haberleşme.
Kartlar: eyes (çift yuvarlak göz), mouth (ağız), chest (göğüs ekranı).
Her satır bir JSON komutu; her karta yalnızca kendi alanı gönderilir.
"""
import asyncio
import json
import logging
import time
from typing import Dict, Optional

try:
    import serial
    from serial.tools import list_ports
except ImportError:   # pyserial yoksa simülasyon modu
    serial = None
    list_ports = None

logger = logging.getLogger("robodi.esp32")

BOARDS = ("eyes", "mouth", "chest")

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


def expression_messages(name: str) -> Dict[str, dict]:
    """İfadeyi her kartın kendi EXPRESSION komutuna böl."""
    expr = EXPRESSION_MAP[name]
    return {
        "eyes":  {"cmd": "EXPRESSION", "eyes": expr["eyes"], "color": expr["color"]},
        "mouth": {"cmd": "EXPRESSION", "mouth": expr["mouth"], "color": expr["color"]},
        "chest": {"cmd": "EXPRESSION", "state": name, "color": expr["color"]},
    }


class ESP32Comm:
    def __init__(self, config: dict):
        self.baud = config.get("baud_rate", 115200)
        self.board_ports: Dict[str, str] = {b: "auto" for b in BOARDS}
        self.board_ports.update(config.get("boards") or {})
        self._serials: Dict[str, "serial.Serial"] = {}
        self._lock = asyncio.Lock()
        self._current_expression = "idle"

    # ── Bağlantı ─────────────────────────────────────────────────

    async def connect(self):
        if serial is None:
            logger.warning("pyserial kurulu değil, ESP32 kartları simülasyon modunda.")
            return
        loop = asyncio.get_running_loop()
        self._serials = await loop.run_in_executor(None, self._open_boards)
        missing = [b for b in self.board_ports if b not in self._serials]
        if self._serials:
            logger.info(f"ESP32 kartları bağlı: {sorted(self._serials)}")
        if missing:
            logger.warning(f"ESP32 kartı bulunamadı (simülasyon): {missing}")
        await self._broadcast({"cmd": "INIT", "version": "2.0"})

    def _open_boards(self) -> dict:
        """Sabit portları aç, 'auto' olanları USB portlarında WHO ile bul."""
        found = {}
        for board, port in self.board_ports.items():
            if port and port != "auto":
                ser = self._open(port)
                if ser:
                    found[board] = ser
        wanted = {b for b, p in self.board_ports.items() if p == "auto"}
        if wanted and list_ports is not None:
            used = {s.port for s in found.values()}
            for info in list_ports.comports():
                if not wanted or info.device in used:
                    continue
                if not (info.device.startswith(("/dev/ttyACM", "/dev/ttyUSB")) or info.vid):
                    continue
                ser = self._open(info.device)
                if ser is None:
                    continue
                name = self._who(ser)
                if name in wanted:
                    found[name] = ser
                    wanted.discard(name)
                else:
                    ser.close()
        return found

    def _open(self, port: str):
        try:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = port, self.baud, 0.2
            ser.dtr = ser.rts = False   # açarken kartı sıfırlama
            ser.open()
            return ser
        except (serial.SerialException, OSError) as e:
            logger.debug(f"{port} açılamadı: {e}")
            return None

    @staticmethod
    def _who(ser, timeout: float = 2.0) -> Optional[str]:
        """Karta adını sor; {"board": "..."} cevabını bekle."""
        try:
            ser.reset_input_buffer()
            ser.write(b'{"cmd":"WHO"}\n')
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                line = ser.readline().decode(errors="ignore").strip()
                if line.startswith("{"):
                    try:
                        board = json.loads(line).get("board")
                    except ValueError:
                        continue
                    if board:
                        return board
        except (serial.SerialException, OSError):
            pass
        return None

    async def disconnect(self):
        await self._broadcast({"cmd": "SLEEP"})
        for ser in self._serials.values():
            if ser.is_open:
                ser.close()
        self._serials = {}

    def connected_boards(self) -> list:
        return sorted(b for b, s in self._serials.items() if s.is_open)

    def status_text(self) -> str:
        boards = self.connected_boards()
        return f"Bağlı: {', '.join(boards)}" if boards else "Simülasyon"

    # ── Komutlar ─────────────────────────────────────────────────

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
        for board, msg in expression_messages(name).items():
            await self._send(board, msg)

    async def set_brightness(self, value: int):
        await self._broadcast({"cmd": "BRIGHTNESS", "value": max(0, min(255, int(value)))})

    async def blink(self):
        await self._send("eyes", {"cmd": "BLINK"})

    async def _broadcast(self, data: dict):
        for board in self.board_ports:
            await self._send(board, data)

    async def _send(self, board: str, data: dict):
        ser = self._serials.get(board)
        if ser is None or not ser.is_open:
            logger.debug(f"[SIM] ESP32 {board} → {data}")
            return
        async with self._lock:
            try:
                ser.write((json.dumps(data) + "\n").encode())
            except Exception as e:
                logger.error(f"ESP32 {board} gönderim hatası: {e}")
