from models.database import db
from datetime import datetime


class Attendance(db.Model):
    __tablename__ = 'attendances'
    id              = db.Column(db.Integer, primary_key=True)
    student_id      = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=False)
    class_session_id= db.Column(db.Integer, db.ForeignKey('class_sessions.id'),   nullable=False)
    status          = db.Column(db.String(20), default='present')  # present/absent/late
    face_verified   = db.Column(db.Boolean, default=True)
    joined_at       = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'student': self.student.user.name if self.student and self.student.user else '',
            'status': self.status,
            'face_verified': self.face_verified,
            'joined_at': self.joined_at.isoformat()
        }
