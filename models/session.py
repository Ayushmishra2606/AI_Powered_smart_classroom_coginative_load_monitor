from models.database import db
from datetime import datetime


class MonitoringSession(db.Model):
    __tablename__ = 'monitoring_sessions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=False)
    attention_score = db.Column(db.Float, default=0.0)    # 0-100
    cognitive_load = db.Column(db.Float, default=0.0)     # 0-100
    attention_state = db.Column(db.String(20), default='attentive')  # attentive/distracted/sleeping/absent
    cognitive_state = db.Column(db.String(20), default='optimal')    # low/optimal/high
    emotion = db.Column(db.String(20), default='neutral')
    blink_rate = db.Column(db.Float, default=15.0)
    head_pose = db.Column(db.String(20), default='forward')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'attention_score': round(self.attention_score, 1),
            'cognitive_load': round(self.cognitive_load, 1),
            'attention_state': self.attention_state,
            'cognitive_state': self.cognitive_state,
            'emotion': self.emotion,
            'blink_rate': round(self.blink_rate, 1),
            'head_pose': self.head_pose,
            'timestamp': self.timestamp.isoformat()
        }
