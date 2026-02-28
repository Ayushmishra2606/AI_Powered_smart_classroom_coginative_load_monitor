from flask import Blueprint, render_template, jsonify, Response, current_app
from flask_login import login_required, current_user
from models.student import Student
from models.session import MonitoringSession
from models.alert import Alert
from models.database import db
from ai.analyzer import analyze_class
import json
import time

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    students = Student.query.all()
    alerts = Alert.query.filter_by(is_read=False).order_by(Alert.timestamp.desc()).limit(5).all()
    last_sessions = {}
    for s in students:
        sess = MonitoringSession.query.filter_by(student_id=s.id)\
            .order_by(MonitoringSession.timestamp.desc()).first()
        last_sessions[s.id] = sess
    return render_template('dashboard/index.html',
                           teacher=current_user,
                           students=students,
                           alerts=alerts,
                           last_sessions=last_sessions)


@dashboard_bp.route('/api/dashboard/live')
@login_required
def live_stream():
    """Server-Sent Events stream for live dashboard updates."""
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    students = Student.query.all()
                    if students:
                        student_ids = [s.id for s in students]
                        analysis = analyze_class(student_ids)

                        # Save sessions to DB
                        for result in analysis['per_student']:
                            sess = MonitoringSession(
                                student_id=result['student_id'],
                                attention_score=result['attention_score'],
                                cognitive_load=result['cognitive_load'],
                                attention_state=result['attention_state'],
                                cognitive_state=result['cognitive_state'],
                                emotion=result['emotion'],
                                blink_rate=result['blink_rate'],
                                head_pose=result['head_pose']
                            )
                            db.session.add(sess)

                        summary = analysis['class_summary']
                        if summary.get('avg_attention', 100) < 45:
                            db.session.add(Alert(
                                alert_type='attention_drop',
                                message=f"Class attention at {summary['avg_attention']}% — below threshold",
                                severity='warning'
                            ))

                        distracted = summary.get('state_counts', {}).get('distracted', 0)
                        sleeping  = summary.get('state_counts', {}).get('sleeping', 0)
                        if (distracted + sleeping) >= 3:
                            db.session.add(Alert(
                                alert_type='distraction',
                                message=f"{distracted + sleeping} students off-task",
                                severity='critical'
                            ))

                        db.session.commit()

                        payload = json.dumps({
                            'summary': analysis['class_summary'],
                            'students': {str(r['student_id']): r for r in analysis['per_student']}
                        })
                        yield f"data: {payload}\n\n"
                    else:
                        yield f"data: {json.dumps({'summary': {}, 'students': {}})}\n\n"
                except Exception as e:
                    db.session.rollback()
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(3)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
