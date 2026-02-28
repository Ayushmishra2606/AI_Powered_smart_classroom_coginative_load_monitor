from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from models.session import MonitoringSession
from models.student import Student
from models.database import db
from datetime import datetime, timedelta
import random

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/analytics')
@login_required
def index():
    students = Student.query.all()
    return render_template('analytics/index.html', students=students)


@analytics_bp.route('/api/analytics/data')
@login_required
def data():
    """Return 7-day trend data for charts."""
    labels = []
    attention_trend = []
    cognitive_trend = []
    engagement_trend = []

    now = datetime.utcnow()
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        labels.append(day.strftime('%b %d'))
        # Try to get real DB data
        day_start = day.replace(hour=0, minute=0, second=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        sessions = MonitoringSession.query.filter(
            MonitoringSession.timestamp >= day_start,
            MonitoringSession.timestamp <= day_end
        ).all()

        if sessions:
            avg_att = sum(s.attention_score for s in sessions) / len(sessions)
            avg_cog = sum(s.cognitive_load for s in sessions) / len(sessions)
            # engagement = inverse of cognitive overload penalty
            engagement = min(100, avg_att * 0.7 + (100 - avg_cog) * 0.3)
        else:
            # Simulated baseline for demo
            avg_att = random.uniform(55, 85)
            avg_cog = random.uniform(35, 70)
            engagement = avg_att * 0.7 + (100 - avg_cog) * 0.3

        attention_trend.append(round(avg_att, 1))
        cognitive_trend.append(round(avg_cog, 1))
        engagement_trend.append(round(engagement, 1))

    students = Student.query.all()
    subject_difficulty = {}
    for s in students:
        sessions = MonitoringSession.query.filter_by(student_id=s.id).all()
        if sessions:
            avg_cog = sum(x.cognitive_load for x in sessions) / len(sessions)
            subject_difficulty[s.name] = round(avg_cog, 1)
        else:
            subject_difficulty[s.name] = round(random.uniform(40, 80), 1)

    return jsonify({
        'labels': labels,
        'attention': attention_trend,
        'cognitive': cognitive_trend,
        'engagement': engagement_trend,
        'subject_difficulty': subject_difficulty
    })
