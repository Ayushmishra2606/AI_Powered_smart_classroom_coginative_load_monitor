from models.database import db
from datetime import datetime

class ClassroomSignal(db.Model):
    __tablename__ = 'classroom_signals'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, index=True)
    sender_id = db.Column(db.Integer)
    sender_name = db.Column(db.String(100))
    signal_type = db.Column(db.String(50)) # chat, nudge, rtc-signal
    message = db.Column(db.Text)
    target_id = db.Column(db.Integer) # for nudges/rtc targeting
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.signal_type,
            'sender': self.sender_name,
            'message': self.message,
            'sender_id': self.sender_id,
            'target_id': self.target_id,
            'timestamp': self.timestamp.timestamp()
        }
