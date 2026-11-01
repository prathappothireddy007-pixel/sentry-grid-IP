"""
SentryGrid – Authentication Routes
====================================
Handles user registration, login, logout, and session management.
Demonstrates: HTML Forms, POST requests, JSON responses, password hashing, sessions.
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re
from config import get_db_connection, close_db_connection

# Create Blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)


# ============================================================
# Role-Based Access Control Decorators
# ============================================================

def login_required(f):
    """
    Decorator to protect routes that require authentication.
    Checks if user_id exists in the Flask session.
    Returns 401 JSON response if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': 'Authentication required. Please log in.'
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """
    Decorator to restrict access based on user role.
    Usage: @role_required('admin') or @role_required('admin', 'responder')
    Returns 403 JSON response if user role is not in the allowed list.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({
                    'success': False,
                    'message': 'Authentication required. Please log in.'
                }), 401
            if session.get('role') not in roles:
                return jsonify({
                    'success': False,
                    'message': 'Access denied. Insufficient permissions.'
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================
# POST /api/register – Create a new user account
# ============================================================

@auth_bp.route('/api/register', methods=['POST'])
def register():
    """
    Register a new user account.
    Expected JSON: {username, email, password, full_name, role, phone, locality, latitude, longitude}
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body is required.'}), 400

        # --- Input Validation ---
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'citizen').strip()
        phone = data.get('phone', '').strip()
        locality = data.get('locality', '').strip()
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        errors = []
        if not username or len(username) < 3 or len(username) > 50:
            errors.append('Username must be 3-50 characters.')
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Valid email address is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if not full_name:
            errors.append('Full name is required.')
        if role not in ('citizen', 'responder'):
            errors.append('Role must be citizen or responder.')

        if errors:
            return jsonify({'success': False, 'message': ' '.join(errors)}), 400

        # --- Database Operation ---
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check uniqueness
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Username already exists.'}), 409

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Email already registered.'}), 409

        # Hash password and insert user
        password_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role,
                             phone, locality, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            username, email, password_hash, full_name, role,
            phone or None, locality or None,
            float(latitude) if latitude else None,
            float(longitude) if longitude else None
        ))
        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Registration successful! You can now log in.',
            'data': {'username': username, 'role': role}
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': f'Registration failed: {str(e)}'}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# POST /api/login – Authenticate user and create session
# ============================================================

@auth_bp.route('/api/login', methods=['POST'])
def login():
    """
    Authenticate a user and create a server-side session.
    Expected JSON: {username, password}
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body is required.'}), 400

        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, username, email, password_hash, full_name, role,
                   phone, locality, latitude, longitude, is_active
            FROM users WHERE username = %s
        """, (username,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401

        if not user['is_active']:
            return jsonify({'success': False, 'message': 'Account is deactivated. Contact admin.'}), 403

        if not check_password_hash(user['password_hash'], password):
            return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401

        # Store user info in Flask session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['full_name'] = user['full_name']
        session['email'] = user['email']
        session['role'] = user['role']
        session['phone'] = user['phone']
        session['locality'] = user['locality']
        session['latitude'] = float(user['latitude']) if user['latitude'] else None
        session['longitude'] = float(user['longitude']) if user['longitude'] else None

        return jsonify({
            'success': True,
            'message': f'Welcome back, {user["full_name"]}!',
            'data': {
                'user_id': user['id'],
                'username': user['username'],
                'full_name': user['full_name'],
                'role': user['role'],
                'locality': user['locality']
            }
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Login failed: {str(e)}'}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# POST /api/logout – Destroy user session
# ============================================================

@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """Log out the current user by clearing the session."""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'}), 200


# ============================================================
# GET /api/session – Return current session info
# ============================================================

@auth_bp.route('/api/session', methods=['GET'])
def get_session():
    """Return current user session information for the frontend."""
    if 'user_id' in session:
        return jsonify({
            'success': True,
            'data': {
                'user_id': session['user_id'],
                'username': session['username'],
                'full_name': session['full_name'],
                'role': session['role'],
                'locality': session.get('locality'),
                'latitude': session.get('latitude'),
                'longitude': session.get('longitude')
            }
        }), 200
    return jsonify({'success': False, 'message': 'Not authenticated'}), 401


# ============================================================
# PUT /api/profile – Update user profile
# ============================================================

@auth_bp.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update the current user's profile information."""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body is required.'}), 400

        updates = []
        values = []

        for field in ['full_name', 'phone', 'locality']:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(data[field].strip() if data[field] else None)
        for field in ['latitude', 'longitude']:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(float(data[field]) if data[field] else None)

        if not updates:
            return jsonify({'success': False, 'message': 'No fields to update.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        values.append(session['user_id'])
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", values)
        conn.commit()

        # Update session data
        for field in ['full_name', 'phone', 'locality']:
            if field in data:
                session[field] = data[field].strip() if data[field] else None
        for field in ['latitude', 'longitude']:
            if field in data:
                session[field] = float(data[field]) if data[field] else None

        return jsonify({'success': True, 'message': 'Profile updated successfully.'}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': f'Update failed: {str(e)}'}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/notifications – Get user notifications
# ============================================================

@auth_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get notifications for the current user."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        unread_only = request.args.get('unread', 'false').lower() == 'true'
        limit = min(int(request.args.get('limit', 20)), 50)

        query = "SELECT * FROM notifications WHERE user_id = %s"
        params = [session['user_id']]

        if unread_only:
            query += " AND is_read = FALSE"

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        notifications = cursor.fetchall()

        for n in notifications:
            if n.get('created_at'):
                n['created_at'] = n['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        # Unread count
        cursor.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = FALSE",
            (session['user_id'],)
        )
        unread_count = cursor.fetchone()['count']

        return jsonify({
            'success': True,
            'data': notifications,
            'unread_count': unread_count
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# PUT /api/notifications/<id>/read – Mark notification as read
# ============================================================

@auth_bp.route('/api/notifications/<int:notif_id>/read', methods=['PUT'])
@login_required
def mark_notification_read(notif_id):
    """Mark a notification as read."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s",
            (notif_id, session['user_id'])
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Notification marked as read.'}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
