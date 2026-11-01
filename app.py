"""
SentryGrid – Main Application Entry Point
==========================================
Real-Time Disaster Alert and Emergency Response Web Application
CSA4310 – Internet Programming

This file initializes the Flask application, registers all route blueprints,
and provides the setup endpoint for creating default database records.
"""

import os
from flask import Flask, render_template, session, redirect, url_for, jsonify, request
from werkzeug.security import generate_password_hash
from config import Config, get_db_connection, close_db_connection

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# Register Route Blueprints (modular route organization)
# ============================================================
from routes.auth import auth_bp
from routes.alerts import alerts_bp
from routes.emergencies import emergencies_bp
from routes.teams import teams_bp
from routes.shelters import shelters_bp
from routes.resources import resources_bp
from routes.reports import reports_bp
from routes.messages import messages_bp

app.register_blueprint(auth_bp)
app.register_blueprint(alerts_bp)
app.register_blueprint(emergencies_bp)
app.register_blueprint(teams_bp)
app.register_blueprint(shelters_bp)
app.register_blueprint(resources_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(messages_bp)


# ============================================================
# Page Routes – Serve HTML templates
# ============================================================

@app.route('/')
def index():
    """Redirect to login page or dashboard based on session."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    """Serve the login/register page."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    """Serve the main dashboard (role-specific content loaded via AJAX)."""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', 
                         user=session,
                         config=Config)


@app.route('/alerts')
def alerts_page():
    """Serve the disaster alerts page (Module 1)."""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('alerts.html', user=session, config=Config)


@app.route('/emergencies')
def emergencies_page():
    """Serve the emergency requests page (Module 2)."""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('emergencies.html', user=session, config=Config)


@app.route('/shelters')
def shelters_page():
    """Serve the shelters page (Module 3)."""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('shelters.html', user=session, config=Config)


@app.route('/teams')
def teams_page():
    """Serve the response teams management page."""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    if session.get('role') not in ['admin', 'responder']:
        return redirect(url_for('dashboard'))
    return render_template('teams.html', user=session, config=Config)


@app.route('/resources')
def resources_page():
    """Serve the resource management page."""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('resources.html', user=session, config=Config)


# ============================================================
# Setup Endpoint – Create default users and sample data
# ============================================================

@app.route('/api/setup', methods=['POST'])
def setup_database():
    """
    Create default user accounts with properly hashed passwords.
    Run this once after setting up the database schema.
    
    Default accounts created:
    - admin / admin123 (Administrator)
    - responder1 / resp123 (Emergency Responder)
    - citizen1 / citizen123 (Citizen)
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if users already exist
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count > 0:
            return jsonify({
                'success': False,
                'message': 'Users already exist. Setup has already been run.'
            }), 400
        
        # Default users with hashed passwords
        default_users = [
            ('admin', 'admin@sentrygrid.com', generate_password_hash('admin123'),
             'System Administrator', 'admin', '9876543210', 'Chennai', 13.0827, 80.2707),
            ('responder1', 'responder1@sentrygrid.com', generate_password_hash('resp123'),
             'Rajesh Kumar', 'responder', '9876543211', 'Chennai', 13.0674, 80.2376),
            ('citizen1', 'citizen1@sentrygrid.com', generate_password_hash('citizen123'),
             'Priya Sharma', 'citizen', '9876543212', 'Chennai', 13.0524, 80.2508),
        ]
        
        insert_query = """
            INSERT INTO users (username, email, password_hash, full_name, role, 
                             phone, locality, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        for user in default_users:
            cursor.execute(insert_query, user)
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Default users created successfully.',
            'users': [
                {'username': 'admin', 'password': 'admin123', 'role': 'Administrator'},
                {'username': 'responder1', 'password': 'resp123', 'role': 'Emergency Responder'},
                {'username': 'citizen1', 'password': 'citizen123', 'role': 'Citizen'}
            ]
        }), 201
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# Error Handlers
# ============================================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors – return JSON for API routes, redirect otherwise."""
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Endpoint not found'}), 404
    return redirect(url_for('login_page'))


@app.errorhandler(413)
def file_too_large(e):
    """Handle file upload size limit exceeded."""
    return jsonify({'success': False, 'message': 'File too large. Maximum size is 5MB.'}), 413


@app.errorhandler(500)
def server_error(e):
    """Handle internal server errors."""
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
    return render_template('login.html'), 500


# ============================================================
# Run the Application
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  SentryGrid – Disaster Alert & Emergency Response System")
    print("  Starting server on http://localhost:{}".format(Config.PORT))
    print("=" * 60)
    app.run(debug=Config.DEBUG, port=Config.PORT, host='0.0.0.0')
