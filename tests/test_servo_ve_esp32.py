"""
PCA9685 servo sürücü (simülasyon), gövde dönüşü ve ESP32 kart mesajları. Donanım gerekmez.
"""
import asyncio
import logging

import pytest
import yaml

from src.core.esp32_comm import ESP32Comm, expression_messages
from src.core.robot import Robodi
from src.servo.controller import ServoController, physical_angle

logging.disable(logging.WARNING)


@pytest.fixture
def servos():
    with open("config/settings.yaml", encoding="utf-8") as f:
        return ServoController(yaml.safe_load(f)["servos"])


def run(coro):
    return asyncio.run(coro)


# ── Servo sürücü ─────────────────────────────────────────────────

def test_bes_servo_tanimli_ve_merkezde(servos):
    assert set(servos.positions()) == {"head_pan", "head_tilt", "left_arm", "right_arm", "waist"}
    assert servos.position("left_arm") == 90 and servos.position("waist") == 0
    assert servos.mode == "Simülasyon"


def test_aci_sinirlarda_kirpilir(servos):
    run(servos.move_to("head_tilt", 80, speed=20))
    assert servos.position("head_tilt") == 30
    run(servos.move_to("waist", -500, speed=50))
    assert servos.position("waist") == -90


def test_bilinmeyen_servo_yok_sayilir(servos):
    run(servos.move_to("kuyruk", 10))
    assert "kuyruk" not in servos.positions()


@pytest.mark.parametrize("aci, cfg, beklenen", [
    (0,   {"offset": 90}, 90),
    (-90, {"offset": 90}, 0),
    (90,  {"offset": 90}, 180),
    (30,  {"offset": 0},  30),
    (30,  {"offset": 0, "invert": True}, 150),
    (200, {"offset": 0},  180),
])
def test_fiziksel_aci(aci, cfg, beklenen):
    assert physical_angle(aci, cfg) == beklenen


def test_ayar_yoksa_varsayilan_kanallar():
    s = ServoController({})
    assert s.has("waist") and s.limits("head_pan") == (-90, 90)


# ── Gövde dönüşü (kafa → gövde devri) ───────────────────────────

@pytest.fixture
def robot(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return Robodi("config/settings.yaml")


def test_kafa_esigi_gecince_govde_doner_bakis_ayni_kalir(robot):
    robot.servos._positions.update(head_pan=75, waist=0)
    run(robot._waist_handoff())
    assert robot.servos.position("waist") == 75
    assert robot.servos.position("head_pan") == 0


def test_govde_sinirdaysa_sadece_kalan_kadar_doner(robot):
    robot.servos._positions.update(head_pan=-80, waist=-50)
    run(robot._waist_handoff())
    assert robot.servos.position("waist") == -90
    assert robot.servos.position("head_pan") == -40   # bakış -130° olarak korunur


def test_esik_altinda_govde_kipirdamaz(robot):
    robot.servos._positions.update(head_pan=40, waist=10)
    run(robot._waist_handoff())
    assert robot.servos.position("waist") == 10 and robot.servos.position("head_pan") == 40


def test_durum_ozeti_yeni_alanlar(robot):
    st = robot.status()
    assert st["servo_driver"] == "Simülasyon"
    assert st["esp32"] == "Simülasyon"
    assert "waist" in st["servos"] and st["volume"] == 80


# ── ESP32 mesajları ──────────────────────────────────────────────

def test_her_karta_yalniz_kendi_alani():
    m = expression_messages("speaking")
    assert m["eyes"] == {"cmd": "EXPRESSION", "eyes": "happy", "color": [0, 200, 255]}
    assert m["mouth"] == {"cmd": "EXPRESSION", "mouth": "talking", "color": [0, 200, 255]}
    assert m["chest"] == {"cmd": "EXPRESSION", "state": "speaking", "color": [0, 200, 255]}


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.sent = []

    def write(self, data):
        self.sent.append(data.decode())

    def close(self):
        self.is_open = False


def test_ifade_ilgili_kartlara_gider_bagli_olmayan_simule():
    comm = ESP32Comm({"boards": {"eyes": "auto", "mouth": "auto", "chest": "auto"}})
    eyes, mouth = FakeSerial(), FakeSerial()
    comm._serials = {"eyes": eyes, "mouth": mouth}
    run(comm._send_expression("happy"))
    assert eyes.sent == ['{"cmd": "EXPRESSION", "eyes": "happy", "color": [0, 255, 100]}\n']
    assert mouth.sent == ['{"cmd": "EXPRESSION", "mouth": "smile", "color": [0, 255, 100]}\n']
    assert comm.status_text() == "Bağlı: eyes, mouth"


def test_parlaklik_tum_kartlara_ve_sinirli():
    comm = ESP32Comm({})
    cards = {b: FakeSerial() for b in ("eyes", "mouth", "chest")}
    comm._serials = cards
    run(comm.set_brightness(999))
    assert all(c.sent == ['{"cmd": "BRIGHTNESS", "value": 255}\n'] for c in cards.values())
