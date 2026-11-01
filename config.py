"""
SentryGrid Configuration Module
================================
Loads environment variables and provides database connectivity.
Primary database: MySQL 8.0 via mysql-connector-python.
Fallback: Auto-seeded SQLite database for cloud hosting environments
(such as Render) where external MySQL server is not yet provisioned.
CSA4310 – Internet Programming
"""

import os
import re
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration loaded from environment variables."""

    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'sentrygrid-csa4310-super-secret-key-2026')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    PORT = int(os.getenv('PORT', os.getenv('FLASK_PORT', 5000)))

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
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))  # 5MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Polling intervals (milliseconds) - passed to frontend JavaScript
    POLL_ALERTS = int(os.getenv('POLL_ALERTS', 30000))
    POLL_REQUESTS = int(os.getenv('POLL_REQUESTS', 15000))
    POLL_MESSAGES = int(os.getenv('POLL_MESSAGES', 5000))
    POLL_DASHBOARD = int(os.getenv('POLL_DASHBOARD', 60000))


def allowed_file(filename):
    """Check if file extension is in ALLOWED_EXTENSIONS."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


# ============================================================
# Database Engine Manager (MySQL with Cloud Fallback)
# ============================================================

_use_fallback = False
_fallback_initialized = False
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'sentrygrid_render.db')

class SQLiteDictCursor:
    """Cursor wrapper for SQLite that mimics mysql.connector dictionary cursor."""
    def __init__(self, sqlite_cursor, dictionary=True):
        self.cursor = sqlite_cursor
        self.dictionary = dictionary
        self.lastrowid = None

    def execute(self, query, params=None):
        sql = query
        # Translate MySQL specific SQL syntax for SQLite
        sql = re.sub(r"DATE_SUB\(NOW\(\),\s*INTERVAL\s*(\d+)\s*HOUR\)", r"datetime('now', '-\1 hours')", sql, flags=re.IGNORECASE)
        sql = re.sub(r"DATE_SUB\(NOW\(\),\s*INTERVAL\s*(\d+)\s*DAY\)", r"datetime('now', '-\1 days')", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bNOW\(\)", "datetime('now')", sql, flags=re.IGNORECASE)
        sql = re.sub(r"FIELD\(er\.priority,\s*'Critical',\s*'High',\s*'Medium',\s*'Low'\)",
                     "CASE er.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END", sql, flags=re.IGNORECASE)
        sql = re.sub(r"GROUP_CONCAT\(rt\.team_name\s+SEPARATOR\s+', '\)", "GROUP_CONCAT(rt.team_name, ', ')", sql, flags=re.IGNORECASE)
        sql = sql.replace('%s', '?')

        if params is None:
            self.cursor.execute(sql)
        else:
            converted = [1 if p is True else (0 if p is False else p) for p in params]
            self.cursor.execute(sql, converted)

        self.lastrowid = self.cursor.lastrowid
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row) if self.dictionary else row

    def fetchall(self):
        rows = self.cursor.fetchall()
        if not rows:
            return []
        return [dict(r) for r in rows] if self.dictionary else rows

    def close(self):
        try:
            self.cursor.close()
        except Exception:
            pass


class SQLiteConnectionWrapper:
    """Connection wrapper for SQLite that mimics mysql.connector."""
    def __init__(self, conn):
        self.conn = conn

    def cursor(self, dictionary=False):
        c = self.conn.cursor()
        return SQLiteDictCursor(c, dictionary=dictionary)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def is_connected(self):
        return True


