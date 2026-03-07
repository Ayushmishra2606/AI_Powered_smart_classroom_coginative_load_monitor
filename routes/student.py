from flask import Blueprint, render_template, redirect, url_for, jsonify, request, flash
from flask_login import login_required, current_user
from functools import wraps
from models.database import db
from models.user import StudentProfile
from models.timetable import TimetableEntry, ClassSession, ClassEnrollment
from models.attendance import Attendance
from models.focus import FocusSession
from datetime import datetime, date, timedelta

student_bp = Blueprint('student', __name__, url_prefix='/student')


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_student():
            flash('Student access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def get_student_profile():
    return StudentProfile.query.filter_by(user_id=current_user.id).first()


@student_bp.route('/')
@login_required
@student_required
def dashboard():
    profile  = get_student_profile()
    today    = datetime.now().weekday()       # 0=Mon … 6=Sun
    # Today's timetable filtered by student's semester + dept
    today_schedule = _get_today_schedule(profile)
    # Last 3 focus sessions
    recent_focus   = FocusSession.query.filter_by(student_id=profile.id if profile else 0)\
                        .order_by(FocusSession.timestamp.desc()).limit(3).all() if profile else []
    # Attendance stats
    att_stats = _attendance_stats(profile)
    return render_template('student/dashboard.html', profile=profile,
                           today_schedule=today_schedule,
                           recent_focus=recent_focus, att_stats=att_stats)


@student_bp.route('/schedule')
@login_required
@student_required
def schedule():
    profile  = get_student_profile()
    entries  = _get_full_schedule(profile)
    days     = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    return render_template('student/schedule.html', profile=profile,
                           entries=entries, days=days,
                           now_day=datetime.now().weekday())


@student_bp.route('/attendance')
@login_required
@student_required
def attendance():
    profile  = get_student_profile()
    records  = Attendance.query.filter_by(student_id=profile.id if profile else 0)\
                  .order_by(Attendance.joined_at.desc()).all() if profile else []
    stats    = _attendance_stats(profile)
    return render_template('student/attendance.html', profile=profile,
                           records=records, stats=stats)


@student_bp.route('/analytics')
@login_required
@student_required
def analytics():
    profile = get_student_profile()
    return render_template('student/analytics.html', profile=profile)


@student_bp.route('/join-class/<int:entry_id>', methods=['POST'])
@login_required
@student_required
def join_class(entry_id):
    entry   = TimetableEntry.query.get_or_404(entry_id)
    profile = get_student_profile()
    # Create or get today's session
    today   = date.today()
    session = ClassSession.query.filter_by(timetable_id=entry_id, date=today).first()
    if not session:
        session = ClassSession(timetable_id=entry_id, date=today)
        db.session.add(session)
        db.session.flush()
    # Mark attendance
    existing_att = Attendance.query.filter_by(
        student_id=profile.id, class_session_id=session.id).first()
    if not existing_att and profile:
        att = Attendance(student_id=profile.id, class_session_id=session.id,
                         status='present', face_verified=True)
        db.session.add(att)
    db.session.commit()
    return redirect(url_for('classroom.room', session_id=session.id))


# ---- API endpoints ----
@student_bp.route('/api/focus-history')
@login_required
@student_required
def focus_history_api():
    profile = get_student_profile()
    if not profile:
        return jsonify({'labels': [], 'attention': [], 'cognitive': []})
    sessions = FocusSession.query.filter_by(student_id=profile.id)\
                   .order_by(FocusSession.timestamp.desc()).limit(14).all()
    sessions.reverse()
    return jsonify({
        'labels':    [s.timestamp.strftime('%b %d') for s in sessions],
        'attention': [round(s.avg_attention, 1) for s in sessions],
        'cognitive': [round(s.avg_cognitive, 1) for s in sessions],
        'emotions':  [s.peak_emotion for s in sessions]
    })


# ---- Helper functions ----
def _get_today_schedule(profile):
    today = datetime.now().weekday()  # 0=Mon
    if today > 5:  return []  # Sunday
    query = TimetableEntry.query.filter_by(day_of_week=today)
    if profile:
        # Get custom assigned classes
        enrolled_ids = [e.timetable_id for e in ClassEnrollment.query.filter_by(student_id=profile.id).all()]
        query = query.filter(
            (TimetableEntry.semester == profile.semester) |
            (TimetableEntry.department_id == profile.department_id) |
            (TimetableEntry.id.in_(enrolled_ids))
        )
    return query.order_by(TimetableEntry.start_time).all()


def _get_full_schedule(profile):
    query = TimetableEntry.query
    if profile:
        # Get custom assigned classes
        enrolled_ids = [e.timetable_id for e in ClassEnrollment.query.filter_by(student_id=profile.id).all()]
        query = query.filter(
            (TimetableEntry.semester == profile.semester) |
            (TimetableEntry.department_id == profile.department_id) |
            (TimetableEntry.id.in_(enrolled_ids))
        )
    return query.order_by(TimetableEntry.day_of_week, TimetableEntry.start_time).all()


def _attendance_stats(profile):
    if not profile:
        return {'total': 0, 'present': 0, 'pct': 0}
    total   = Attendance.query.filter_by(student_id=profile.id).count()
    present = Attendance.query.filter_by(student_id=profile.id, status='present').count()
    pct     = round((present / total * 100) if total else 0, 1)
    return {'total': total, 'present': present, 'pct': pct}
