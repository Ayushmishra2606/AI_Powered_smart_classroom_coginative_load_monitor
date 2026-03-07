from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required
from models.database import db
from models.user import StudentProfile, User
from models.department import Department
import random

students_bp = Blueprint('students', __name__)

AVATAR_COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#3b82f6']


@students_bp.route('/students')
@login_required
def index():
    profiles = StudentProfile.query.join(User).order_by(User.name).all()
    departments = Department.query.all()
    return render_template('dashboard/students.html', students=profiles, departments=departments)


@students_bp.route('/students/add', methods=['POST'])
@login_required
def add_student():
    name   = request.form.get('name', '').strip()
    email  = request.form.get('email', '').strip()
    dept   = request.form.get('department_id', type=int)
    sem    = request.form.get('semester', 1, type=int)
    if not name or not email:
        flash('Name and email required.', 'error')
    elif User.query.filter_by(email=email).first():
        flash('Email already registered.', 'error')
    else:
        color = random.choice(AVATAR_COLORS)
        u = User(name=name, email=email, role='student', avatar_color=color)
        u.set_password('pass123')
        db.session.add(u)
        db.session.flush()
        profile = StudentProfile(user_id=u.id, department_id=dept, semester=sem,
                                  enrollment_no=f'CS{u.id:04d}', avatar_color=color)
        db.session.add(profile)
        db.session.commit()
        flash(f'Student {name} added.', 'success')
    return redirect(url_for('students.index'))


@students_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    profile = StudentProfile.query.get_or_404(student_id)
    user    = User.query.get(profile.user_id)
    db.session.delete(profile)
    if user: db.session.delete(user)
    db.session.commit()
    flash('Student removed.', 'success')
    return redirect(url_for('students.index'))


@students_bp.route('/api/students')
@login_required
def api_list():
    profiles = StudentProfile.query.all()
    return jsonify([p.to_dict() for p in profiles])
