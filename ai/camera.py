"""
ai/camera.py — Browser-based per-user frame store.

In the new architecture, there is NO server-side webcam.
Students and teachers capture video in their OWN browsers via getUserMedia(),
then POST JPEG frames to /api/upload_student_frame or /api/upload_teacher_frame.
This module holds the latest frame + analysed metrics for each user.
"""
import threading
import time
import cv2
import numpy as np
from ai.face_detector import FaceDetector


class CameraManager:
    """
    Thread-safe per-user frame store.
    Replaces the old single-webcam cv2.VideoCapture(0) design.

    Frame lifecycle:
      1. Browser POSTs a JPEG frame to /api/upload_student_frame.
      2. The route calls camera_manager.ingest_frame(user_id, jpeg_bytes).
      3. The AI pipeline analyses the frame and stores results.
      4. SSE streams call camera_manager.get_latest(user_id) to read results.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
        return cls._instance

    # ── Init ──────────────────────────────────────────────────────────────────
    def _init(self):
        self._frame_store: dict[int, bytes] = {}        # user_id → latest JPEG bytes
        self._metrics_store: dict[int, dict] = {}       # user_id → latest metrics dict
        self._last_seen: dict[int, float] = {}          # user_id → timestamp of last frame
        self._detectors: dict[int, FaceDetector] = {}   # user_id → isolated FaceDetector
        self._store_lock = threading.Lock()

        # Teacher's broadcast frame (separate from AI analysis)
        self._teacher_frame: bytes | None = None
        self._teacher_lock = threading.Lock()

        # Compatibility shim: old code checked camera_manager.has_hardware
        self.has_hardware = False  # Always False — no server webcam

        print("[OK] CameraManager initialized (browser-upload mode, no server webcam)")

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """No-op kept for backwards compatibility with old import-time call."""
        pass

    def ingest_frame(self, user_id: int, jpeg_bytes: bytes) -> dict:
        """
        Called by /api/upload_student_frame after receiving a JPEG from the browser.
        Runs AI analysis through a per-user isolated FaceDetector and stores result.
        Returns the metrics dict.
        """
        try:
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return {}

            # Get or create an isolated FaceDetector for this user
            with self._store_lock:
                if user_id not in self._detectors:
                    self._detectors[user_id] = FaceDetector()
                detector = self._detectors[user_id]

            analyzed_bytes, metrics = detector.analyze_frame(frame, user_id)

            with self._store_lock:
                self._frame_store[user_id] = analyzed_bytes
                self._metrics_store[user_id] = metrics
                self._last_seen[user_id] = time.time()

            return metrics
        except Exception as e:
            print(f"[WARNING] CameraManager.ingest_frame error for user {user_id}: {e}")
            return {}

    def get_latest(self, user_id: int | None = None):
        """
        Returns (frame_jpeg_bytes, metrics_dict) for a given user.
        If user_id is None, returns the teacher's broadcast frame.
        If no frame available, returns a placeholder.
        """
        if user_id is None:
            with self._teacher_lock:
                return self._teacher_frame or self._placeholder_frame(), None

        with self._store_lock:
            frame = self._frame_store.get(user_id)
            metrics = self._metrics_store.get(user_id)

        if frame:
            return frame, metrics
        return self._placeholder_frame(), None

    def update_teacher_frame(self, jpeg_bytes: bytes):
        """Store the teacher's broadcast frame (uploaded by teacher's browser)."""
        with self._teacher_lock:
            self._teacher_frame = jpeg_bytes

    def is_user_active(self, user_id: int, timeout_secs: float = 10.0) -> bool:
        """True if we received a frame from this user within the timeout window."""
        with self._store_lock:
            last = self._last_seen.get(user_id, 0)
        return (time.time() - last) < timeout_secs

    # ── Placeholder Frame ─────────────────────────────────────────────────────
    def _placeholder_frame(self) -> bytes:
        """Dark placeholder shown before the browser sends its first frame."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (20, 10, 10)  # Dark navy

        for i in range(0, 640, 40):
            cv2.line(img, (i, 0), (i, 480), (30, 30, 30), 1)
        for i in range(0, 480, 40):
            cv2.line(img, (0, i), (640, i), (30, 30, 30), 1)

        cv2.putText(img, "AI CLASSROOM", (200, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(img, "Waiting for browser camera...", (140, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 1)
        cv2.putText(img, "Please allow camera access", (160, 295), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

        if int(time.time()) % 2 == 0:
            cv2.circle(img, (185, 210), 6, (0, 255, 255), -1)

        _, buf = cv2.imencode('.jpg', img)
        return buf.tobytes()


# Global singleton
camera_manager = CameraManager()
