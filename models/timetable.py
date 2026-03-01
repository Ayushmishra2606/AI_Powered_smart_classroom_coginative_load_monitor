from models.database import db
from datetime import datetime, time
import string
import random

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

def generate_join_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

class ClassEnrollment(db.Model):
    __tablename__ = 'class_enrollments'
    id           = db.Column(db.Integer, primary_key=True)
    timetable_id = db.Column(db.Integer, db.ForeignKey('timetable_entries.id', ondelete='CASCADE'), nullable=False)
    student_id   = db.Column(db.Integer, db.ForeignKey('student_profiles.id', ondelete='CASCADE'), nullable=False)


class ClassRoom(db.Model):
    __tablename__ = 'classrooms'
    id       = db.Column(db.Integer, primary_key=True)
    room_no  = db.Column(db.String(20), nullable=False)
    building = db.Column(db.String(50), default='Main Block')
    capacity = db.Column(db.Integer, default=60)

    timetable_entries = db.relationship('TimetableEntry', backref='room', lazy=True)

    def to_dict(self):
        return {'id': self.id, 'room_no': self.room_no, 'building': self.building, 'capacity': self.capacity}


class TimetableEntry(db.Model):
    """Recurring weekly schedule slot."""
    __tablename__ = 'timetable_entries'
    id          = db.Column(db.Integer, primary_key=True)
    subject_id  = db.Column(db.Integer, db.ForeignKey('subjects.id'),   nullable=False)
    teacher_id  = db.Column(db.Integer, db.ForeignKey('users.id'),      nullable=False)
    room_id     = db.Column(db.Integer, db.ForeignKey('classrooms.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Mon … 5=Sat
    start_time  = db.Column(db.String(5), nullable=False)  # "HH:MM"
    end_time    = db.Column(db.String(5), nullable=False)
    semester      = db.Column(db.Integer, default=1)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)

    # New fields for Instant/Custom classes
    class_type    = db.Column(db.String(20), default='regular') # regular/custom/instant
    is_public     = db.Column(db.Boolean, default=False)
    join_code     = db.Column(db.String(10), unique=True, nullable=True)

    sessions      = db.relationship('ClassSession', backref='timetable_entry', lazy=True)
    enrollments   = db.relationship('ClassEnrollment', backref='timetable_entry', lazy=True, cascade='all, delete-orphan')

    def is_active_now(self):
        """Returns True if this slot is currently in progress or is an ongoing instant class."""
        if self.class_type == 'instant':
            return True # Managed manually via sessions
        now = datetime.now()
        if now.weekday() != self.day_of_week:
            return False
        current = now.strftime('%H:%M')
        return self.start_time <= current <= self.end_time

    def day_name(self):
        return DAYS[self.day_of_week] if 0 <= self.day_of_week <= 5 else '?'

    def to_dict(self):
        return {
            'id': self.id,
            'subject': self.subject.name if self.subject else '',
            'subject_code': self.subject.code if self.subject else '',
            'subject_color': self.subject.color if self.subject else '#6366f1',
            'teacher': self.teacher.name if self.teacher else '',
            'room': self.room.room_no if self.room else '',
            'building': self.room.building if self.room else '',
            'day': self.day_name(),
            'day_of_week': self.day_of_week,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'semester': self.semester,
            'is_active': self.is_active_now(),
            'class_type': self.class_type,
            'is_public': self.is_public,
            'join_code': self.join_code
        }


class ClassSession(db.Model):
    """A live instance of a TimetableEntry on a specific date."""
    __tablename__ = 'class_sessions'
    id             = db.Column(db.Integer, primary_key=True)
    timetable_id   = db.Column(db.Integer, db.ForeignKey('timetable_entries.id'), nullable=False)
    date           = db.Column(db.Date, default=datetime.utcnow)
    started_at     = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at       = db.Column(db.DateTime, nullable=True)
    status         = db.Column(db.String(20), default='active')   # active/ended

    attendances    = db.relationship('Attendance',   backref='class_session', lazy=True)
    focus_sessions = db.relationship('FocusSession', backref='class_session', lazy=True)
