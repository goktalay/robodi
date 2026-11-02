"""
ROBODİ - Yüz Tanıma (kimlik)
Camera'dan gelen karelerle çalışır; kendi kamerasını açmaz.
"""
import json
import logging
import pickle
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("robodi.vision.face_id")

DEFAULT_USERS = {
    "admin": {
        "name": "Muhammed",
        "role": "admin",
        "greeting": "Merhaba Muhammed! Nasılsın?",
    }
}


class FaceIdentifier:
    def __init__(self, config: dict):
        self.encodings_file = Path(config.get("encodings_file", "data/face_encodings.pkl"))
        self.users_file     = Path(config.get("users_file", "data/authorized_users.json"))
        self.tolerance      = config.get("tolerance", 0.5)
        self.scale          = config.get("scale", 0.25)   # HOG hızı için küçültme
        self.known_encodings: list = []
        self.known_names: list = []
        self.authorized_users: dict = {}

        try:
            import face_recognition  # noqa: F401
            self.available = True
        except ImportError:
            logger.warning("face_recognition kurulu değil, kimlik tanıma kapalı.")
            self.available = False

        self._load_encodings()
        self._load_users()

    # ── Kalıcı veri ─────────────────────────────────────────────

    def _load_encodings(self):
        if self.encodings_file.exists():
            with open(self.encodings_file, "rb") as f:
                data = pickle.load(f)
            self.known_encodings = data.get("encodings", [])
            self.known_names     = data.get("names", [])
            logger.info(f"{len(self.known_names)} yüz yüklendi: {self.known_names}")
        else:
            logger.warning(f"Yüz verisi yok: {self.encodings_file}")

    def _load_users(self):
        if self.users_file.exists():
            with open(self.users_file, encoding="utf-8") as f:
                self.authorized_users = json.load(f)
        else:
            self.authorized_users = dict(DEFAULT_USERS)
            self._save_users()

    def _save_users(self):
        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(self.authorized_users, f, ensure_ascii=False, indent=2)

    def _save_encodings(self):
        self.encodings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.encodings_file, "wb") as f:
            pickle.dump({"encodings": self.known_encodings, "names": self.known_names}, f)

    # ── Kullanıcı yönetimi ──────────────────────────────────────

    def add_user(self, username: str, user_info: dict, frames: list) -> bool:
        """BGR karelerden yüz kaydı oluştur."""
        if not self.available:
            return False
        import face_recognition as fr

        encodings = []
        for frame in frames:
            rgb = np.ascontiguousarray(frame[:, :, ::-1])
            locations = fr.face_locations(rgb, model="hog")
            if locations:
                encodings.append(fr.face_encodings(rgb, locations)[0])

        if not encodings:
            logger.error("Kayıt için yüz bulunamadı.")
            return False

        self.known_encodings.append(np.mean(encodings, axis=0))
        self.known_names.append(username)
        self.authorized_users[username] = user_info
        self._save_encodings()
        self._save_users()
        logger.info(f"Kullanıcı eklendi: {username}")
        return True

    def remove_user(self, username: str) -> bool:
        if username not in self.authorized_users or username == "admin":
            return False
        for i in sorted((i for i, n in enumerate(self.known_names) if n == username), reverse=True):
            self.known_encodings.pop(i)
            self.known_names.pop(i)
        del self.authorized_users[username]
        self._save_encodings()
        self._save_users()
        logger.info(f"Kullanıcı silindi: {username}")
        return True

    def is_authorized(self, username: Optional[str]) -> bool:
        return username in self.authorized_users

    # ── Tanıma ──────────────────────────────────────────────────

    def identify(self, frame) -> Tuple[Optional[str], Optional[dict]]:
        """BGR karede yetkili kullanıcıyı bul. Bloklayıcı; executor'da çağırın."""
        if not self.available or frame is None or not self.known_encodings:
            return None, None
        try:
            import cv2
            import face_recognition as fr

            small = cv2.resize(frame, (0, 0), fx=self.scale, fy=self.scale)
            rgb = np.ascontiguousarray(small[:, :, ::-1])
            locations = fr.face_locations(rgb, model="hog")
            for encoding in fr.face_encodings(rgb, locations):
                distances = fr.face_distance(self.known_encodings, encoding)
                best = int(np.argmin(distances))
                if distances[best] <= self.tolerance:
                    name = self.known_names[best]
                    if name in self.authorized_users:
                        return name, self.authorized_users[name]
        except Exception as e:
            logger.error(f"Yüz tanıma hatası: {e}")
        return None, None
