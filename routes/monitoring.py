from flask import Blueprint, render_template, Response, current_app
from flask_login import login_required
from models.user import StudentProfile
from models.database import db
from ai.analyzer import analyze_class
from ai.camera import camera_manager
from ai.screen_manager import screen_manager
import json
import time
import base64

monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/monitoring')
@login_required
def live():
    profiles = StudentProfile.query.all()
    return render_template('monitoring/live.html', students=profiles)


@monitoring_bp.route('/api/video_feed')
@login_required
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
def stream():
    """SSE stream for live monitoring page — runs analysis inside app context."""
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    profiles = StudentProfile.query.all()
                    if profiles:
                        ids   = [p.id for p in profiles]
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
