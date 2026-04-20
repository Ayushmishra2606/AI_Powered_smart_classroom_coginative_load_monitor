import cv2
import threading
import time
from ai.face_detector import FaceDetector

class CameraManager:
    """Singleton to manage a single webcam cv2 capture safely across threads."""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CameraManager, cls).__new__(cls)
                cls._instance._init()
            return cls._instance
            
    def _init(self):
        self.cap = None
        self.detector = FaceDetector()
        self.running = False
        self.thread = None
        
        self.latest_frame_bytes = None
        self.latest_metrics = None
        self.metrics_lock = threading.Lock()
        
        self.has_hardware = False

    def start(self):
        if self.running:
            return
            
        self.cap = cv2.VideoCapture(0)
        # Check if camera opened successfully
        if not self.cap.isOpened():
            print("WARNING: No webcam detected. OpenCV fallbacks to simulation.")
            self.has_hardware = False
            return
            
        self.has_hardware = True
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print("[OK] Background Camera Thread Started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
            
    def _capture_loop(self):
        while self.running and self.cap.isOpened():
            success, frame = self.cap.read()
            if not success:
                time.sleep(0.1)
                continue
                
            frame = cv2.flip(frame, 1) # Mirror image
            
            # Analyze frame
            jpg_bytes, metrics = self.detector.analyze_frame(frame)
            
            with self.metrics_lock:
                self.latest_frame_bytes = jpg_bytes
                self.latest_metrics = metrics
                
            # Throttle slightly to save CPU (e.g. process ~15 fps)
            time.sleep(0.05)

    def get_latest(self):
        """Returns (frame_mjpeg_bytes, metrics_dict)."""
        if not self.has_hardware:
            return self._get_placeholder_frame(), None
            
        with self.metrics_lock:
            return self.latest_frame_bytes, self.latest_metrics

    def _get_placeholder_frame(self):
        """Generates a dark placeholder frame for simulation mode."""
        import numpy as np
        # Create a dark blue/black background
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (20, 10, 10) # Dark navy
        
        # Add subtle grid or design
        for i in range(0, 640, 40): cv2.line(img, (i, 0), (i, 480), (30, 30, 30), 1)
        for i in range(0, 480, 40): cv2.line(img, (0, i), (640, i), (30, 30, 30), 1)
        
        cv2.putText(img, "AI CLASSROOM", (210, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(img, "SIMULATION ACTIVE", (200, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        
        # Add a pulsing dot to show it's "live"
        import time
        if int(time.time()) % 2 == 0:
            cv2.circle(img, (190, 220), 5, (0, 255, 255), -1)
            
        _, buffer = cv2.imencode('.jpg', img)
        return buffer.tobytes()

# Global singleton instance
camera_manager = CameraManager()
