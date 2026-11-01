"""
SentryGrid – Database Initialization Script
============================================
Executes schema.sql and sample_data.sql on MySQL 8.0,
and creates default test user accounts with securely hashed passwords.
CSA4310 – Internet Programming

Usage:
    python init_db.py
"""

import os
import re
import sys
import mysql.connector
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'NewPassword123')
DB_NAME = os.getenv('DB_NAME', 'sentrygrid_db')

def remove_comments(sql):
    """Remove SQL comments while preserving query structure."""
    lines = []
    for line in sql.splitlines():
        trimmed = line.strip()
        if trimmed.startswith('--') or trimmed.startswith('/*') or trimmed.startswith('*'):
            continue
        # Also remove inline comments like `-- comment`
        if '--' in line:
            line = line.split('--')[0]
        lines.append(line)
    return '\n'.join(lines)

def init_database():
    print("=" * 65)
    print("  SentryGrid Database Initialization")
    print(f"  Target: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("=" * 65)

    try:
        # Step 1: Connect to MySQL Server (without selecting database yet)
        print("\n[1/4] Connecting to MySQL server...")
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True
        )
        cursor = conn.cursor()
        print("  [OK] Connected to MySQL 8.0 successfully!")

        # Step 2: Create database and select it
        print("\n[2/4] Initializing database and 12 relational tables...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE {DB_NAME};")
        conn.database = DB_NAME

        schema_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            raw_schema = f.read()

        clean_schema = remove_comments(raw_schema)
        statements = clean_schema.split(';')
        executed_tables = 0
        for stmt in statements:
            cleaned = stmt.strip()
            if not cleaned:
                continue
            if cleaned.upper().startswith('CREATE DATABASE') or cleaned.upper().startswith('USE '):
                continue
            try:
                cursor.execute(cleaned)
                if 'CREATE TABLE' in cleaned.upper():
                    executed_tables += 1
            except mysql.connector.Error as e:
                print(f"  Schema note: {e}")

        print(f"  [OK] Database {DB_NAME} initialized with {executed_tables} tables.")

        # Step 3: Insert default users with hashed passwords
        print("\n[3/4] Creating default user accounts with secure password hashes...")
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        if user_count == 0:
            default_users = [
                ('admin', 'admin@sentrygrid.com', generate_password_hash('admin123'),
                 'System Administrator', 'admin', '9876543210', 'Chennai', 13.0827, 80.2707),
                ('responder1', 'responder1@sentrygrid.com', generate_password_hash('resp123'),
                 'Rajesh Kumar (Field Captain)', 'responder', '9876543211', 'Chennai', 13.0674, 80.2376),
                ('citizen1', 'citizen1@sentrygrid.com', generate_password_hash('citizen123'),
                 'Priya Sharma', 'citizen', '9876543212', 'Chennai', 13.0524, 80.2508),
            ]

            insert_user_query = """
                INSERT INTO users (username, email, password_hash, full_name, role,
                                 phone, locality, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            for u in default_users:
                cursor.execute(insert_user_query, u)
            print("  [OK] Created default accounts:")
            print("       - Administrator:       admin / admin123")
            print("       - Emergency Responder:  responder1 / resp123")
            print("       - Citizen:              citizen1 / citizen123")
        else:
            print(f"  [INFO] Users already populated ({user_count} records).")

        # Step 4: Execute sample data
        print("\n[4/4] Inserting sample demonstration data (sample_data.sql)...")
        sample_path = os.path.join(os.path.dirname(__file__), 'database', 'sample_data.sql')
        with open(sample_path, 'r', encoding='utf-8') as f:
            raw_sample = f.read()

        clean_sample = remove_comments(raw_sample)
        sample_stmts = clean_sample.split(';')
        inserted_items = 0
        for stmt in sample_stmts:
            cleaned = stmt.strip()
            if not cleaned or cleaned.upper().startswith('USE '):
                continue
            try:
                cursor.execute(cleaned)
                if cleaned.upper().startswith('INSERT'):
                    inserted_items += 1
            except mysql.connector.Error as err:
                if err.errno != 1062:  # ignore duplicate key
                    print(f"  Sample data note: {err}")

        print(f"  [OK] Inserted {inserted_items} demonstration alert, rescue, shelter, and resource records.")

        cursor.close()
        conn.close()

        print("\n" + "=" * 65)
        print("  SentryGrid Database Successfully Initialized on MySQL 8.0!")
        print("  Database Name: sentrygrid_db")
        print("=" * 65)
        return True

    except mysql.connector.Error as err:
        print(f"\n[ERROR] MySQL Error [{err.errno}]: {err.msg}")
        return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
