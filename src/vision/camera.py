"""
IMX500 AI Kamera - Yüz tanıma ve nesne algılama
"""
import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger("robodi.vision")


class Camera:
    def __init__(self, config: dict):
        self.resolution = config.get("resolution", [1920, 1080])
        self.fps        = config.get("fps", 30)
        self.confidence = config.get("detection_confidence", 0.6)
        self._cap       = None
        self._face_cascade = None
        self._init()

    def _init(self):
        try:
            import cv2
            # IMX500 önce Picamera2 ile dene
            try:
                from picamera2 import Picamera2
                self._picam = Picamera2()
                cfg = self._picam.create_preview_configuration(
                    # RGB888 → numpy'da BGR, 3 kanal (OpenCV ile uyumlu)
                    main={"size": tuple(self.resolution), "format": "RGB888"}
                )
                self._picam.configure(cfg)
                self._picam.start()
                self._mode = "picamera2"
                logger.info("IMX500 Picamera2 ile başlatıldı.")
            except Exception:
                # Fallback: USB kamera / V4L2
                self._cap = cv2.VideoCapture(0)
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.resolution[0])
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self._mode = "opencv"
                logger.info("Kamera OpenCV ile başlatıldı.")

            # Yüz tanıma (Haar Cascade - hafif)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
            self._cv2 = cv2

        except ImportError:
            logger.warning("OpenCV kurulu değil, simülasyon modu.")
            self._mode = "sim"

    async def get_frame(self):
        """Kameradan bir kare al."""
        if self._mode == "sim":
            return None
        return await asyncio.get_event_loop().run_in_executor(
            None, self._read_frame
        )

    def _read_frame(self):
        if self._mode == "picamera2":
            import numpy as np
            return self._picam.capture_array()
        elif self._cap:
            ret, frame = self._cap.read()
            return frame if ret else None
        return None

    async def detect_face(self, frame=None) -> Optional[Tuple[int,int,int,int]]:
        """
        Karede yüz algıla (frame verilmezse kameradan alınır).
        Döner: (x, y, w, h) veya None
        """
        if frame is None:
            frame = await self.get_frame()
        if frame is None:
            return None
        return await asyncio.get_event_loop().run_in_executor(
            None, self._find_face, frame
        )

    def _find_face(self, frame):
        if self._face_cascade is None:
            return None
        gray  = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )
        if len(faces) == 0:
            return None
        # En büyük yüzü seç
        return max(faces, key=lambda f: f[2] * f[3])

    async def snapshot(self, path: str = "/tmp/robodi_snap.jpg"):
        """Anlık fotoğraf kaydet."""
        frame = await self.get_frame()
        if frame is not None and self._mode != "sim":
            self._cv2.imwrite(path, frame)
            return path
        return None

    def stop(self):
        if self._mode == "picamera2":
            self._picam.stop()
        elif self._cap:
            self._cap.release()
