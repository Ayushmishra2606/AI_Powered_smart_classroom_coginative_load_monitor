from models.database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(UserMixin, db.Model):
    """Base user for all roles: student, teacher, admin."""
    __tablename__ = 'users'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)
    email        = db.Column(db.String(120), unique=True, nullable=False)
    password_hash= db.Column(db.String(256), nullable=False)
    role         = db.Column(db.String(20), default='student')  # student/teacher/admin
    avatar_color = db.Column(db.String(20), default='#6366f1')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    is_active_   = db.Column(db.Boolean, default=True)

    # relationships
    student_profile = db.relationship('StudentProfile', backref='user', uselist=False, lazy=True)
    teacher_entries = db.relationship('TimetableEntry',  backref='teacher', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_student(self):  return self.role == 'student'
    def is_teacher(self):  return self.role == 'teacher'
    def is_admin(self):    return self.role == 'admin'


class StudentProfile(db.Model):
    """Extended profile for student role."""
    __tablename__ = 'student_profiles'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id  = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    enrollment_no  = db.Column(db.String(30), unique=True, nullable=True)
    semester       = db.Column(db.Integer, default=1)
    avatar_color   = db.Column(db.String(20), default='#06b6d4')

    # relationships
    attendances    = db.relationship('Attendance',    backref='student', lazy=True)
    focus_sessions = db.relationship('FocusSession',  backref='student', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.user.name if self.user else '',
            'enrollment_no': self.enrollment_no,
            'semester': self.semester,
            'avatar_color': self.avatar_color,
            'department': self.department.name if self.department else 'N/A'
        }
