from models.database import db
from datetime import datetime


class FocusSession(db.Model):
    """Stores aggregated AI data for one student's classroom visit."""
    __tablename__ = 'focus_sessions'
    id               = db.Column(db.Integer, primary_key=True)
    student_id       = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=False)
    class_session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.id'),   nullable=True)
    avg_attention    = db.Column(db.Float,   default=0.0)
    avg_cognitive    = db.Column(db.Float,   default=0.0)
    peak_emotion     = db.Column(db.String(20), default='neutral')
    duration_mins    = db.Column(db.Float,   default=0.0)
    timestamp        = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'avg_attention': round(self.avg_attention, 1),
            'avg_cognitive': round(self.avg_cognitive, 1),
            'peak_emotion': self.peak_emotion,
            'duration_mins': round(self.duration_mins, 1),
            'timestamp': self.timestamp.isoformat()
        }
