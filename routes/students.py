from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required
from models.database import db
from models.student import Student
import random

students_bp = Blueprint('students', __name__)

AVATAR_COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#3b82f6']


@students_bp.route('/students')
@login_required
def index():
    students = Student.query.order_by(Student.created_at.desc()).all()
    return render_template('dashboard/students.html', students=students)


@students_bp.route('/students/add', methods=['POST'])
@login_required
def add_student():
    name = request.form.get('name', '').strip()
    roll_no = request.form.get('roll_no', '').strip()
    class_name = request.form.get('class_name', '').strip()
    if not name or not roll_no or not class_name:
        flash('All fields are required.', 'error')
    elif Student.query.filter_by(roll_no=roll_no).first():
        flash(f'Roll number {roll_no} already exists.', 'error')
    else:
        color = random.choice(AVATAR_COLORS)
        student = Student(name=name, roll_no=roll_no, class_name=class_name, avatar_color=color)
        db.session.add(student)
        db.session.commit()
        flash(f'Student {name} added successfully.', 'success')
    return redirect(url_for('students.index'))


@students_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash(f'Student {student.name} removed.', 'success')
    return redirect(url_for('students.index'))


@students_bp.route('/api/students')
@login_required
def api_list():
    students = Student.query.all()
    return jsonify([s.to_dict() for s in students])
