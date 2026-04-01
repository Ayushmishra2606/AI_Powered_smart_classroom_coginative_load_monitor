from flask import Blueprint, render_template, Response, current_app, request, redirect, url_for, flash
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


@monitoring_bp.route('/monitoring')
@login_required
@teacher_required
def live():
    """Live monitoring page — shows all students and the teacher's active session."""
    profiles = StudentProfile.query.all()
    # Find the most recent active ClassSession for this teacher
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


@monitoring_bp.route('/api/video_feed')
@login_required
@teacher_required
def video_feed():
    """MJPEG stream from the global CameraManager."""
    def generate():
        while True:
            frame_bytes, _ = camera_manager.get_latest()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                time.sleep(1.0)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@monitoring_bp.route('/api/teacher_feed')
def teacher_feed():
    """MJPEG stream representing the teacher's broadcast."""
    def generate():
        while True:
            frame_bytes, _ = camera_manager.get_latest()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                time.sleep(1.0)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@monitoring_bp.route('/api/upload_screen', methods=['POST'])
@login_required
@teacher_required
def upload_screen():
    """Endpoint for teacher to upload screen capture frames."""
    data = request.json.get('image')
    if data:
        # data is "data:image/jpeg;base64,..."
        try:
            header, encoded = data.split(',', 1)
            frame_bytes = base64.b64decode(encoded)
            screen_manager.update_frame(frame_bytes)
            return json.dumps({'success': True}), 200
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)}), 400
    return json.dumps({'success': False}), 400

@monitoring_bp.route('/api/screen_feed')
def screen_feed():
    """MJPEG stream of the shared screen."""
    def generate():
        while True:
            frame = screen_manager.get_latest()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.1) # 10 FPS for screen is fine
            else:
                time.sleep(0.5)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')



@monitoring_bp.route('/api/monitoring/stream')
@login_required
@teacher_required
def stream():
    """SSE stream for live monitoring page — session-scoped when session_id provided."""
    session_id = request.args.get('session_id', type=int)
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    # Session-scoped: use only students in this session's attendance
                    if session_id:
                        atts = Attendance.query.filter_by(class_session_id=session_id).all()
                        ids  = [a.student_id for a in atts]
                        profiles = [a.student for a in atts if a.student]
                    else:
                        profiles = StudentProfile.query.all()
                        ids = [p.id for p in profiles]

                    if profiles and ids:
                        names = {p.id: p.user.name for p in profiles if p.user}
                        analysis = analyze_class(ids)
                        for r in analysis['per_student']:
                            r['name'] = names.get(r['student_id'], 'Unknown')
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
