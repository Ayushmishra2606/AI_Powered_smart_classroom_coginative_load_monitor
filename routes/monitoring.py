from flask import Blueprint, render_template, Response, current_app
from flask_login import login_required
from models.student import Student
from models.database import db
from ai.analyzer import analyze_class
import json
import time

monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/monitoring')
@login_required
def live():
    students = Student.query.all()
    return render_template('monitoring/live.html', students=students)


@monitoring_bp.route('/api/monitoring/stream')
@login_required
def stream():
    """SSE stream for live monitoring page — runs analysis inside app context."""
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    students = Student.query.all()
                    if students:
                        ids   = [s.id for s in students]
                        names = {s.id: s.name for s in students}
                        analysis = analyze_class(ids)
                        for r in analysis['per_student']:
                            r['name'] = names.get(r['student_id'], 'Unknown')
                        payload = json.dumps({'students': analysis['per_student'],
                                              'summary': analysis['class_summary']})
                    else:
                        payload = json.dumps({'students': [], 'summary': {}})
                    yield f"data: {payload}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(2)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
