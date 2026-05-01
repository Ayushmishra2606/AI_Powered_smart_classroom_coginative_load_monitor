from flask import Blueprint, render_template, Response, jsonify, request, redirect, url_for, current_app, session as flask_session, flash

from flask_login import login_required, current_user
from models.database import db
from models.user import StudentProfile
from models.timetable import ClassSession, TimetableEntry
from models.attendance import Attendance
from models.focus import FocusSession
from ai.analyzer import simulate_student
import json, time, random

# Simple in-memory storage for live signaling (Chat/Nudges)
# Format: { session_id: [ {'type': 'nudge', 'student_id': 1, 'message': '...'}, ... ] }
LIVE_SIGNALS = {}

classroom_bp = Blueprint('classroom', __name__, url_prefix='/classroom')

@classroom_bp.route('/join/<code>', methods=['GET', 'POST'])
def join_public(code):
    """Handle public join links for Instant Classes."""
    entry = TimetableEntry.query.filter_by(join_code=code, is_public=True).first_or_404()
    session = ClassSession.query.filter_by(timetable_id=entry.id, status='active').first()
    
    if not session:
        flash("This class has already ended.", "error")
        return redirect(url_for('auth.login'))
        
    if current_user.is_authenticated:
        if current_user.is_student():
            return redirect(url_for('classroom.room', session_id=session.id))
        else:
            flash("Teachers/Admins cannot join as students.", "warning")
            return redirect(url_for('dashboard.index'))
            
    # Guest user logic
    if request.method == 'POST':
        guest_name = request.form.get('guest_name')
        if guest_name:
            flask_session['guest_name'] = guest_name
            flask_session['guest_room_id'] = session.id
            return redirect(url_for('classroom.guest_room', session_id=session.id))
            
    return render_template('classroom/guest_join.html', entry=entry)

@classroom_bp.route('/guest/<int:session_id>')
def guest_room(session_id):
    """Render the classroom for a guest."""
    if flask_session.get('guest_room_id') != session_id or not flask_session.get('guest_name'):
        return redirect(url_for('auth.login'))
        
    class_session = ClassSession.query.get_or_404(session_id)
    entry = class_session.timetable_entry
    student_count = Attendance.query.filter_by(class_session_id=session_id).count()
    
    # Fake profile for the template
    class DummyProfile:
        class DummyUser:
            def __init__(self, name): self.name = name
        def __init__(self, name):
            self.user = self.DummyUser(name)
            self.avatar_color = '#' + ''.join([random.choice('0123456789ABCDEF') for j in range(6)])
            
    profile = DummyProfile(flask_session['guest_name'])
    
    import random
    return render_template('classroom/room.html',
                           session=class_session, entry=entry,
                           student_count=student_count,
                           profile=profile,
                           is_teacher=False,
                           is_guest=True)

@classroom_bp.route('/<int:session_id>')
@login_required
def room(session_id):
    session = ClassSession.query.get_or_404(session_id)
    entry   = session.timetable_entry
    # Count students in this session
    student_count = Attendance.query.filter_by(class_session_id=session_id).count()
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    return render_template('classroom/room.html',
                           session=session, entry=entry,
                           student_count=student_count,
                           profile=profile,
                           is_teacher=current_user.is_teacher())


@classroom_bp.route('/<int:session_id>/stream')
@login_required
def stream(session_id):
    """SSE stream — per-student AI data for this student in this session."""
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    student_id = profile.id if profile else current_user.id
    user_id    = current_user.id  # Flask user ID for camera_manager lookup
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    from ai.camera import camera_manager

                    # Use real AI metrics if this user has an active browser camera
                    data = None
                    if camera_manager.is_user_active(user_id):
                        _, metrics = camera_manager.get_latest(user_id)
                        if metrics:
                            data = metrics.copy()
                            data['student_id'] = student_id

                    # Fall back to simulation if no real frame yet
                    if not data:
                        data = simulate_student(student_id)

                    # Screen share status
                    from ai.screen_manager import screen_manager
                    data['is_screen_sharing'] = screen_manager.is_sharing

                    # Class pulse (uses simulation for all; can upgrade later)
                    from ai.analyzer import analyze_class
                    summary = analyze_class([student_id], {student_id: user_id})['class_summary']
                    data['class_summary'] = summary

                    # Live signals (nudges / chat)
                    signals = LIVE_SIGNALS.get(session_id, [])
                    my_signals = [s for s in signals if s.get('student_id') == student_id or s.get('type') == 'chat']
                    if my_signals:
                        data['signals'] = my_signals

                    yield f"data: {json.dumps(data)}\n\n"

                    # Consume delivered signals
                    if session_id in LIVE_SIGNALS:
                        LIVE_SIGNALS[session_id] = [s for s in LIVE_SIGNALS[session_id] if s not in my_signals]

                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(2)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@classroom_bp.route('/<int:session_id>/teacher-stream')
