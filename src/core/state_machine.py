"""ROBODİ Durum Makinesi"""
from enum import Enum, auto
import logging

logger = logging.getLogger("robodi.state")


class RobodiState(Enum):
    IDLE       = auto()   # Bekleme
    LISTENING  = auto()   # Ses dinleme
    PROCESSING = auto()   # Komut işleme
    SPEAKING   = auto()   # Konuşma
    MOVING     = auto()   # Hareket
    ERROR      = auto()   # Hata


# Geçerli state geçişleri
TRANSITIONS = {
    RobodiState.IDLE:       [RobodiState.LISTENING, RobodiState.MOVING],
    RobodiState.LISTENING:  [RobodiState.PROCESSING, RobodiState.IDLE],
    RobodiState.PROCESSING: [RobodiState.SPEAKING, RobodiState.IDLE],
    RobodiState.SPEAKING:   [RobodiState.IDLE, RobodiState.LISTENING],
    RobodiState.MOVING:     [RobodiState.IDLE],
    RobodiState.ERROR:      [RobodiState.IDLE],
}


class StateMachine:
    def __init__(self, initial: RobodiState = RobodiState.IDLE):
        self.current = initial
        logger.info(f"State machine başladı: {initial.name}")

    def transition(self, new_state: RobodiState) -> bool:
        allowed = TRANSITIONS.get(self.current, [])
        if new_state not in allowed:
            logger.warning(
                f"Geçersiz geçiş: {self.current.name} → {new_state.name}"
            )
            return False
        logger.debug(f"State: {self.current.name} → {new_state.name}")
        self.current = new_state
        return True

    def force(self, state: RobodiState):
        """Hata durumunda zorla geçiş."""
        logger.warning(f"Zorla state değişimi: {self.current.name} → {state.name}")
        self.current = state
