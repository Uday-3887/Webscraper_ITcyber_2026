from __future__ import annotations

import os
from werkzeug.security import generate_password_hash
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent


class Config:
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', generate_password_hash(os.getenv('ADMIN_PASSWORD', 'Admin@123')))
    SECRET_KEY = os.getenv('SECRET_KEY', 'development-only-change-me')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    DATABASE_PATH = os.getenv('DATABASE_PATH', str(BASE_DIR / 'database' / 'scraper.db'))
    EXPORT_FOLDER = os.getenv('EXPORT_FOLDER', str(BASE_DIR / 'exports'))
    LOG_FILE = os.getenv('LOG_FILE', str(BASE_DIR / 'logs' / 'app.log'))

    DEFAULT_REQUEST_TIMEOUT = int(os.getenv('DEFAULT_REQUEST_TIMEOUT', '20'))
    DEFAULT_BROWSER_TIMEOUT = int(os.getenv('DEFAULT_BROWSER_TIMEOUT', '60000'))
    MAX_PAGES = int(os.getenv('MAX_PAGES', '500'))
    MAX_RECORDS = int(os.getenv('MAX_RECORDS', '5000'))
    MIN_REQUEST_DELAY = float(os.getenv('MIN_REQUEST_DELAY', '1'))
    MAX_RESPONSE_BYTES = int(os.getenv('MAX_RESPONSE_BYTES', '5000000'))
    MAX_JOB_SECONDS = int(os.getenv('MAX_JOB_SECONDS', '600'))
    MAX_LOAD_MORE_CLICKS = int(os.getenv('MAX_LOAD_MORE_CLICKS', '30'))
    MAX_SCROLL_COUNT = int(os.getenv('MAX_SCROLL_COUNT', '30'))
    PLAYWRIGHT_HEADLESS = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '1048576'))
    CORS_ORIGINS = [item.strip() for item in os.getenv(
        'CORS_ORIGINS', 'http://127.0.0.1:5000,http://localhost:5000'
    ).split(',') if item.strip()]
