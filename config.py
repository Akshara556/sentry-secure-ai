import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-this-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # MongoDB configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/sentry_secure')
    MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/sentry_secure')  # For Flask-PyMongo
    
    # File upload configuration
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # Session configuration
    SESSION_COOKIE_SECURE = False  # Set to True for HTTPS in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Flask-Login configuration
    REMEMBER_COOKIE_DURATION = timedelta(days=1)