import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def get_database_uri():
    url = (os.getenv('DATABASE_URL') or '').strip()
    if url:
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url
    return f'sqlite:///{os.path.join(BASE_DIR, "instance", "appeals.db")}'


def get_engine_options(database_uri):
    if database_uri.startswith('sqlite'):
        return {
            'connect_args': {'check_same_thread': False, 'timeout': 30},
        }
    return {}


_DATABASE_URI = get_database_uri()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'super-secret-key-for-diploma-2026')

    SQLALCHEMY_DATABASE_URI = _DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options(_DATABASE_URI)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PREFERRED_URL_SCHEME = 'https' if SESSION_COOKIE_SECURE else 'http'