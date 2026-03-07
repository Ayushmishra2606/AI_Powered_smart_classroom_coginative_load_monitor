from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from functools import wraps
from models.database import db
from models.user import User, StudentProfile
from models.department import Department, Subject
from models.timetable import ClassRoom, TimetableEntry, ClassSession
from models.alert import Alert
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

SUBJECT_COLORS = ['#6366f1','#06b6d4','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#3b82f6']


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def index():
    stats = {
        'students': StudentProfile.query.count(),
        'teachers': User.query.filter_by(role='teacher').count(),
        'subjects': Subject.query.count(),
        'rooms':    ClassRoom.query.count(),
        'timetable_entries': TimetableEntry.query.count(),
    }
    departments  = Department.query.all()
    subjects     = Subject.query.all()
    rooms        = ClassRoom.query.all()
    timetable    = TimetableEntry.query.all()
    teachers     = User.query.filter_by(role='teacher').all()
    students     = StudentProfile.query.all()
    return render_template('admin/index.html', stats=stats, departments=departments,
                           subjects=subjects, rooms=rooms, timetable=timetable,
                           teachers=teachers, students=students)


@admin_bp.route('/departments/add', methods=['POST'])
@login_required
@admin_required
def add_department():
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().upper()
    if not name or not code:
        flash('Name and code required.', 'error')
    elif Department.query.filter_by(code=code).first():
        flash(f'Department code {code} already exists.', 'error')
    else:
        db.session.add(Department(name=name, code=code))
        db.session.commit()
        flash(f'Department {name} added.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/subjects/add', methods=['POST'])
@login_required
@admin_required
def add_subject():
    import random
    name  = request.form.get('name', '').strip()
    code  = request.form.get('code', '').strip().upper()
    dept  = request.form.get('department_id', type=int)
    creds = request.form.get('credits', 3, type=int)
    if not name or not code or not dept:
        flash('All fields required.', 'error')
    elif Subject.query.filter_by(code=code).first():
        flash(f'Subject code {code} exists.', 'error')
    else:
        color = random.choice(SUBJECT_COLORS)
        db.session.add(Subject(name=name, code=code, department_id=dept, credits=creds, color=color))
        db.session.commit()
        flash(f'Subject {name} added.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/rooms/add', methods=['POST'])
@login_required
@admin_required
def add_room():
    room_no  = request.form.get('room_no', '').strip()
    building = request.form.get('building', 'Main Block').strip()
    capacity = request.form.get('capacity', 60, type=int)
    if room_no:
        db.session.add(ClassRoom(room_no=room_no, building=building, capacity=capacity))
        db.session.commit()
        flash(f'Room {room_no} added.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/timetable/add', methods=['POST'])
@login_required
@admin_required
def add_timetable():
    subject_id  = request.form.get('subject_id', type=int)
    teacher_id  = request.form.get('teacher_id', type=int)
    room_id     = request.form.get('room_id', type=int)
    day         = request.form.get('day_of_week', type=int)
    start_time  = request.form.get('start_time', '')
    end_time    = request.form.get('end_time', '')
    semester    = request.form.get('semester', 1, type=int)
    dept_id     = request.form.get('department_id', type=int)
    if subject_id and teacher_id and room_id and start_time and end_time:
        entry = TimetableEntry(subject_id=subject_id, teacher_id=teacher_id,
                               room_id=room_id, day_of_week=day,
                               start_time=start_time, end_time=end_time,
                               semester=semester, department_id=dept_id)
        db.session.add(entry)
        db.session.commit()
        flash('Timetable entry added.', 'success')
    else:
        flash('All timetable fields required.', 'error')
    return redirect(url_for('admin.index'))


@admin_bp.route('/timetable/<int:entry_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_timetable(entry_id):
    entry = TimetableEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash('Timetable entry removed.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.role, User.name).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.name} removed.', 'success')
    return redirect(url_for('admin.users'))
