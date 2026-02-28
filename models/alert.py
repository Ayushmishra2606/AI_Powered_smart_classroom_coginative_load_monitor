from models.database import db
from datetime import datetime


class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(50), nullable=False)   # attention_drop/high_load/distraction
    message = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(20), default='warning')  # info/warning/critical
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'alert_type': self.alert_type,
            'message': self.message,
            'severity': self.severity,
            'is_read': self.is_read,
            'timestamp': self.timestamp.isoformat()
        }
