# 🧠 AI-Powered Smart Classroom: Cognitive Load & Engagement Monitor

A high-performance, real-time AI classroom monitoring system built with **Flask**, **OpenCV**, and **MediaPipe**. This platform enables teachers to monitor student engagement, track automated face-recognition attendance, and interact through bi-directional video and screen sharing.

---

## 🚀 Key Features

### 📸 Fully Automated Face Recognition Attendance
- **Zero-Friction Marking**: State-of-the-art LBPH face recognition automatically marks students present when they join the class.
- **Anti-Duplication**: Ensures students are marked present exactly once per session.
- **Teacher Dashboard**: Real-time MJPEG feed over SSE showing bounding boxes, live names, and confidence scores.
- **Student Training Portal**: Students upload a single photo that is automatically cropped, augmented, and trained into the AI model in the background.

### 👁️ Real-Time AI Monitoring
- **Attention Tracking:** Analyzes head pose, gaze stability, and blink rates to calculate live attention scores (0-100%).
- **Cognitive Load Detection:** Monitors facial expressions and blink frequency to estimate mental effort and confusion.
- **Hybrid AI Engine:** Uses **MediaPipe FaceMesh** for high-precision 3D tracking with a robust fallback to **OpenCV Haar Cascades** for wide compatibility.

### 👥 Role-Based Portals
- **Admin Control Panel:** Manage users, database tables, and university departments.
- **Teacher Dashboard:** Schedule instant/custom classes, view live analytics grids, and control attendance sessions.
- **Student Dashboard:** View upcoming schedule, personal focus analytics history, and manage face recognition training.

### 🎥 Live Bi-Directional Interaction
- **Teacher Broadcast:** Students see the teacher's live camera feed as the primary focal point.
- **Dual-Feed Layout:** Students can see their own AI-processed "Self-View" alongside the teacher's lesson.
- **Live Screen Sharing:** Teachers can share their desktop or specific windows directly with all students via a server-side MJPEG relay.

### 📊 Classroom Analytics
- **Class Pulse:** A live, aggregate engagement index showing the collective focus level of the entire classroom.
- **Live Dashboards:** Real-time per-student metrics for teachers and personal focus summaries for students.

---

## 🛠️ Tech Stack

- **Backend:** Flask (Python 3.x)
- **Database:** SQLite with SQLAlchemy ORM
- **AI/CV:** OpenCV (`opencv-contrib-python`), MediaPipe, SciPy
- **Real-Time Data:** Server-Sent Events (SSE) for metrics, MJPEG for video/screen streaming
- **Frontend:** HTML5, CSS3 (Glassmorphism), Vanilla JavaScript, Jinja2 Templates

---

## 📂 Project Structure

```text
mini-project/
├── ai/                 # Core AI Logic
│   ├── face_recognizer.py # Face Training & Recognition (LBPH)
│   ├── face_detector.py   # Landmark detection & heuristics
│   ├── camera.py          # Singleton Camera Manager
│   ├── analyzer.py        # Engagement & Class stats logic
│   └── screen_manager.py  # Screen share relay manager
├── models/             # SQLAlchemy Database Models
├── routes/             # Flask Blueprints (auth, student, face_attendance, etc.)
├── static/             # JS, CSS assets, & Face Uploads
├── templates/          # Jinja2 HTML templates
├── app.py              # Application Entry Point
└── classroom.db        # SQLite Database
```

---

## 📦 Installation & Setup

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/Ayushmishra2606/AI_Powered_smart_classroom_coginative_load_monitor.git
   cd AI_Powered_smart_classroom_coginative_load_monitor
   ```

2. **Set Up Virtual Environment:**

   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Database:**

   ```bash
   python app.py  # Automatically creates DB on first run
   python migrate_db.py  # Run this to apply any pending schema updates
   ```

5. **Run the Application:**
   ```bash
   python app.py
   ```
   Access at: `http://127.0.0.1:5000`

---

## 🤝 Contributing

Contributions are welcome! Please fork the repo, create a feature branch, and submit a PR.

## 📜 License

This project is licensed under the MIT License.

---

**Author:** [Rahul Rathore](https://github.com/rahulrathore579) & [Ayush Mishra](https://github.com/Ayushmishra2606)
