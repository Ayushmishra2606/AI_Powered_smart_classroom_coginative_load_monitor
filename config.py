import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-classroom-secret-key-2024')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'classroom.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Simulation interval in seconds
    SIMULATION_INTERVAL = 3
    # Alert thresholds
    ATTENTION_ALERT_THRESHOLD = 40   # below this → alert
    COGNITIVE_ALERT_THRESHOLD = 75   # above this → overloaded alert
    DISTRACTION_ALERT_COUNT = 3      # number of distracted students to trigger alert
