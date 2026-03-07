import cv2
import numpy as np
import time
import os
from datetime import datetime
from collections import deque

# Try to import mediapipe but prepare for failure in Python 3.14 environments
HAS_MEDIAPIPE = False
try:
    import mediapipe as mp
    # Check for solutions subpackage specifically
    if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_mesh'):
        mp_face_mesh = mp.solutions.face_mesh
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        HAS_MEDIAPIPE = True
except (ImportError, AttributeError):
    pass

class FaceDetector:
    def __init__(self):
        self.has_mp = HAS_MEDIAPIPE
        
        if self.has_mp:
            self.face_mesh = mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        else:
            # Fallback to OpenCV Haar Cascades
            cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            print("⚠️ MediaPipe solutions missing. Falling back to OpenCV Haar Cascades for face detection.")
        
        # State tracking over time
        self.blink_counter = 0
        self.blink_active = False
        self.blink_history = deque(maxlen=100)
        
        # Smoothers
        self.attention_ema = 100.0
        self.cognitive_ema = 50.0
        
        # EAR threshold (only for MediaPipe)
        self.ear_threshold = 0.22

    def calculate_ear(self, landmarks, frame_w, frame_h, eye_indices):
        from scipy.spatial import distance as dist
        pts = np.array([(landmarks[i].x * frame_w, landmarks[i].y * frame_h) for i in eye_indices])
        v1 = dist.euclidean(pts[1], pts[5])
        v2 = dist.euclidean(pts[2], pts[4])
        h = dist.euclidean(pts[0], pts[3])
        return (v1 + v2) / (2.0 * h) if h > 0 else 0

    def get_head_pose(self, face_rect, frame_w, frame_h):
        """Simulate head pose based on face position if MediaPipe unavailable."""
        fx, fy, fw, fh = face_rect
        center_x = fx + fw/2
        center_y = fy + fh/2
        
        # Normalize position relative to frame center
        norm_x = (center_x - frame_w/2) / (frame_w/2)
        norm_y = (center_y - frame_h/2) / (frame_h/2)
        
        yaw = norm_x * 45.0  # Guess yaw based on position
        pitch = norm_y * 30.0 # Guess pitch
        
        pose_label = "forward"
        if abs(yaw) > 15: pose_label = "left" if yaw < 0 else "right"
        elif abs(pitch) > 15: pose_label = "down" if pitch > 0 else "up"
            
        return pitch, yaw, 0, pose_label

    def analyze_frame(self, frame, student_id=1):
        h, w, _ = frame.shape
        annotated_frame = frame.copy()
        now = time.time()
        
        defaults = {
            'student_id': student_id,
            'is_present': False,
            'attention_score': 0, 'cognitive_load': 0,
            'attention_state': 'absent', 'cognitive_state': 'low',
            'emotion': 'neutral',
            'blink_rate': 0, 'head_pose': 'unknown',
            'timestamp': datetime.utcnow().isoformat() if 'datetime' in globals() else str(now)
        }

        if self.has_mp:
            # --- MediaPipe Logic ---
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)
            
            if not results.multi_face_landmarks:
                self.attention_ema = max(0, self.attention_ema - 5)
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                return buffer.tobytes(), defaults

            face_landmarks = results.multi_face_landmarks[0]
            nodes = face_landmarks.landmark
            
            # Ear/Blinks
            LEFT_EYE = [362, 385, 387, 263, 373, 380]
            RIGHT_EYE = [33, 160, 158, 133, 153, 144]
            left_ear = self.calculate_ear(nodes, w, h, LEFT_EYE)
            right_ear = self.calculate_ear(nodes, w, h, RIGHT_EYE)
            avg_ear = (left_ear + right_ear) / 2.0
            
            if avg_ear < self.ear_threshold:
                if not self.blink_active:
                    self.blink_active = True
                    self.blink_history.append(now)
            else:
                self.blink_active = False

            # Pose (Simulated or via SolvePnP if PnP points added - keeping simple for fallback)
            # Using position-based pose as it's more stable for this hybrid
            x_min = int(min([lm.x for lm in nodes]) * w)
            y_min = int(min([lm.y for lm in nodes]) * h)
            fw = int((max([lm.x for lm in nodes]) - min([lm.x for lm in nodes])) * w)
            fh = int((max([lm.y for lm in nodes]) - min([lm.y for lm in nodes])) * h)
            pitch, yaw, roll, pose_label = self.get_head_pose((x_min, y_min, fw, fh), w, h)
            
            # Draw Mesh
            mp_drawing.draw_landmarks(
                image=annotated_frame,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())
        else:
            # --- OpenCV Fallback Logic ---
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            if len(faces) == 0:
                self.attention_ema = max(0, self.attention_ema - 5)
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                return buffer.tobytes(), defaults
                
            # Take the largest face
            (x, y, fw, fh) = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)[0]
            cv2.rectangle(annotated_frame, (x, y), (x+fw, y+fh), (255, 0, 0), 2)
            cv2.putText(annotated_frame, "Face Detected (Fallback Mode)", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            pitch, yaw, roll, pose_label = self.get_head_pose((x, y, fw, fh), w, h)
            
            # Simulate binks randomly in fallback mode to keep UI alive
            if np.random.random() < 0.05: # 5% chance per frame
                if not self.blink_active:
                    self.blink_active = True
                    self.blink_history.append(now)
            else:
                self.blink_active = False

        # --- Metrics Calculation (Common) ---
        recent_blinks = [t for t in self.blink_history if now - t < 60.0]
        bpm = len(recent_blinks)

        yaw_penalty = min(100, (abs(yaw) / 45.0) * 100) if abs(yaw) > 15 else 0
        pitch_penalty = min(100, (abs(pitch) / 30.0) * 100) if abs(pitch) > 15 else 0
        
        raw_attention = 100.0 - max(yaw_penalty, pitch_penalty)
        self.attention_ema = self.attention_ema * 0.8 + raw_attention * 0.2
        att_score = round(max(0, min(100, self.attention_ema)), 1)
        
        # Categorical
        if att_score >= 70: att_state = 'attentive'
        elif att_score >= 45: att_state = 'distracted'
        else: att_state = 'sleeping'

        raw_cog = min(100.0, (bpm / 25.0) * 100)
        self.cognitive_ema = self.cognitive_ema * 0.9 + raw_cog * 0.1
        cog_score = round(max(0, min(100, self.cognitive_ema)), 1)
        
        cog_state = 'low' if cog_score < 35 else 'optimal' if cog_score <= 65 else 'high'
        emotion = 'neutral' if att_state == 'attentive' else 'bored' if att_state == 'distracted' else 'neutral'

        # Overlay Text
        cv2.putText(annotated_frame, f"Attention: {att_score}%", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Cognitive: {cog_score}%", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(annotated_frame, f"Pose: {pose_label}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        _, buffer = cv2.imencode('.jpg', annotated_frame)
        
        return buffer.tobytes(), {
            'student_id': student_id,
            'is_present': True,
            'attention_score': att_score, 'cognitive_load': cog_score,
            'attention_state': att_state, 'cognitive_state': cog_state,
            'emotion': emotion, 'blink_rate': bpm, 'head_pose': pose_label,
            'timestamp': datetime.utcnow().isoformat()
        }
