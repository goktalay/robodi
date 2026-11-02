"""
3.5" TFT SPI Ekran Kontrolü
Yüz ifadesi ve bilgi görüntüleme
"""
import logging
from pathlib import Path

logger = logging.getLogger("robodi.display")

# Yüz ifadesi görüntüleri (PNG)
FACE_IMAGES = {
    "idle":      "assets/faces/idle.png",
    "happy":     "assets/faces/happy.png",
    "sad":       "assets/faces/sad.png",
    "thinking":  "assets/faces/thinking.png",
    "listening": "assets/faces/listening.png",
    "speaking":  "assets/faces/speaking.png",
    "angry":     "assets/faces/angry.png",
    "surprised": "assets/faces/surprised.png",
}


class Display:
    def __init__(self, config: dict):
        self.width    = config.get("width",  480)
        self.height   = config.get("height", 320)
        self.rotation = config.get("rotation", 90)
        self.dc_pin   = config.get("dc_pin",  24)
        self.rst_pin  = config.get("rst_pin", 25)
        self.bl_pin   = config.get("bl_pin",  18)
        self._disp    = None

    async def init(self):
        try:
            import board, busio
            from adafruit_ili9341 import ILI9341
            import digitalio

            spi = busio.SPI(clock=board.SCLK, MOSI=board.MOSI, MISO=board.MISO)
            cs  = digitalio.DigitalInOut(board.CE0)
            dc  = digitalio.DigitalInOut(getattr(board, f"D{self.dc_pin}"))
            rst = digitalio.DigitalInOut(getattr(board, f"D{self.rst_pin}"))

            self._disp = ILI9341(
                spi, cs=cs, dc=dc, rst=rst,
                width=self.width, height=self.height,
                rotation=self.rotation
            )
            logger.info("TFT ekran başlatıldı.")
            self._draw_text("ROBODİ", color=(0, 200, 255))

        except (ImportError, Exception) as e:
            logger.warning(f"TFT kullanılamıyor: {e}")
            self._disp = None

    def show_face(self, expression: str):
        """Yüz ifadesi göster."""
        if expression not in FACE_IMAGES:
            expression = "idle"

        img_path = FACE_IMAGES[expression]
        if self._disp is None:
            logger.debug(f"[SIM DISPLAY] Yüz: {expression}")
            return

        try:
            from PIL import Image
            if Path(img_path).exists():
                img = Image.open(img_path).resize((self.width, self.height))
                self._disp.image(img)
            else:
                self._draw_text(expression.upper())
        except Exception as e:
            logger.error(f"Ekran hata: {e}")

    def show_text(self, text: str, color=(255, 255, 255)):
        if self._disp is None:
            logger.debug(f"[SIM DISPLAY] {text}")
            return
        self._draw_text(text, color)

    def _draw_text(self, text: str, color=(255, 255, 255)):
        try:
            from PIL import Image, ImageDraw, ImageFont
            img  = Image.new("RGB", (self.width, self.height), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((self.width//2, self.height//2), text,
                      fill=color, anchor="mm")
            self._disp.image(img)
        except Exception as e:
            logger.debug(f"Draw hatası: {e}")