@login_required
def teacher_stream(session_id):
    """SSE stream — all students in this session, for teacher view."""
    from ai.analyzer import analyze_class
    app = current_app._get_current_object()

    def generate():
        with app.app_context():
            while True:
                try:
                    session  = ClassSession.query.get(session_id)
                    atts     = Attendance.query.filter_by(class_session_id=session_id).all()
                    ids      = [a.student_id for a in atts]
                    names    = {a.student_id: a.student.user.name for a in atts if a.student and a.student.user}
                    # Map student profile id → flask user id for camera lookup
                    user_id_map = {a.student_id: a.student.user_id for a in atts if a.student and a.student.user_id}
                    if ids:
                        from ai.analyzer import analyze_class
                        analysis = analyze_class(ids, user_id_map)
                        for r in analysis['per_student']:
                            r['name'] = names.get(r['student_id'], 'Student')

                        signals = LIVE_SIGNALS.get(session_id, [])

                        payload = json.dumps({'students': analysis['per_student'],
                                              'summary': analysis['class_summary'],
                                              'signals': signals})
                    else:
                        payload = json.dumps({'students': [], 'summary': {}})
                    yield f"data: {payload}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(3)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@classroom_bp.route('/<int:session_id>/leave', methods=['POST'])
@login_required
def leave(session_id):
    """Save a FocusSession summary when student leaves."""
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        avg_att = request.json.get('avg_attention', 0)
        avg_cog = request.json.get('avg_cognitive', 0)
        emotion = request.json.get('peak_emotion', 'neutral')
        dur     = request.json.get('duration_mins', 0)
        fs = FocusSession(student_id=profile.id, class_session_id=session_id,
                          avg_attention=avg_att, avg_cognitive=avg_cog,
                          peak_emotion=emotion, duration_mins=dur)
        db.session.add(fs)
        db.session.commit()
    return jsonify({'success': True})


@classroom_bp.route('/<int:session_id>/signal', methods=['POST'])
@login_required
def send_signal(session_id):
    """Teachers/admins send nudges; any authenticated user can send a chat message."""
    payload = request.get_json(silent=True) or {}

    signal_type = payload.get('type', '')
    msg         = str(payload.get('message', '')).strip()[:500]  # max 500 chars
    sid         = payload.get('student_id')  # target student profile id (nudge) or sender id (chat)

    # Validate signal type
    ALLOWED_TYPES = ('chat', 'nudge')
    if signal_type not in ALLOWED_TYPES:
        return jsonify({'success': False, 'error': 'Invalid signal type'}), 400

    # Only teachers/admins may send nudges
    if signal_type == 'nudge' and current_user.role not in ('teacher', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized: only teachers can send nudges'}), 403

    if not msg:
        return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400

    if session_id not in LIVE_SIGNALS:
        LIVE_SIGNALS[session_id] = []

    signal = {
        'type': signal_type,
        'message': msg,
        'student_id': int(sid) if sid is not None else None,
        'sender': current_user.name,
        'timestamp': time.time()
    }
    LIVE_SIGNALS[session_id].append(signal)

    # Keep queue short
    if len(LIVE_SIGNALS[session_id]) > 50:
        LIVE_SIGNALS[session_id].pop(0)

    return jsonify({'success': True})
