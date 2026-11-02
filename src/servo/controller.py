"""
SG90 Servo Motor Kontrolü - RPi5 GPIO PWM
"""
import asyncio
import logging
from typing import Dict

logger = logging.getLogger("robodi.servo")

# Servo limitleri (derece)
SERVO_LIMITS = {
    "head_pan":   {"min": -90,  "max":  90,  "center":  0},
    "head_tilt":  {"min": -30,  "max":  30,  "center":  0},
    "left_arm":   {"min":   0,  "max": 180,  "center": 90},
    "right_arm":  {"min":   0,  "max": 180,  "center": 90},
}

# PWM: 50 Hz, 1ms=0°, 1.5ms=90°, 2ms=180°
def angle_to_duty(angle_deg: float, min_dc=2.5, max_dc=12.5) -> float:
    """Açıyı duty cycle'a çevir (0-100)."""
    angle_norm = (angle_deg + 90) / 180.0   # 0.0 .. 1.0
    return min_dc + angle_norm * (max_dc - min_dc)


class ServoController:
    def __init__(self, config: dict):
        self.pin_map    = config   # {"head_pan": 12, ...}
        self._positions: Dict[str, float] = {}
        self._pwm       = {}
        self._gpio      = None
        self._init_gpio()

    def _init_gpio(self):
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            for name, pin in self.pin_map.items():
                GPIO.setup(pin, GPIO.OUT)
                pwm = GPIO.PWM(pin, 50)  # 50 Hz
                pwm.start(0)
                self._pwm[name]      = pwm
                self._positions[name] = 0.0

            logger.info(f"GPIO servolar başlatıldı: {list(self.pin_map.keys())}")
        except (ImportError, RuntimeError) as e:
            logger.warning(f"RPi.GPIO kullanılamıyor (PC modu?): {e}")
            for name in self.pin_map:
                self._positions[name] = 0.0

    async def move_to(self, servo: str, angle: float, speed: float = 1.0):
        """Servolu belirli açıya taşı."""
        if servo not in SERVO_LIMITS:
            logger.warning(f"Bilinmeyen servo: {servo}")
            return

        lim   = SERVO_LIMITS[servo]
        angle = max(lim["min"], min(lim["max"], angle))
        start = self._positions.get(servo, lim["center"])
        steps = max(1, int(abs(angle - start) / speed))

        for i in range(steps + 1):
            t = i / steps
            current = start + (angle - start) * t
            self._set_angle(servo, current)
            await asyncio.sleep(0.02)

        self._positions[servo] = angle

    async def move_relative(self, servo: str, delta: float, speed: float = 2.0):
        """Mevcut pozisyona göre görece hareket."""
        current = self._positions.get(servo, 0.0)
        await self.move_to(servo, current + delta, speed)

    async def center_all(self):
        """Tüm servoları merkeze al."""
        tasks = [
            self.move_to(name, lim["center"])
            for name, lim in SERVO_LIMITS.items()
        ]
        await asyncio.gather(*tasks)
        logger.info("Tüm servolar merkeze alındı.")

    def _set_angle(self, servo: str, angle: float):
        if servo in self._pwm:
            dc = angle_to_duty(angle)
            self._pwm[servo].ChangeDutyCycle(dc)
        self._positions[servo] = angle

    def cleanup(self):
        for pwm in self._pwm.values():
            pwm.stop()
        if self._gpio:
            self._gpio.cleanup()
