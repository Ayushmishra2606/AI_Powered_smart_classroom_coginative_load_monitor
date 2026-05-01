from flask import Blueprint, render_template, jsonify, Response, current_app, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.user import StudentProfile
from models.session import MonitoringSession
from models.alert import Alert
from models.timetable import TimetableEntry, ClassSession, ClassEnrollment, generate_join_code
from models.database import db
from ai.analyzer import analyze_class
import json
from datetime import datetime, timedelta
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

    # Find any currently active ClassSession for this teacher
    active_session = (
        ClassSession.query
        .join(ClassSession.timetable_entry)
        .filter(TimetableEntry.teacher_id == current_user.id)
        .filter(ClassSession.status == 'active')
        .order_by(ClassSession.id.desc())
        .first()
    )

    # For the join-link banner: only show if there is an ACTIVE instant session
    active_instant = None
    if active_session and active_session.timetable_entry.class_type == 'instant':
        active_instant = active_session.timetable_entry

    # All sessions (active + recent ended) for this teacher to display in the schedule list
    all_sessions = (
        ClassSession.query
        .join(ClassSession.timetable_entry)
        .filter(TimetableEntry.teacher_id == current_user.id)
        .order_by(ClassSession.id.desc())
        .limit(20)
        .all()
    )

    return render_template('dashboard/index.html',
                           teacher=current_user,
                           students=profiles,
                           alerts=alerts,
                           last_sessions=last_sessions,
                           subjects=Subject.query.all(),
                           rooms=ClassRoom.query.all(),
                           days=DAYS,
                           now=datetime.now(),
                           active_instant=active_instant,
                           active_session=active_session,
                           all_sessions=all_sessions)


@dashboard_bp.route('/dashboard/instant-class', methods=['POST'])
@login_required
def start_instant_class():
    """Immediately start an instant class with a public join link."""
    from models.timetable import ClassRoom
    from models.department import Subject
    from datetime import date

    room = ClassRoom.query.first()
    subject = Subject.query.first()

    if not room:
        flash('No classrooms configured. Ask admin to add a room first.', 'error')
        return redirect(url_for('dashboard.index'))
    if not subject:
        flash('No subjects configured. Ask admin to add a subject first.', 'error')
        return redirect(url_for('dashboard.index'))

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
    db.session.flush()  # get entry.id before commit

    # Immediately create an ACTIVE session
    session = ClassSession(timetable_id=entry.id, status='active', date=date.today())
    db.session.add(session)
    db.session.commit()

    flash(f'Instant Class started! Share join code: {entry.join_code}', 'success')
    return redirect(url_for('classroom.room', session_id=session.id))

@dashboard_bp.route('/dashboard/custom-class', methods=['POST'])
@login_required
def schedule_custom_class():
    """Schedule a class for explicitly selected students."""
    from datetime import date
    subject_id  = request.form.get('subject_id', type=int)
    room_id     = request.form.get('room_id', type=int)
    day_of_week = request.form.get('day_of_week', type=int)
    start_time  = request.form.get('start_time')
    end_time    = request.form.get('end_time')
    student_ids = request.form.getlist('student_ids')  # list of student profile IDs
    start_now   = request.form.get('start_now') == '1'  # optional checkbox
    is_public   = request.form.get('is_public') == '1'

    if not subject_id or not room_id or start_time is None or end_time is None:
        flash('All fields are required to schedule a class.', 'error')
        return redirect(url_for('dashboard.index'))

    entry = TimetableEntry(
        subject_id=subject_id,
        teacher_id=current_user.id,
        room_id=room_id,
        day_of_week=day_of_week if day_of_week is not None else datetime.now().weekday(),
        start_time=start_time,
        end_time=end_time,
        class_type='custom',
        is_public=is_public,
        join_code=generate_join_code()
    )
    db.session.add(entry)
    db.session.flush()  # get entry.id

    for sid in student_ids:
        try:
            enroll = ClassEnrollment(timetable_id=entry.id, student_id=int(sid))
            db.session.add(enroll)
        except (ValueError, TypeError):
            pass

    # Immediately start an active session so students can join now
    session = ClassSession(timetable_id=entry.id, status='active', date=date.today())
    db.session.add(session)
    db.session.commit()

    flash(f'Class scheduled and session started — students can join now!', 'success')
    return redirect(url_for('classroom.room', session_id=session.id))


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

                        summary = analysis['class_summary']
                        # Add a 5-minute cooldown for alerts to avoid 'irritating' duplicates
                        now_ts = time.time()
                        
                        if summary.get('avg_attention', 100) < 45:
                            # Use a unique key for this session and alert type
                            cooldown_key = f"att_drop_{current_user.id}"
                            last_sent = getattr(app, '_last_alert_ts', {}).get(cooldown_key, 0)
                            if now_ts - last_sent > 300: # 5 min cooldown
                                db.session.add(Alert(
                                    alert_type='attention_drop',
                                    message=f"Class attention at {summary['avg_attention']}% — consider a quick interaction.",
                                    severity='warning'
                                ))
                                # Update app-level cache (simple way for SSE)
                                if not hasattr(app, '_last_alert_ts'): app._last_alert_ts = {}
                                app._last_alert_ts[cooldown_key] = now_ts

                        distracted = summary.get('state_counts', {}).get('distracted', 0)
                        sleeping  = summary.get('state_counts', {}).get('sleeping', 0)
                        if (distracted + sleeping) >= 3:
                            cooldown_key = f"distract_{current_user.id}"
                            last_sent = getattr(app, '_last_alert_ts', {}).get(cooldown_key, 0)
                            if now_ts - last_sent > 300:
                                db.session.add(Alert(
                                    alert_type='distraction',
                                    message=f"Multiple students ({distracted + sleeping}) seem off-task.",
                                    severity='critical'
                                ))
                                if not hasattr(app, '_last_alert_ts'): app._last_alert_ts = {}
                                app._last_alert_ts[cooldown_key] = now_ts

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


@dashboard_bp.route('/dashboard/session/<int:session_id>/end', methods=['POST'])
@login_required
def end_session(session_id):
    """End an active class session."""
    session = ClassSession.query.get_or_404(session_id)
    # Verify ownership
    if session.timetable_entry.teacher_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard.index'))
    session.status = 'ended'
    session.ended_at = datetime.utcnow()
    db.session.commit()
    flash('Class session ended.', 'success')
    return redirect(url_for('dashboard.index'))
