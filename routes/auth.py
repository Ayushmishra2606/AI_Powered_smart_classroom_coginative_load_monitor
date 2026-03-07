from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models.database import db
from models.user import User, StudentProfile
from models.department import Department
import random

auth_bp = Blueprint('auth', __name__)

AVATAR_COLORS = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#ef4444','#ec4899','#3b82f6']


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user     = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if user.is_student():  return redirect(url_for('student.dashboard'))
            if user.is_teacher():  return redirect(url_for('dashboard.index'))
            if user.is_admin():    return redirect(url_for('admin.index'))
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    departments = Department.query.all()
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role     = request.form.get('role', 'student')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            color = random.choice(AVATAR_COLORS)
            user  = User(name=name, email=email, role=role, avatar_color=color)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # get user.id

            if role == 'student':
                dept_id = request.form.get('department_id', type=int)
                semester= request.form.get('semester', 1, type=int)
                enroll  = f"EN{user.id:04d}"
                profile = StudentProfile(user_id=user.id, department_id=dept_id,
                                         semester=semester, enrollment_no=enroll,
                                         avatar_color=color)
                db.session.add(profile)

            db.session.commit()
            login_user(user)
            if role == 'student':  return redirect(url_for('student.dashboard'))
            if role == 'teacher':  return redirect(url_for('dashboard.index'))
            return redirect(url_for('admin.index'))
    return render_template('auth/register.html', departments=departments)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