def _init_cloud_schema():
    """Initializes local tables and default records if cloud MySQL is not linked."""
    global _fallback_initialized
    if _fallback_initialized and os.path.exists(SQLITE_DB_PATH):
        return

    conn = sqlite3.connect(SQLITE_DB_PATH)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'citizen',
        phone TEXT, locality TEXT, latitude REAL, longitude REAL,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS disaster_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_by INTEGER NOT NULL, disaster_type TEXT NOT NULL, severity TEXT NOT NULL,
        title TEXT NOT NULL, description TEXT, location TEXT NOT NULL, latitude REAL, longitude REAL,
        safety_instructions TEXT, is_active INTEGER DEFAULT 1, source TEXT DEFAULT 'Manual',
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS emergency_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, citizen_name TEXT NOT NULL, contact_number TEXT NOT NULL,
        emergency_type TEXT NOT NULL, description TEXT, location TEXT, latitude REAL, longitude REAL,
        image_path TEXT, status TEXT DEFAULT 'Reported', priority TEXT DEFAULT 'Medium', is_sos INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS emergency_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL,
        old_status TEXT, new_status TEXT NOT NULL, changed_by INTEGER NOT NULL, notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS response_teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT, team_name TEXT NOT NULL, team_category TEXT NOT NULL,
        team_leader TEXT, member_count INTEGER DEFAULT 0, phone TEXT, status TEXT DEFAULT 'available',
        base_location TEXT, latitude REAL, longitude REAL,
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS team_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL, team_id INTEGER NOT NULL,
        assigned_by INTEGER NOT NULL, assigned_at TEXT DEFAULT (datetime('now')), completed_at TEXT, notes TEXT
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS emergency_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL, sender_id INTEGER NOT NULL,
        message TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS shelters (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, address TEXT NOT NULL,
        latitude REAL NOT NULL, longitude REAL NOT NULL, total_capacity INTEGER NOT NULL,
        current_occupancy INTEGER DEFAULT 0, contact_phone TEXT, contact_email TEXT, is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS shelter_facilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT, shelter_id INTEGER NOT NULL, facility_name TEXT NOT NULL,
        is_available INTEGER DEFAULT 1
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0, unit TEXT NOT NULL, min_threshold INTEGER DEFAULT 10,
        location TEXT, last_restocked TEXT,
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS disaster_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, report_type TEXT NOT NULL,
        disaster_type TEXT, affected_location TEXT, total_affected INTEGER DEFAULT 0,
        missing_persons INTEGER DEFAULT 0, casualties INTEGER DEFAULT 0, description TEXT, generated_by INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    );''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL,
        message TEXT NOT NULL, type TEXT DEFAULT 'info', is_read INTEGER DEFAULT 0, link TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );''')

    # Seed users if empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        from werkzeug.security import generate_password_hash
        c.execute("""
            INSERT INTO users (id, username, email, password_hash, full_name, role, phone, locality, latitude, longitude)
            VALUES (1, 'admin', 'admin@sentrygrid.com', ?, 'System Administrator', 'admin', '9876543210', 'Chennai', 13.0827, 80.2707)
        """, (generate_password_hash('admin123'),))
        c.execute("""
            INSERT INTO users (id, username, email, password_hash, full_name, role, phone, locality, latitude, longitude)
            VALUES (2, 'responder1', 'responder1@sentrygrid.com', ?, 'Rajesh Kumar (Field Captain)', 'responder', '9876543211', 'Chennai', 13.0674, 80.2376)
        """, (generate_password_hash('resp123'),))
        c.execute("""
            INSERT INTO users (id, username, email, password_hash, full_name, role, phone, locality, latitude, longitude)
            VALUES (3, 'citizen1', 'citizen1@sentrygrid.com', ?, 'Priya Sharma', 'citizen', '9876543212', 'Chennai', 13.0524, 80.2508)
        """, (generate_password_hash('citizen123'),))

        # Sample alerts
        c.execute("""
            INSERT INTO disaster_alerts (id, created_by, disaster_type, severity, title, description, location, latitude, longitude, safety_instructions)
            VALUES (1, 1, 'flood', 'Critical', 'Catastrophic Flood Alert – Velachery Sector', 'Continuous 140mm rainfall in last 3 hours. Waterlogged streets exceeding 4 feet.', 'Chennai, Velachery Basin', 12.9815, 80.2180, 'Move to higher floor immediately. Avoid wading through storm drains.')
        """)
        c.execute("""
            INSERT INTO disaster_alerts (id, created_by, disaster_type, severity, title, description, location, latitude, longitude, safety_instructions)
            VALUES (2, 1, 'cyclone', 'High', 'Severe Cyclone Michaung Warning', 'Gale force winds of 85-95 km/h moving towards coastline. Storm surge expected.', 'Chennai, Marina Coast', 13.0500, 80.2824, 'Secure loose exterior objects.')
        """)

        # Sample teams
        c.execute("""
            INSERT INTO response_teams (id, team_name, team_category, team_leader, member_count, phone, status, base_location, latitude, longitude)
            VALUES (1, 'NDRF Unit 4 (Medical Rescue)', 'medical', 'Dr. Arun Varma', 12, '9876543220', 'available', 'Kilpauk Medical Camp', 13.0805, 80.2435)
        """)
        c.execute("""
            INSERT INTO response_teams (id, team_name, team_category, team_leader, member_count, phone, status, base_location, latitude, longitude)
            VALUES (2, 'State Fire & Flood Boat Squad', 'flood_rescue', 'Commander Suresh', 8, '9876543221', 'available', 'Guindy Fire Station', 13.0067, 80.2025)
        """)

        # Sample emergency requests
        c.execute("""
            INSERT INTO emergency_requests (id, user_id, citizen_name, contact_number, emergency_type, description, location, latitude, longitude, status, priority, is_sos)
            VALUES (1, 3, 'Priya Sharma', '9876543212', 'flood_rescue', 'Ground floor submerged by flash flood waters. Elderly couple trapped on first floor balcony.', 'Velachery, 100 Feet Road', 12.9815, 80.2180, 'Dispatched', 'Critical', 1)
        """)
        c.execute("""
            INSERT INTO emergency_requests (id, user_id, citizen_name, contact_number, emergency_type, description, location, latitude, longitude, status, priority, is_sos)
            VALUES (2, 3, 'Karthik Raman', '9876543215', 'medical', 'Severe head trauma from collapsed roof tiles during cyclone gusts.', 'Mylapore, South Mada St', 13.0336, 80.2687, 'Verified', 'High', 0)
        """)

        # Sample shelters
        c.execute("""
            INSERT INTO shelters (id, name, address, latitude, longitude, total_capacity, current_occupancy, contact_phone, contact_email)
            VALUES (1, 'Govt Boys Higher Secondary School Relief Camp', '14 Patel Road, Perambur, Chennai', 13.1118, 80.2335, 450, 120, '044-2551234', 'perambur.camp@disaster.gov.in')
        """)
        c.execute("""
            INSERT INTO shelters (id, name, address, latitude, longitude, total_capacity, current_occupancy, contact_phone, contact_email)
            VALUES (2, 'Anna Community Hall & Safe Haven', 'Anna Nagar West Extension, Chennai', 13.0878, 80.2078, 300, 85, '044-2615432', 'annanagar.camp@disaster.gov.in')
        """)

        # Sample resources
        c.execute("""
            INSERT INTO resources (name, category, quantity, unit, min_threshold, location)
            VALUES ('Packaged Drinking Water (20L Cans)', 'food_water', 450, 'cans', 100, 'Central Logistics Bay 1')
        """)
        c.execute("""
            INSERT INTO resources (name, category, quantity, unit, min_threshold, location)
            VALUES ('Emergency Trauma Bandages & Dressing', 'medical', 15, 'kits', 50, 'Medical Reserve Depot')
        """)

    conn.commit()
    conn.close()
    _fallback_initialized = True


def get_db_connection():
    """
    Returns MySQL database connection when configured.
    Falls back gracefully to localized storage on cloud hosting environments (Render).
    """
    global _use_fallback

    if not _use_fallback:
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                autocommit=False
            )
            return conn
        except Exception as e:
            _use_fallback = True
            print(f"[DB Notice] MySQL connection inactive ({e}). Utilizing auto-seeded cloud storage engine.")

    _init_cloud_schema()
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return SQLiteConnectionWrapper(conn)


def close_db_connection(conn, cursor=None):
    """Safely close database cursor and connection."""
    try:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    except Exception:
        pass
