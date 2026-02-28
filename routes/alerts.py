from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.alert import Alert
from models.database import db

alerts_bp = Blueprint('alerts', __name__)


@alerts_bp.route('/api/alerts')
@login_required
def get_alerts():
    alerts = Alert.query.order_by(Alert.timestamp.desc()).limit(20).all()
    return jsonify([a.to_dict() for a in alerts])


@alerts_bp.route('/api/alerts/unread-count')
@login_required
def unread_count():
    count = Alert.query.filter_by(is_read=False).count()
    return jsonify({'count': count})


@alerts_bp.route('/api/alerts/<int:alert_id>/read', methods=['POST'])
@login_required
def mark_read(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@alerts_bp.route('/api/alerts/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Alert.query.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})
