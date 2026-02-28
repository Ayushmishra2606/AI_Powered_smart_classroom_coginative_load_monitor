"""
AI-Powered Smart Classroom — Flask Application Entry Point
"""
from flask import Flask, redirect, url_for
from flask_login import current_user
from config import Config
from models.database import db, login_manager
from models.student import Teacher


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please login to access the dashboard.'
    login_manager.login_message_category = 'error'

    @login_manager.user_loader
    def load_user(user_id):
        return Teacher.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.students import students_bp
    from routes.monitoring import monitoring_bp
    from routes.analytics import analytics_bp
    from routes.alerts import alerts_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(alerts_bp)

    # Create DB tables and seed demo data
    with app.app_context():
        db.create_all()
        _seed_demo_data()

    return app


def _seed_demo_data():
    """Add demo students and a default teacher if the database is empty."""
    from models.student import Teacher, Student

    # Default teacher account
    if not Teacher.query.filter_by(email='teacher@demo.com').first():
        t = Teacher(name='Demo Teacher', email='teacher@demo.com')
        t.set_password('password123')
        db.session.add(t)

    # Demo students
    if Student.query.count() == 0:
        demo_students = [
            ('Aarav Sharma',   'CS001', 'CS-A', '#6366f1'),
            ('Priya Patel',    'CS002', 'CS-A', '#06b6d4'),
            ('Rohan Mehta',    'CS003', 'CS-A', '#10b981'),
            ('Ananya Singh',   'CS004', 'CS-A', '#f59e0b'),
            ('Vikram Gupta',   'CS005', 'CS-A', '#8b5cf6'),
            ('Sanya Kapoor',   'CS006', 'CS-A', '#ec4899'),
            ('Arjun Nair',     'CS007', 'CS-A', '#ef4444'),
            ('Meera Reddy',    'CS008', 'CS-A', '#3b82f6'),
        ]
        for name, roll, cls, color in demo_students:
            s = Student(name=name, roll_no=roll, class_name=cls, avatar_color=color)
            db.session.add(s)

    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    print("\n" + "="*55)
    print("  🧠 AI Smart Classroom — Flask Server")
    print("  📡  http://127.0.0.1:5000")
    print("  👤  Demo login: teacher@demo.com / password123")
    print("="*55 + "\n")
    app.run(debug=True, threaded=True)
