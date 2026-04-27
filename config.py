"""
config.py — Application configuration
Selects the correct config class based on FLASK_ENV environment variable.
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared by all environments."""
    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-insecure-key-change-me')

    # ── Database ──────────────────────────────────────────────────────────────
    # On Render free tier: SQLite stored in /tmp (ephemeral, resets on redeploy)
    # On Render paid tier: set DATABASE_URL to a PostgreSQL URL
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url and _db_url.startswith('postgres://'):
        # Fix Heroku/Render legacy postgres:// → postgresql://
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url or ('sqlite:///' + os.path.join(BASE_DIR, 'classroom.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ── AI / Classroom ─────────────────────────────────────────────────────────
    SIMULATION_INTERVAL = int(os.environ.get('SIMULATION_INTERVAL', '3'))
    ATTENTION_ALERT_THRESHOLD = int(os.environ.get('ATTENTION_ALERT_THRESHOLD', '40'))
    COGNITIVE_ALERT_THRESHOLD = int(os.environ.get('COGNITIVE_ALERT_THRESHOLD', '75'))
    DISTRACTION_ALERT_COUNT   = int(os.environ.get('DISTRACTION_ALERT_COUNT', '3'))

    # ── Upload paths ──────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload


class DevelopmentConfig(Config):
    """Local development — debug ON, verbose logging."""
    DEBUG = True
    TESTING = False
    # Use local SQLite for dev (always)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'classroom.db')


def _raise_missing_key():
    """Called only in production when SECRET_KEY env var is not set."""
    raise RuntimeError(
        "FATAL: SECRET_KEY environment variable is not set. "
        "Set it in your Render dashboard under Environment Variables."
    )


class ProductionConfig(Config):
    """Render / production — debug OFF, strict secret key."""
    DEBUG = False
    TESTING = False

    # Force a real SECRET_KEY in production
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Tighten session cookie
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


def get_config():
    """Return the correct config class based on FLASK_ENV."""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if env == 'production' and not os.environ.get('SECRET_KEY'):
        _raise_missing_key()

    configs = {
        'development': DevelopmentConfig,
        'production':  ProductionConfig,
        'testing':     Config,
    }
    return configs.get(env, DevelopmentConfig)
