"""
ai/face_recognizer.py — LBPH Face Recognizer for Automated Attendance
Uses the existing model structure from face-reccognization/ folder.
"""
import cv2
import numpy as np
import os
import json
import threading
from datetime import datetime

# Paths (relative to project root, resolved via os.path)
BASE_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FR_DIR        = os.path.join(BASE_DIR, 'face-reccognization')
MODEL_PATH    = os.path.join(FR_DIR, 'face_recognizer.yml')
DB_DIR        = os.path.join(FR_DIR, 'database')
MAPPING_PATH  = os.path.join(FR_DIR, 'name_mapping.json')
HAAR_PATH     = os.path.join(FR_DIR, 'haarcascade_frontalface_default.xml')
UPLOADS_DIR   = os.path.join(BASE_DIR, 'static', 'face_uploads')

FACE_W, FACE_H    = 130, 100
CONFIDENCE_THRESH = 80  # lower = stricter; LBPH score < this = recognized


class FaceRecognizer:
    """Thread-safe singleton LBPH face recognizer."""

    _instance = None
    _lock      = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
        return cls._instance

    # ── Init ──────────────────────────────────────────────────────────────────
    def _init(self):
        os.makedirs(DB_DIR, exist_ok=True)
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        self.cascade = cv2.CascadeClassifier(HAAR_PATH)
        self._model  = None
        self._id_to_student_id: dict[int, int] = {}  # LBPH label → StudentProfile.id
        self._load_model()

    # ── Model persistence ────────────────────────────────────────────────────
    def _load_model(self):
        """Load model + mapping from disk if they exist."""
        if os.path.exists(MODEL_PATH) and os.path.exists(MAPPING_PATH):
            try:
                self._model = cv2.face.LBPHFaceRecognizer_create()
                self._model.read(MODEL_PATH)
                with open(MAPPING_PATH) as f:
                    raw = json.load(f)
                # mapping file stores {str_label: student_id}
                self._id_to_student_id = {int(k): int(v) for k, v in raw.items()}
                print(f"✅ Face recognizer loaded — {len(self._id_to_student_id)} students trained.")
            except Exception as e:
                print(f"⚠️ Could not load face recognizer: {e}")
                self._model = None

    def is_ready(self) -> bool:
        return self._model is not None and len(self._id_to_student_id) > 0

    # ── Training ──────────────────────────────────────────────────────────────
    def rebuild_model(self):
        """
        Scan face-reccognization/database/<student_id>/ folders,
        train fresh LBPH model, save model + mapping JSON.
        """
        images, labels = [], []
        label_map: dict[int, int] = {}  # LBPH label (0,1,2...) → student_profile_id

        lbph_label = 0
        for folder in sorted(os.listdir(DB_DIR)):
            folder_path = os.path.join(DB_DIR, folder)
            if not os.path.isdir(folder_path):
                continue
            # Folder name must be "student_<id>"
            if not folder.startswith('student_'):
                continue
            try:
                student_id = int(folder.split('_', 1)[1])
            except ValueError:
                continue

            face_found = False
            for fname in os.listdir(folder_path):
                img_path = os.path.join(folder_path, fname)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img_resized = cv2.resize(img, (FACE_W, FACE_H))
                images.append(img_resized)
                labels.append(lbph_label)
                face_found = True

            if face_found:
                label_map[lbph_label] = student_id
                lbph_label += 1

        if not images:
            print("⚠️ No face images found — model not trained.")
            return False

        model = cv2.face.LBPHFaceRecognizer_create()
        model.train(np.array(images), np.array(labels))
        model.write(MODEL_PATH)

        with open(MAPPING_PATH, 'w') as f:
            json.dump({str(k): v for k, v in label_map.items()}, f)

        # Hot-reload
        self._model           = model
        self._id_to_student_id = label_map
        print(f"✅ Model retrained — {len(label_map)} students.")
        return True

    # ── Face extraction ───────────────────────────────────────────────────────
    def extract_and_save_face(self, image_path: str, student_id: int) -> bool:
        """
        Open an image, detect a face, save 130x100 grayscale crop to
        database/student_<id>/ directory.  Returns True on success.
        """
        img = cv2.imread(image_path)
        if img is None:
            return False
        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, 1.3, 5, minSize=(60, 60))

        if len(faces) == 0:
            return False

        # Use the largest face
        x, y, w, h = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]
        face_crop   = gray[y:y + h, x:x + w]
        face_resized = cv2.resize(face_crop, (FACE_W, FACE_H))

        dest_dir = os.path.join(DB_DIR, f'student_{student_id}')
        os.makedirs(dest_dir, exist_ok=True)

        # Save multiple crops (slight variations) for better recognition
        dest = os.path.join(dest_dir, 'face_0.jpg')
        cv2.imwrite(dest, face_resized)
        # Add brightness variation
        brighter = np.clip(face_resized.astype(np.int16) + 20, 0, 255).astype(np.uint8)
        cv2.imwrite(os.path.join(dest_dir, 'face_1.jpg'), brighter)
        darker = np.clip(face_resized.astype(np.int16) - 20, 0, 255).astype(np.uint8)
        cv2.imwrite(os.path.join(dest_dir, 'face_2.jpg'), darker)

        return True

    # ── Recognition ───────────────────────────────────────────────────────────
    def recognize_frame(self, frame: np.ndarray) -> list[dict]:
        """
        Detect and recognize all faces in a BGR frame.
        Returns list of dicts: {student_id, confidence, x, y, w, h, label}
        """
        if not self.is_ready():
            return []

        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, 1.3, 5, minSize=(60, 60))

        results = []
        for (x, y, w, h) in faces:
            face_crop    = gray[y:y + h, x:x + w]
            face_resized = cv2.resize(face_crop, (FACE_W, FACE_H))
            try:
                label, confidence = self._model.predict(face_resized)
            except Exception:
                continue

            recognized = confidence < CONFIDENCE_THRESH
            student_id = self._id_to_student_id.get(label) if recognized else None

            results.append({
                'student_id': student_id,
                'confidence': round(float(confidence), 1),
                'recognized': recognized,
                'x': int(x), 'y': int(y),
                'w': int(w), 'h': int(h),
            })

        return results

    def annotate_frame(self, frame: np.ndarray, results: list[dict],
                       name_map: dict[int, str]) -> np.ndarray:
        """Draw bounding boxes + names on the frame."""
        annotated = frame.copy()
        for r in results:
            x, y, w, h = r['x'], r['y'], r['w'], r['h']
            if r['recognized']:
                name  = name_map.get(r['student_id'], f"ID:{r['student_id']}")
                color = (0, 255, 100)
                label = f"{name} ({r['confidence']:.0f})"
            else:
                color = (0, 100, 255)
                label = f"Unknown ({r['confidence']:.0f})"
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv2.putText(annotated, label, (x, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        return annotated


# Singleton instance
face_recognizer = FaceRecognizer()
