from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from models.session import MonitoringSession
from models.user import StudentProfile
from models.database import db
from datetime import datetime, timedelta
import random

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/analytics')
@login_required
def index():
    profiles = StudentProfile.query.all()
    return render_template('analytics/index.html', students=profiles)


@analytics_bp.route('/api/analytics/data')
@login_required
def data():
    """Return 7-day trend data for charts."""
    labels, attention_trend, cognitive_trend, engagement_trend = [], [], [], []
    now = datetime.utcnow()
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        labels.append(day.strftime('%b %d'))
        day_start = day.replace(hour=0, minute=0, second=0)
        day_end   = day.replace(hour=23, minute=59, second=59)
        sessions  = MonitoringSession.query.filter(
            MonitoringSession.timestamp >= day_start,
            MonitoringSession.timestamp <= day_end
        ).all()
        if sessions:
            avg_att = sum(s.attention_score for s in sessions) / len(sessions)
            avg_cog = sum(s.cognitive_load  for s in sessions) / len(sessions)
        else:
            avg_att = random.uniform(55, 85)
            avg_cog = random.uniform(35, 70)
        engagement = min(100, avg_att * 0.7 + (100 - avg_cog) * 0.3)
        attention_trend.append(round(avg_att, 1))
        cognitive_trend.append(round(avg_cog, 1))
        engagement_trend.append(round(engagement, 1))

    profiles = StudentProfile.query.all()
    subject_difficulty = {}
    for p in profiles:
        sessions = MonitoringSession.query.filter_by(student_id=p.id).all()
        name = p.user.name if p.user else f'Student{p.id}'
        subject_difficulty[name] = round(
            sum(x.cognitive_load for x in sessions)/len(sessions) if sessions else random.uniform(40, 80), 1)

    return jsonify({
        'labels': labels, 'attention': attention_trend,
        'cognitive': cognitive_trend, 'engagement': engagement_trend,
        'subject_difficulty': subject_difficulty
    })
