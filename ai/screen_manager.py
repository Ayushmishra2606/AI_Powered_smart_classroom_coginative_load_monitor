import threading
import time

class ScreenManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ScreenManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self.latest_frame = None
        self.is_sharing = False
        self.last_update = 0
        self.lock = threading.Lock()

    def update_frame(self, frame_bytes):
        with self.lock:
            self.latest_frame = frame_bytes
            self.last_update = time.time()
            self.is_sharing = True

    def get_latest(self):
        with self.lock:
            # If no update for 5 seconds, assume sharing stopped
            if time.time() - self.last_update > 5:
                self.is_sharing = False
                return None
            return self.latest_frame

    def stop_sharing(self):
        with self.lock:
            self.is_sharing = False
            self.latest_frame = None

screen_manager = ScreenManager()
