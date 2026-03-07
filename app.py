"""
AI-Powered Smart Classroom — Flask Application Factory
University Edition: Student / Teacher / Admin roles, Timetable, Live Classroom AI
"""
from flask import Flask, redirect, url_for
from flask_login import current_user
from models.database import db, login_manager
from config import Config
from datetime import datetime
import random


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    # ── Register Blueprints ──────────────────────────────────────────────────
    from routes.auth       import auth_bp
    from routes.dashboard  import dashboard_bp
    from routes.students   import students_bp
    from routes.monitoring import monitoring_bp
    from routes.analytics  import analytics_bp
    from routes.alerts     import alerts_bp
    from routes.admin      import admin_bp
    from routes.student    import student_bp
    from routes.classroom  import classroom_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(classroom_bp)

    # ── Root redirect ────────────────────────────────────────────────────────
    @app.route('/')
    def root():
        if current_user.is_authenticated:
            if current_user.is_student(): return redirect(url_for('student.dashboard'))
            if current_user.is_admin():   return redirect(url_for('admin.index'))
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    # ── Jinja2 globals ───────────────────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {'now': datetime.now(), 'now_day': datetime.now().weekday(),
                'enumerate': enumerate}

    # ── DB Init & Seed ───────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_demo_data()

    return app


def _seed_demo_data():
    from models.user import User, StudentProfile
    from models.department import Department, Subject
    from models.timetable import ClassRoom, TimetableEntry
    from models.alert import Alert

    if User.query.count() > 0:
        return   # Already seeded

    print("🌱 Seeding demo data...")

    COLORS = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#ef4444','#ec4899','#3b82f6']

    # ── Admin ────────────────────────────────────────────────────────────────
    admin = User(name='Admin', email='admin@demo.com', role='admin', avatar_color='#f59e0b')
    admin.set_password('pass123')
    db.session.add(admin)

    # ── Teachers ─────────────────────────────────────────────────────────────
    teachers_data = [
        ('Dr. Priya Sharma', 'teacher@demo.com', '#3b82f6'),
        ('Prof. Rahul Verma', 'teacher2@demo.com', '#8b5cf6'),
    ]
    teachers = []
    for name, email, color in teachers_data:
        t = User(name=name, email=email, role='teacher', avatar_color=color)
        t.set_password('pass123')
        db.session.add(t)
        teachers.append(t)

    db.session.flush()

    # ── Departments ──────────────────────────────────────────────────────────
    depts_data = [
        ('Computer Science Engineering', 'CSE'),
        ('Electronics Engineering',      'ECE'),
        ('Mechanical Engineering',       'ME'),
    ]
    depts = []
    for name, code in depts_data:
        d = Department(name=name, code=code)
        db.session.add(d)
        depts.append(d)
    db.session.flush()

    # ── Subjects ─────────────────────────────────────────────────────────────
    subjects_data = [
        ('Data Structures & Algorithms', 'DSA301', depts[0].id, 4, '#6366f1'),
        ('Machine Learning',             'ML401',  depts[0].id, 3, '#8b5cf6'),
        ('Database Systems',             'DB302',  depts[0].id, 3, '#06b6d4'),
        ('Digital Signal Processing',    'DSP201', depts[1].id, 3, '#10b981'),
        ('Engineering Mathematics',      'MATH101',depts[2].id, 4, '#f59e0b'),
        ('Computer Networks',            'CN303',  depts[0].id, 3, '#ef4444'),
    ]
    subjects = []
    for name, code, dept_id, cred, color in subjects_data:
        s = Subject(name=name, code=code, department_id=dept_id, credits=cred, color=color)
        db.session.add(s)
        subjects.append(s)
    db.session.flush()

    # ── Classrooms ───────────────────────────────────────────────────────────
    rooms_data = [
        ('A-101', 'Main Block', 60),
        ('B-204', 'Tech Block', 45),
        ('CS-LAB', 'CS Block', 30),
    ]
    rooms = []
    for room_no, building, cap in rooms_data:
        r = ClassRoom(room_no=room_no, building=building, capacity=cap)
        db.session.add(r)
        rooms.append(r)
    db.session.flush()

    # ── Timetable (Mon–Fri slots) ─────────────────────────────────────────────
    now = datetime.now()
    today_day = now.weekday()   # 0=Mon…4=Fri
    current_hour = now.strftime('%H')

    timetable_data = [
        # (subject_idx, teacher_idx, room_idx, day, start, end, semester)
        (0, 0, 0, 0, '09:00', '10:00', 3),   # DSA — Mon
        (1, 0, 1, 0, '10:00', '11:00', 3),   # ML  — Mon
        (2, 1, 0, 1, '09:00', '10:00', 3),   # DB  — Tue
        (3, 1, 2, 1, '11:00', '12:00', 3),   # DSP — Tue
        (4, 0, 0, 2, '10:00', '11:00', 3),   # MATH— Wed
        (5, 1, 1, 2, '14:00', '15:00', 3),   # CN  — Wed
        (0, 0, 2, 3, '09:00', '10:00', 3),   # DSA — Thu
        (1, 0, 0, 3, '11:00', '12:00', 3),   # ML  — Thu
        (2, 1, 1, 4, '09:00', '10:00', 3),   # DB  — Fri
        (5, 1, 0, 4, '14:00', '15:00', 3),   # CN  — Fri
    ]
    # Add today's slot at current time so JOIN works in demo
    current_start = f"{current_hour}:00"
    current_end   = f"{min(int(current_hour)+1, 22):02d}:00"
    timetable_data.append((0, 0, 0, today_day if today_day <= 5 else 0, current_start, current_end, 3))

    tt_entries = []
    for sub_i, tch_i, rm_i, day, start, end, sem in timetable_data:
        if day <= 5:
            entry = TimetableEntry(
                subject_id=subjects[sub_i].id,
                teacher_id=teachers[tch_i].id,
                room_id=rooms[rm_i].id,
                day_of_week=day,
                start_time=start,
                end_time=end,
                semester=sem,
                department_id=depts[0].id
            )
            db.session.add(entry)
            tt_entries.append(entry)

    # ── Students ─────────────────────────────────────────────────────────────
    students_data = [
        ('Aarav Sharma',   'student1@demo.com', 3),
        ('Priya Patel',    'student2@demo.com', 3),
        ('Rahul Gupta',    'student3@demo.com', 3),
        ('Meera Reddy',    'student4@demo.com', 3),
        ('Arjun Singh',    'student5@demo.com', 3),
        ('Kavya Nair',     'student6@demo.com', 3),
        ('Vikram Joshi',   'student7@demo.com', 3),
        ('Ananya Kumar',   'student8@demo.com', 3),
    ]
    for idx, (name, email, sem) in enumerate(students_data):
        color = COLORS[idx % len(COLORS)]
        u = User(name=name, email=email, role='student', avatar_color=color)
        u.set_password('pass123')
        db.session.add(u)
        db.session.flush()
        profile = StudentProfile(user_id=u.id, department_id=depts[0].id,
                                  semester=sem, enrollment_no=f'CS{2021+idx:04d}',
                                  avatar_color=color)
        db.session.add(profile)

    # ── Welcome alert ─────────────────────────────────────────────────────────
    db.session.add(Alert(alert_type='system', message='University AI Classroom system initialized. Welcome!', severity='info'))

    db.session.commit()
    print("✅ Demo data seeded — 1 admin, 2 teachers, 8 students, 3 depts, 6 subjects, 11 timetable entries")


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
