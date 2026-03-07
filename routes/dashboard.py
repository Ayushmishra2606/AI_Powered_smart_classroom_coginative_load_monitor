from flask import Blueprint, render_template, jsonify, Response, current_app, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.user import StudentProfile
from models.session import MonitoringSession
from models.alert import Alert
from models.timetable import TimetableEntry, ClassSession, ClassEnrollment, generate_join_code
from models.database import db
from ai.analyzer import analyze_class
import json
import time

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    profiles = StudentProfile.query.all()
    alerts = Alert.query.filter_by(is_read=False).order_by(Alert.timestamp.desc()).limit(5).all()
    last_sessions = {}
    from models.department import Subject, Department
    from models.timetable import ClassRoom, DAYS
    from datetime import datetime

    for p in profiles:
        sess = MonitoringSession.query.filter_by(student_id=p.id)\
            .order_by(MonitoringSession.timestamp.desc()).first()
        last_sessions[p.id] = sess

    active_instant = TimetableEntry.query.filter_by(teacher_id=current_user.id, class_type='instant').order_by(TimetableEntry.id.desc()).first()

    return render_template('dashboard/index.html',
                           teacher=current_user,
                           students=profiles,
                           alerts=alerts,
                           last_sessions=last_sessions,
                           subjects=Subject.query.all(),
                           rooms=ClassRoom.query.all(),
                           days=DAYS,
                           now=datetime.now(),
                           active_instant=active_instant)


@dashboard_bp.route('/dashboard/instant-class', methods=['POST'])
@login_required
def start_instant_class():
    """Immediately start an instant class with a public join link."""
    # Find a default room (or accept from form, but we'll use first available for 'instant')
    from models.timetable import ClassRoom
    room = ClassRoom.query.first() 
    # Use a dummy subject for instant class if none provided
    from models.department import Subject
    subject = Subject.query.first()
    
    now = datetime.now()
    end_time = (now + timedelta(hours=1)).strftime('%H:%M')
    
    entry = TimetableEntry(
        subject_id=subject.id,
        teacher_id=current_user.id,
        room_id=room.id,
        day_of_week=now.weekday(),
        start_time=now.strftime('%H:%M'),
        end_time=end_time,
        class_type='instant',
        is_public=True,
        join_code=generate_join_code()
    )
    db.session.add(entry)
    db.session.commit()
    
    # Immediately start the session
    session = ClassSession(timetable_id=entry.id, status='active')
    db.session.add(session)
    db.session.commit()
    
    flash(f'Instant Class started! Join code: {entry.join_code}', 'success')
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/dashboard/custom-class', methods=['POST'])
@login_required
def schedule_custom_class():
    """Schedule a class for explicitly selected students."""
    subject_id = request.form.get('subject_id')
    room_id = request.form.get('room_id')
    day_of_week = request.form.get('day_of_week')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    student_ids = request.form.getlist('student_ids') # list of student profile IDs
    
    entry = TimetableEntry(
        subject_id=subject_id,
        teacher_id=current_user.id,
        room_id=room_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        class_type='custom'
    )
    db.session.add(entry)
    db.session.commit()
    
    for sid in student_ids:
        enroll = ClassEnrollment(timetable_id=entry.id, student_id=sid)
        db.session.add(enroll)
        
    db.session.commit()
    flash('Custom Class scheduled successfully', 'success')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/api/dashboard/live')
@login_required
def live_stream():
    """Server-Sent Events stream for live dashboard updates."""
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    students = StudentProfile.query.all()
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
