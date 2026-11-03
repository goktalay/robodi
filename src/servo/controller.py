"""
Servo kontrolü - PCA9685 16 kanal sürücü (I2C) üzerinden MG996R servolar.
Kafa (yatay/dikey), kollar ve gövde dönüşü. Sürücü yoksa simülasyon.
"""
import asyncio
import logging
from typing import Dict

logger = logging.getLogger("robodi.servo")

# Ayar dosyasında kanal yoksa kullanılan varsayılanlar
DEFAULT_CHANNELS = {
    "head_pan":  {"channel": 0, "min": -90, "max":  90, "center":  0, "offset": 90},
    "head_tilt": {"channel": 1, "min": -30, "max":  30, "center":  0, "offset": 90},
    "left_arm":  {"channel": 2, "min":   0, "max": 180, "center": 90, "offset":  0},
    "right_arm": {"channel": 3, "min":   0, "max": 180, "center": 90, "offset":  0},
    "waist":     {"channel": 4, "min": -90, "max":  90, "center":  0, "offset": 90},
}
DEFAULT_PULSE = (500, 2500)   # µs, 0°..180°


def physical_angle(angle: float, cfg: dict) -> float:
    """Yazılım açısını servonun 0..180° fiziksel açısına çevir."""
    phys = angle + cfg.get("offset", 0)
    if cfg.get("invert", False):
        phys = 180 - phys
    return max(0.0, min(180.0, phys))


class ServoController:
    def __init__(self, config: dict):
        config = config or {}
        self.channels: Dict[str, dict] = config.get("channels") or DEFAULT_CHANNELS
        self.address   = config.get("i2c_address", 0x40)
        self.frequency = config.get("frequency", 50)
        self._positions: Dict[str, float] = {
            name: float(cfg.get("center", 0)) for name, cfg in self.channels.items()
        }
        self._kit = None
        self._init_driver()

    def _init_driver(self):
        try:
            from adafruit_servokit import ServoKit
            self._kit = ServoKit(channels=16, address=self.address, frequency=self.frequency)
            for cfg in self.channels.values():
                lo, hi = cfg.get("min_pulse", DEFAULT_PULSE[0]), cfg.get("max_pulse", DEFAULT_PULSE[1])
                self._kit.servo[cfg["channel"]].set_pulse_width_range(lo, hi)
                self._kit.servo[cfg["channel"]].actuation_range = 180
            logger.info(f"PCA9685 servolar başlatıldı (0x{self.address:02X}): {list(self.channels)}")
        except (ImportError, OSError, ValueError, RuntimeError) as e:
            logger.warning(f"PCA9685 kullanılamıyor, servo simülasyon modunda: {e}")
            self._kit = None

    # ── Sorgular ─────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return "PCA9685" if self._kit else "Simülasyon"

    def has(self, servo: str) -> bool:
        return servo in self.channels

    def position(self, servo: str) -> float:
        return self._positions.get(servo, 0.0)

    def positions(self) -> Dict[str, float]:
        return dict(self._positions)

    def limits(self, servo: str) -> tuple:
        cfg = self.channels[servo]
        return cfg["min"], cfg["max"]

    # ── Hareket ──────────────────────────────────────────────────

    async def move_to(self, servo: str, angle: float, speed: float = 1.0):
        """Servoyu belirli açıya yumuşakça taşı (speed: adım başına derece, adım 20 ms)."""
        if servo not in self.channels:
            logger.warning(f"Bilinmeyen servo: {servo}")
            return
        lo, hi = self.limits(servo)
        angle = max(lo, min(hi, angle))
        start = self._positions.get(servo, self.channels[servo].get("center", 0))
        steps = max(1, int(abs(angle - start) / speed))

        for i in range(1, steps + 1):
            self._set_angle(servo, start + (angle - start) * i / steps)
            await asyncio.sleep(0.02)

    async def move_relative(self, servo: str, delta: float, speed: float = 2.0):
        """Mevcut pozisyona göre görece hareket."""
        await self.move_to(servo, self.position(servo) + delta, speed)

    async def center_all(self):
        """Tüm servoları merkeze al."""
        await asyncio.gather(*(
            self.move_to(name, cfg.get("center", 0)) for name, cfg in self.channels.items()
        ))
        logger.info("Tüm servolar merkeze alındı.")

    def _set_angle(self, servo: str, angle: float):
        cfg = self.channels[servo]
        if self._kit:
            self._kit.servo[cfg["channel"]].angle = physical_angle(angle, cfg)
        self._positions[servo] = angle

    def cleanup(self):
        """Servoları serbest bırak (darbe gönderimini kes)."""
        if not self._kit:
            return
        for cfg in self.channels.values():
            self._kit.servo[cfg["channel"]].angle = None
