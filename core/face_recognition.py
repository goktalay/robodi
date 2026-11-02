"""
ROBODİ - Yüz Tanıma Modülü
AI Camera (Sony IMX500) veya normal kamera ile çalışır
"""
import logging
import pickle
import json
import threading
import time
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


class FaceRecognizer:
    def __init__(self, encodings_file, authorized_users_file):
        self.encodings_file = Path(encodings_file)
        self.authorized_users_file = Path(authorized_users_file)
        self.known_encodings = []
        self.known_names = []
        self.authorized_users = {}
        self.current_user = None
        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()

        self._load_encodings()
        self._load_authorized_users()

    def _load_encodings(self):
        """Kayıtlı yüz verilerini yükle"""
        if self.encodings_file.exists():
            with open(self.encodings_file, "rb") as f:
                data = pickle.load(f)
                self.known_encodings = data.get("encodings", [])
                self.known_names = data.get("names", [])
            logger.info(f"{len(self.known_names)} yüz yüklendi: {self.known_names}")
        else:
            logger.warning("Yüz verisi bulunamadı, yeni oluşturulacak")
            self.encodings_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_authorized_users(self):
        """Yetkili kullanıcı listesini yükle"""
        if self.authorized_users_file.exists():
            with open(self.authorized_users_file, "r", encoding="utf-8") as f:
                self.authorized_users = json.load(f)
        else:
            # Varsayılan admin kullanıcısı
            self.authorized_users = {
                "admin": {
                    "name": "Muhammed",
                    "role": "admin",
                    "greeting": "Merhaba Muhammed! Nasılsın?"
                }
            }
            self._save_authorized_users()

    def _save_authorized_users(self):
        """Yetkili kullanıcıları kaydet"""
        self.authorized_users_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.authorized_users_file, "w", encoding="utf-8") as f:
            json.dump(self.authorized_users, f, ensure_ascii=False, indent=2)

    def save_encodings(self):
        """Yüz verilerini diske kaydet"""
        data = {
            "encodings": self.known_encodings,
            "names": self.known_names
        }
        with open(self.encodings_file, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"Yüz verileri kaydedildi: {len(self.known_names)} kişi")

    def add_user(self, username: str, user_info: dict, frames: list):
        """Yeni kullanıcı ekle ve yüzünü kaydet"""
        import face_recognition as fr

        encodings = []
        for frame in frames:
            rgb_frame = frame[:, :, ::-1]  # BGR -> RGB
            face_locations = fr.face_locations(rgb_frame, model="hog")
            if face_locations:
                encoding = fr.face_encodings(rgb_frame, face_locations)[0]
                encodings.append(encoding)

        if not encodings:
            logger.error("Yüz tespit edilemedi!")
            return False

        avg_encoding = np.mean(encodings, axis=0)
        self.known_encodings.append(avg_encoding)
        self.known_names.append(username)
        self.authorized_users[username] = user_info

        self.save_encodings()
        self._save_authorized_users()
        logger.info(f"Kullanıcı eklendi: {username}")
        return True

    def remove_user(self, username: str):
        """Kullanıcıyı sil"""
        if username not in self.authorized_users:
            return False
        if username == "admin":
            logger.warning("Admin silinemez!")
            return False

        indices = [i for i, n in enumerate(self.known_names) if n == username]
        for i in sorted(indices, reverse=True):
            self.known_encodings.pop(i)
            self.known_names.pop(i)

        del self.authorized_users[username]
        self.save_encodings()
        self._save_authorized_users()
        logger.info(f"Kullanıcı silindi: {username}")
        return True

    def recognize_face(self, frame) -> tuple:
        """Tek bir karede yüz tanı. Döndürür: (username, user_info) veya (None, None)"""
        try:
            import face_recognition as fr
            rgb_frame = frame[:, :, ::-1]
            face_locations = fr.face_locations(rgb_frame, model="hog")

            if not face_locations:
                return None, None

            face_encodings = fr.face_encodings(rgb_frame, face_locations)

            for encoding in face_encodings:
                from core.config import FACE_RECOGNITION_TOLERANCE
                matches = fr.compare_faces(
                    self.known_encodings, encoding,
                    tolerance=FACE_RECOGNITION_TOLERANCE
                )

                if any(matches):
                    distances = fr.face_distance(self.known_encodings, encoding)
                    best_idx = np.argmin(distances)
                    username = self.known_names[best_idx]

                    if username in self.authorized_users:
                        return username, self.authorized_users[username]

            return None, None
        except Exception as e:
            logger.error(f"Yüz tanıma hatası: {e}")
            return None, None

    def start_continuous(self, callback):
        """Sürekli kamera taraması başlat"""
        import cv2
        self.is_running = True

        def _loop():
            cap = cv2.VideoCapture(0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            last_recognition = 0
            recognition_interval = 2.0  # Her 2 saniyede bir tara

            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                now = time.time()
                if now - last_recognition >= recognition_interval:
                    username, user_info = self.recognize_face(frame)
                    last_recognition = now

                    if username and username != self.current_user:
                        with self._lock:
                            self.current_user = username
                        callback(username, user_info)

                time.sleep(0.033)  # ~30 FPS

            cap.release()

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False

    def get_authorized_users(self):
        return dict(self.authorized_users)

    def is_authorized(self, username: str) -> bool:
        return username in self.authorized_users
