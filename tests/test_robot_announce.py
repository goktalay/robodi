"""
Robotun kendiliğinden konuşma (şaka, sabah özeti) davranışı. Donanım gerekmez.
"""
import asyncio
import logging

import pytest

from src.core.robot import Robodi
from src.core.state_machine import RobodiState

logging.disable(logging.WARNING)


@pytest.fixture
def robot(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = Robodi("config/settings.yaml")
    r.spoken = []

    async def say(text):
        await asyncio.sleep(0.01)
        r.spoken.append(text)

    async def joke():
        return "Şaka metni"

    async def greeting(summary=""):
        return f"Günaydın! {summary}".strip()

    r.speaker.say = say
    r.ai.get_joke = joke
    r.ai.get_morning_greeting = greeting
    return r


def test_saka_bostayken_soylenir(robot):
    assert asyncio.run(robot.tell_joke()) is True
    assert robot.spoken == ["Şaka metni"]
    assert robot.can_announce()


def test_saka_sohbet_sirasinda_soylenmez(robot):
    robot.state.transition(RobodiState.LISTENING)
    assert not robot.can_announce()
    assert asyncio.run(robot.tell_joke()) is False
    assert robot.spoken == []


def test_art_arda_iki_istek_ust_uste_konusmaz(robot):
    async def iki_istek():
        return await asyncio.gather(robot.tell_joke(), robot.tell_joke())
    sonuc = asyncio.run(iki_istek())
    assert sorted(sonuc) == [False, True]
    assert robot.spoken == ["Şaka metni"]


def test_sabah_ozeti_mail_ozetini_ekler(robot, monkeypatch):
    monkeypatch.setattr(robot.gmail, "is_ready", lambda: True)
    monkeypatch.setattr(robot.gmail, "get_summary_text", lambda hours=12: "2 okunmamış mailin var.")
    assert asyncio.run(robot.morning_summary()) is True
    assert robot.spoken == ["Günaydın! 2 okunmamış mailin var."]


def test_sabah_ozeti_gmail_yoksa_sadece_selam(robot):
    assert asyncio.run(robot.morning_summary()) is True
    assert robot.spoken == ["Günaydın!"]
