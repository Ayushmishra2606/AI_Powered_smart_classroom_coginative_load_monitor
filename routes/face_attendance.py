"""
routes/face_attendance.py — Face Recognition Attendance Blueprint
Handles: teacher attendance session control, real-time SSE recognition stream,
         student face upload & training, CSV export.
"""
import os, io, csv, json, time, base64, threading
import cv2
import numpy as np
from datetime import datetime, date

from flask import (Blueprint, render_template, jsonify, request,
                   Response, current_app, redirect, url_for, flash, send_file)
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename

from models.database import db
from models.user import StudentProfile
from models.timetable import ClassSession, TimetableEntry
from models.attendance import Attendance
from ai.face_recognizer import face_recognizer, UPLOADS_DIR

face_att_bp = Blueprint('face_attendance', __name__, url_prefix='/face-attendance')

# ── Helpers ──────────────────────────────────────────────────────────────────
ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'webp'}

def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('teacher', 'admin'):
            flash('Teacher access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

# ── In-memory attendance session state ───────────────────────────────────────
# { session_id: { student_id: timestamp_str } }  — marked this session
_marked_cache: dict[int, dict[int, str]] = {}
# { session_id: bool } — whether attendance mode is running
_active_sessions: dict[int, bool] = {}
_state_lock = threading.Lock()

def _get_or_create_today_session(teacher_id: int):
    """Get/create an active ClassSession for today for this teacher."""
    today = date.today()
    # Find the teacher's most recent active session
    session = (ClassSession.query
               .join(ClassSession.timetable_entry)
               .filter(TimetableEntry.teacher_id == teacher_id,
                       ClassSession.status == 'active')
               .order_by(ClassSession.id.desc())
               .first())
    if session:
        return session

    # Create an ad-hoc instant session
    from models.timetable import ClassRoom
    from models.department import Subject
    room    = ClassRoom.query.first()
    subject = Subject.query.first()
    now     = datetime.now()
    entry   = TimetableEntry(
        subject_id=subject.id if subject else None,
        teacher_id=teacher_id,
        room_id=room.id if room else None,
        day_of_week=now.weekday(),
        start_time=now.strftime('%H:%M'),
        end_time=(now.replace(hour=min(now.hour + 1, 23))).strftime('%H:%M'),
        class_type='instant', is_public=False
    )
    db.session.add(entry)
    db.session.flush()
    session = ClassSession(timetable_id=entry.id, status='active', date=today)
    db.session.add(session)
    db.session.commit()
    return session


# ─────────────────────────────────────────────────────────────────────────────
# TEACHER — Attendance Dashboard page
# ─────────────────────────────────────────────────────────────────────────────
@face_att_bp.route('/')
@login_required
@teacher_required
def dashboard():
    """Teacher's Face Attendance dashboard."""
    profiles = StudentProfile.query.all()
    # Find active session for this teacher
    active_session = (ClassSession.query
                      .join(ClassSession.timetable_entry)
                      .filter(TimetableEntry.teacher_id == current_user.id,
                              ClassSession.status == 'active')
                      .order_by(ClassSession.id.desc())
                      .first())
    # Build marked list for active session
    marked = {}
    if active_session:
        atts = Attendance.query.filter_by(class_session_id=active_session.id).all()
        marked = {a.student_id: a.joined_at.strftime('%H:%M:%S') for a in atts}

    return render_template('face_attendance/dashboard.html',
                           profiles=profiles,
                           active_session=active_session,
                           marked=marked,
                           model_ready=face_recognizer.is_ready())


# ─────────────────────────────────────────────────────────────────────────────
# START / STOP attendance session
# ─────────────────────────────────────────────────────────────────────────────
@face_att_bp.route('/start', methods=['POST'])
@login_required
@teacher_required
def start_attendance():
    session = _get_or_create_today_session(current_user.id)
    with _state_lock:
        _active_sessions[session.id] = True
    flash(f'Attendance session #{session.id} started.', 'success')
    return redirect(url_for('face_attendance.dashboard'))


@face_att_bp.route('/stop', methods=['POST'])
@login_required
@teacher_required
def stop_attendance():
    active_session = (ClassSession.query
                      .join(ClassSession.timetable_entry)
                      .filter(TimetableEntry.teacher_id == current_user.id,
                              ClassSession.status == 'active')
                      .order_by(ClassSession.id.desc())
                      .first())
    if active_session:
        with _state_lock:
            _active_sessions.pop(active_session.id, None)
        flash('Attendance session stopped.', 'info')
    return redirect(url_for('face_attendance.dashboard'))


# ─────────────────────────────────────────────────────────────────────────────
# Real-time Recognition SSE Stream (teacher view)
# ─────────────────────────────────────────────────────────────────────────────
@face_att_bp.route('/stream')
@login_required
@teacher_required
def stream():
    """SSE stream — recognizes faces from webcam, marks attendance automatically."""
    app = current_app._get_current_object()

    # Build name map once
    with app.app_context():
        profiles  = StudentProfile.query.all()
        name_map  = {p.id: p.user.name for p in profiles if p.user}

    def generate():
        from ai.camera import camera_manager

        with app.app_context():
            while True:
                try:
                    # Identify which session is active for this teacher
                    active_session = (ClassSession.query
                                      .join(ClassSession.timetable_entry)
                                      .filter(TimetableEntry.teacher_id == current_user.id,
                                              ClassSession.status == 'active')
                                      .order_by(ClassSession.id.desc())
                                      .first())

                    is_active = (active_session is not None and
                                 _active_sessions.get(active_session.id, False))

                    if not is_active:
                        yield f"data: {json.dumps({'status': 'idle'})}\n\n"
                        time.sleep(2)
                        continue

                    session_id = active_session.id

                    # Get frame from camera
                    frame_bytes, _ = camera_manager.get_latest()
                    if frame_bytes is None:
                        yield f"data: {json.dumps({'status': 'no_camera'})}\n\n"
                        time.sleep(2)
                        continue

                    # Decode frame
                    arr   = np.frombuffer(frame_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is None:
                        time.sleep(1)
                        continue

                    # Run recognition
                    results = face_recognizer.recognize_frame(frame)

                    # Mark attendance for newly recognized students
                    newly_marked = []
                    for r in results:
                        if not r['recognized'] or r['student_id'] is None:
                            continue
                        sid = r['student_id']
                        with _state_lock:
                            already = _marked_cache.get(session_id, {})
                        if sid in already:
                            continue  # duplicate prevention
                        # Check DB too
                        existing = Attendance.query.filter_by(
                            student_id=sid,
                            class_session_id=session_id
                        ).first()
                        if existing:
                            with _state_lock:
                                _marked_cache.setdefault(session_id, {})[sid] = 'db'
                            continue
                        # Mark attendance
                        att = Attendance(
                            student_id=sid,
                            class_session_id=session_id,
                            status='present',
                            face_verified=True,
                            joined_at=datetime.utcnow()
                        )
                        db.session.add(att)
                        db.session.commit()
                        ts = datetime.utcnow().strftime('%H:%M:%S')
                        with _state_lock:
                            _marked_cache.setdefault(session_id, {})[sid] = ts
                        newly_marked.append({'student_id': sid,
                                             'name': name_map.get(sid, f'ID:{sid}'),
                                             'time': ts,
                                             'confidence': r['confidence']})

                    # Annotated frame → base64 for preview
                    annotated = face_recognizer.annotate_frame(frame, results, name_map)
                    _, buf    = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    b64_frame = base64.b64encode(buf).decode('utf-8')

                    # Full marked list for this session
                    with _state_lock:
                        cached = _marked_cache.get(session_id, {})

                    payload = {
                        'status':        'active',
                        'session_id':    session_id,
                        'recognized':    [{'student_id': r['student_id'],
                                           'name': name_map.get(r['student_id'], '?'),
                                           'confidence': r['confidence'],
                                           'recognized': r['recognized']}
                                          for r in results],
                        'newly_marked':  newly_marked,
                        'total_marked':  len(cached),
                        'frame':         b64_frame,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
                time.sleep(1.5)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT — Upload face photo & train
# ─────────────────────────────────────────────────────────────────────────────
@face_att_bp.route('/upload_face', methods=['POST'])
@login_required
def upload_face():
    """Student or admin uploads a face photo; model is retrained automatically."""
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile and current_user.role not in ('teacher', 'admin'):
        return jsonify({'success': False, 'error': 'Student profile not found'}), 404

    # Admin/teacher can upload for any student
    target_id = request.form.get('student_id', type=int)
    if target_id and current_user.role in ('teacher', 'admin'):
        profile = StudentProfile.query.get_or_404(target_id)
    elif not profile:
        return jsonify({'success': False, 'error': 'No profile'}), 400

    if 'photo' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    photo = request.files['photo']
    if not photo or not _allowed(photo.filename):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400

    filename   = secure_filename(f'student_{profile.id}_{int(time.time())}.jpg')
    save_path  = os.path.join(UPLOADS_DIR, filename)
    photo.save(save_path)

    # Extract face and save to database folder
    ok = face_recognizer.extract_and_save_face(save_path, profile.id)
    if not ok:
        return jsonify({'success': False, 'error': 'No face detected in the image. Please upload a clear face photo.'}), 400

    # Retrain model
    trained = face_recognizer.rebuild_model()
    if not trained:
        return jsonify({'success': False, 'error': 'Training failed — no face data available.'}), 500

    # Update profile
    profile.is_face_trained = True
    profile.face_image_path = f'face_uploads/{filename}'
    db.session.commit()

    return jsonify({'success': True, 'message': f'Face trained for {profile.user.name}!'})


# ─────────────────────────────────────────────────────────────────────────────
# CSV Export
# ─────────────────────────────────────────────────────────────────────────────
@face_att_bp.route('/export/<int:session_id>')
@login_required
@teacher_required
def export_csv(session_id):
    """Export attendance for a session as CSV."""
    atts = (Attendance.query
            .filter_by(class_session_id=session_id)
            .order_by(Attendance.joined_at)
            .all())

    si  = io.StringIO()
    cw  = csv.writer(si)
    cw.writerow(['#', 'Name', 'Enrollment No', 'Status', 'Face Verified', 'Time'])
    for i, a in enumerate(atts, 1):
        name   = a.student.user.name if a.student and a.student.user else 'Unknown'
        enroll = a.student.enrollment_no if a.student else ''
        cw.writerow([i, name, enroll, a.status,
                     'Yes' if a.face_verified else 'No',
                     a.joined_at.strftime('%Y-%m-%d %H:%M:%S')])

    output = io.BytesIO(si.getvalue().encode('utf-8'))
    fname  = f'attendance_session_{session_id}_{date.today()}.csv'
    return send_file(output, mimetype='text/csv',
                     as_attachment=True, download_name=fname)


# ─────────────────────────────────────────────────────────────────────────────
# AJAX: Attendance list for a session
# ─────────────────────────────────────────────────────────────────────────────
@face_att_bp.route('/records/<int:session_id>')
@login_required
@teacher_required
def records(session_id):
    """Return current attendance records as JSON."""
    atts = Attendance.query.filter_by(class_session_id=session_id).all()
    return jsonify([{
        'student_id':  a.student_id,
        'name':        a.student.user.name if a.student and a.student.user else 'Unknown',
        'enrollment':  a.student.enrollment_no if a.student else '',
        'status':      a.status,
        'face_verified': a.face_verified,
        'time':        a.joined_at.strftime('%H:%M:%S')
    } for a in atts])


