"""
SentryGrid Configuration Module
================================
Loads environment variables and provides database connectivity.
Uses MySQL 8.0 via mysql-connector-python as the primary database.
CSA4310 – Internet Programming
"""

import os
from dotenv import load_dotenv
import mysql.connector

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration loaded from environment variables."""

    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'sentrygrid-csa4310-super-secret-key-2026')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    PORT = int(os.getenv('FLASK_PORT', 5000))

    # MySQL Database settings
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'NewPassword123')
    DB_NAME = os.getenv('DB_NAME', 'sentrygrid_db')

    # External API keys
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')

    # File upload settings
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))  # 5MB default
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Polling intervals (milliseconds) - passed to frontend JavaScript
    POLL_ALERTS = int(os.getenv('POLL_ALERTS', 30000))
    POLL_REQUESTS = int(os.getenv('POLL_REQUESTS', 15000))
    POLL_MESSAGES = int(os.getenv('POLL_MESSAGES', 5000))
    POLL_DASHBOARD = int(os.getenv('POLL_DASHBOARD', 60000))


def get_db_connection():
    """
    Create and return a new MySQL database connection.
    Uses credentials from environment variables.
    Returns: mysql.connector.connection object
    """
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=False  # Explicit transaction management
        )
        return conn
    except mysql.connector.Error as err:
        print(f"[MySQL Connection Error]: {err}")
        raise


def close_db_connection(conn, cursor=None):
    """
    Safely close database cursor and connection.
    Args:
        conn: MySQL connection object
        cursor: MySQL cursor object (optional)
    """
    try:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
    except Exception as e:
        print(f"[Error closing database connection]: {e}")


def allowed_file(filename):
    """Check if file extension is in ALLOWED_EXTENSIONS."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
