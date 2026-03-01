from models.database import db


class Department(db.Model):
    __tablename__ = 'departments'
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)

    subjects  = db.relationship('Subject', backref='department', lazy=True)
    students  = db.relationship('StudentProfile', backref='department', lazy=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'code': self.code}


class Subject(db.Model):
    __tablename__ = 'subjects'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    code          = db.Column(db.String(20), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    credits       = db.Column(db.Integer, default=3)
    color         = db.Column(db.String(20), default='#6366f1')

    timetable_entries = db.relationship('TimetableEntry', backref='subject', lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'code': self.code, 'credits': self.credits,
            'color': self.color,
            'department': self.department.name if self.department else ''
        }
