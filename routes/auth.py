from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from models.database import db
from models.student import Teacher

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        teacher = Teacher.query.filter_by(email=email).first()
        if teacher and teacher.check_password(password):
            login_user(teacher)
            return redirect(url_for('dashboard.index'))
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if Teacher.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            teacher = Teacher(name=name, email=email)
            teacher.set_password(password)
            db.session.add(teacher)
            db.session.commit()
            login_user(teacher)
            return redirect(url_for('dashboard.index'))
    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
