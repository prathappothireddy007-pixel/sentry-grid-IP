"""
SentryGrid – Emergency Messages Routes
=========================================
Communication between citizens and responders on emergency requests.
Demonstrates: AJAX polling, POST, JSON, real-time-like messaging.
"""

from flask import Blueprint, request, jsonify, session
from config import get_db_connection, close_db_connection
from routes.auth import login_required

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/api/requests/<int:request_id>/messages', methods=['GET'])
@login_required
def get_messages(request_id):
    """
    Get messages for an emergency request.
    Query params: after (timestamp) – for polling only new messages.
    """
    conn = None
    cursor = None
    try:
        after = request.args.get('after')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verify request exists
        cursor.execute("SELECT id, user_id FROM emergency_requests WHERE id=%s", (request_id,))
        req = cursor.fetchone()
        if not req:
            return jsonify({'success': False, 'message': 'Request not found.'}), 404

        # Citizens can only see messages on their own requests
        if session.get('role') == 'citizen' and req['user_id'] != session['user_id']:
            return jsonify({'success': False, 'message': 'Access denied.'}), 403

        query = """
            SELECT m.*, u.full_name as sender_name, u.role as sender_role
            FROM emergency_messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.request_id = %s
        """
        params = [request_id]

        if after:
            query += " AND m.created_at > %s"
            params.append(after)

        query += " ORDER BY m.created_at ASC"
        cursor.execute(query, params)
        messages = cursor.fetchall()

        for m in messages:
            if m.get('created_at'):
                m['created_at'] = m['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({'success': True, 'data': messages}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@messages_bp.route('/api/requests/<int:request_id>/messages', methods=['POST'])
@login_required
def send_message(request_id):
    """Send a message on an emergency request. JSON: {message}"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data or not data.get('message', '').strip():
            return jsonify({'success': False, 'message': 'Message content is required.'}), 400

        message_text = data['message'].strip()
        if len(message_text) > 2000:
            return jsonify({'success': False, 'message': 'Message too long (max 2000 chars).'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verify request
        cursor.execute("SELECT id, user_id FROM emergency_requests WHERE id=%s", (request_id,))
        req = cursor.fetchone()
        if not req:
            return jsonify({'success': False, 'message': 'Request not found.'}), 404

        if session.get('role') == 'citizen' and req['user_id'] != session['user_id']:
            return jsonify({'success': False, 'message': 'Access denied.'}), 403

        cursor.execute("""
            INSERT INTO emergency_messages (request_id, sender_id, message)
            VALUES (%s, %s, %s)
        """, (request_id, session['user_id'], message_text))

        msg_id = cursor.lastrowid
        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Message sent.',
            'data': {
                'id': msg_id,
                'sender_name': session['full_name'],
                'sender_role': session['role'],
                'message': message_text
            }
        }), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
