"""
routes/monitoring.py — Monitoring dashboard and media API endpoints.

Camera feeds now come from BROWSER uploads (getUserMedia → POST JPEG),
NOT from a server-side webcam. The server never calls cv2.VideoCapture.
"""
from flask import Blueprint, render_template, Response, current_app, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models.user import StudentProfile
from models.timetable import ClassSession
from models.attendance import Attendance
from models.database import db
from ai.analyzer import analyze_class
from ai.camera import camera_manager
from ai.screen_manager import screen_manager
import json
import time
import base64

# NOTE: No camera_manager.start() here — there is no server-side webcam.
# Students and teachers upload their own frames from their browsers.


def teacher_required(f):
    """Decorator: restrict endpoint to teachers and admins only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role not in ('teacher', 'admin'):
            flash('Teacher or admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


monitoring_bp = Blueprint('monitoring', __name__)


# ── Pages ─────────────────────────────────────────────────────────────────────

@monitoring_bp.route('/monitoring')
@login_required
@teacher_required
def live():
    """Live monitoring page — shows all students and the teacher's active session."""
    profiles = StudentProfile.query.all()
    active_session = (
        ClassSession.query
        .join(ClassSession.timetable_entry)
        .filter_by(teacher_id=current_user.id)
        .filter(ClassSession.status == 'active')
        .order_by(ClassSession.id.desc())
        .first()
    )
    return render_template('monitoring/live.html',
                           students=profiles,
                           active_session=active_session)


# ── Frame Upload Endpoints (Browser → Server) ─────────────────────────────────

@monitoring_bp.route('/api/upload_student_frame', methods=['POST'])
@login_required
def upload_student_frame():
    """
    Students POST their camera frame here every ~2 seconds.
    The server runs AI analysis on the frame and stores results.
    """
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data'}), 400

    image_data = data.get('image')
    if not image_data:
        return jsonify({'success': False, 'error': 'No image'}), 400

    try:
        # Strip data URL header: "data:image/jpeg;base64,..."
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        jpeg_bytes = base64.b64decode(image_data)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Decode error: {e}'}), 400

    metrics = camera_manager.ingest_frame(current_user.id, jpeg_bytes)
    
    # Auto-verify attendance if face is detected
    if metrics.get('is_present'):
        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        if profile:
            # Find the student's active attendance for this session
            # We don't have session_id in the upload request, so we look for the latest active attendance
            att = Attendance.query.filter_by(student_id=profile.id).order_by(Attendance.joined_at.desc()).first()
            if att and not att.face_verified:
                att.face_verified = True
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

    return jsonify({'success': True, 'metrics': metrics})


@monitoring_bp.route('/api/upload_teacher_frame', methods=['POST'])
@login_required
@teacher_required
def upload_teacher_frame():
    """
    Teacher POSTs their camera frame here.
    Stored separately as the broadcast feed for students.
    """
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data'}), 400

    image_data = data.get('image')
    if not image_data:
        # Empty image = teacher stopped broadcasting
        camera_manager.update_teacher_frame(None)
        return jsonify({'success': True})

    try:
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        jpeg_bytes = base64.b64decode(image_data)
        camera_manager.update_teacher_frame(jpeg_bytes)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Decode error: {e}'}), 400

    return jsonify({'success': True})


# ── MJPEG Feed Endpoints (Server → Browser) ───────────────────────────────────

@monitoring_bp.route('/api/video_feed')
@login_required
def video_feed():
    """
    MJPEG stream of the current user's own AI-analyzed frame.
    Students see their personal AI monitor here.
    Falls back to placeholder until the browser sends a frame.
    """
    user_id = current_user.id

    def generate():
        while True:
            frame_bytes, _ = camera_manager.get_latest(user_id)
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.15)  # ~6 FPS for personal monitor

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@monitoring_bp.route('/api/teacher_feed')
@login_required
def teacher_feed():
    """
    MJPEG stream of the teacher's broadcast camera.
    Students see the teacher here.
    Falls back to placeholder until the teacher starts broadcasting.
    """
    def generate():
        while True:
            frame_bytes, _ = camera_manager.get_latest(None)  # None = teacher feed
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.1)  # ~10 FPS for teacher broadcast

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


# ── Screen Share ──────────────────────────────────────────────────────────────

@monitoring_bp.route('/api/upload_screen', methods=['POST'])
@login_required
@teacher_required
def upload_screen():
    """Teacher uploads screen capture frames."""
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data'}), 400

    image_data = data.get('image')
    if not image_data:
        # Teacher stopped screen sharing
        screen_manager.update_frame(None)
        return jsonify({'success': True})

    try:
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        frame_bytes = base64.b64decode(image_data)
        screen_manager.update_frame(frame_bytes)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    return jsonify({'success': True})


@monitoring_bp.route('/api/screen_feed')
def screen_feed():
    """MJPEG stream of the shared screen."""
    def generate():
        while True:
            frame = screen_manager.get_latest()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.2)
            else:
                # Yield placeholder so connection stays alive
                placeholder = camera_manager._placeholder_frame()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + placeholder + b'\r\n')
                time.sleep(1.0)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


# ── SSE Monitoring Stream ─────────────────────────────────────────────────────

@monitoring_bp.route('/api/monitoring/stream')
@login_required
@teacher_required
def stream():
    """SSE stream for live monitoring page."""
    session_id = request.args.get('session_id', type=int)
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    if session_id:
                        atts = Attendance.query.filter_by(class_session_id=session_id).all()
                        ids = [a.student_id for a in atts]
                        profiles = [a.student for a in atts if a.student]
                    else:
                        profiles = StudentProfile.query.all()
                        ids = [p.id for p in profiles]

                    if profiles and ids:
                        names = {p.id: p.user.name for p in profiles if p.user}
                        # Map student profile ID to Flask User ID for camera tracking
                        u_map = {p.id: p.user_id for p in profiles}
                        analysis = analyze_class(ids, user_id_map=u_map)
                        
                        for r in analysis['per_student']:
                            r['name'] = names.get(r['student_id'], 'Unknown')
                            uid = u_map.get(r['student_id'])
                            r['camera_active'] = camera_manager.is_user_active(uid) if uid else False
                            
                        payload = json.dumps({'students': analysis['per_student'],
                                              'summary': analysis['class_summary'],
                                              'is_screen_sharing': screen_manager.is_sharing})
                    else:
                        payload = json.dumps({'students': [], 'summary': {}, 'is_screen_sharing': False})
                    yield f"data: {payload}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(2)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
