"""
SentryGrid – Emergency Request Routes (MODULE 2)
===================================================
Emergency Reporting and Rescue Coordination.
Handles emergency submissions, SOS, status workflow, and team coordination.
Demonstrates: Forms, FormData, POST/PUT, Geolocation, AJAX, JSON, file upload.
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from config import Config, get_db_connection, close_db_connection, allowed_file
from routes.auth import login_required, role_required

emergencies_bp = Blueprint('emergencies', __name__)

# Enforces the status workflow
VALID_TRANSITIONS = {
    'Reported': ['Verified'],
    'Verified': ['Dispatched'],
    'Dispatched': ['Rescued'],
    'Rescued': ['Closed'],
    'Closed': []
}


# ============================================================
# GET /api/requests – List emergency requests
# ============================================================

@emergencies_bp.route('/api/requests', methods=['GET'])
@login_required
def get_requests():
    """
    List emergency requests with role-based filtering.
    Citizens see own, responders see assigned+unassigned, admins see all.
    Query: status, type, priority, search, limit, offset
    """
    conn = None
    cursor = None
    try:
        status_f = request.args.get('status')
        etype = request.args.get('type')
        priority = request.args.get('priority')
        search = request.args.get('search', '').strip()
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT er.*, u.full_name as submitter_name, u.phone as submitter_phone,
                   (SELECT GROUP_CONCAT(rt.team_name SEPARATOR ', ')
                    FROM team_assignments ta
                    JOIN response_teams rt ON ta.team_id = rt.id
                    WHERE ta.request_id = er.id) as assigned_teams
            FROM emergency_requests er
            LEFT JOIN users u ON er.user_id = u.id
            WHERE 1=1
        """
        params = []

        role = session.get('role')
        if role == 'citizen':
            query += " AND er.user_id = %s"
            params.append(session['user_id'])
        elif role == 'responder':
            query += """ AND (er.id IN (
                SELECT ta.request_id FROM team_assignments ta
            ) OR er.status IN ('Reported', 'Verified'))"""

        if status_f:
            query += " AND er.status = %s"
            params.append(status_f)
        if etype:
            query += " AND er.emergency_type = %s"
            params.append(etype)
        if priority:
            query += " AND er.priority = %s"
            params.append(priority)
        if search:
            st = f"%{search}%"
            query += " AND (er.citizen_name LIKE %s OR er.description LIKE %s OR er.location LIKE %s)"
            params.extend([st, st, st])

        query += " ORDER BY FIELD(er.priority,'Critical','High','Medium','Low'), er.created_at DESC"
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        results = cursor.fetchall()

        for r in results:
            for k in ['created_at', 'updated_at']:
                if r.get(k):
                    r[k] = r[k].strftime('%Y-%m-%d %H:%M:%S')
            for k in ['latitude', 'longitude']:
                if r.get(k):
                    r[k] = float(r[k])

        count_q = "SELECT COUNT(*) as total FROM emergency_requests WHERE 1=1"
        cp = []
        if role == 'citizen':
            count_q += " AND user_id = %s"
            cp.append(session['user_id'])
        cursor.execute(count_q, cp)
        total = cursor.fetchone()['total']

        return jsonify({'success': True, 'data': results, 'total': total}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/requests/<id> – Single request with history
# ============================================================

@emergencies_bp.route('/api/requests/<int:request_id>', methods=['GET'])
@login_required
def get_request_detail(request_id):
    """Get a single emergency request with status history and team assignments."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT er.*, u.full_name as submitter_name, u.phone as submitter_phone
            FROM emergency_requests er
            LEFT JOIN users u ON er.user_id = u.id WHERE er.id = %s
        """, (request_id,))
        req = cursor.fetchone()
        if not req:
            return jsonify({'success': False, 'message': 'Request not found.'}), 404

        if session.get('role') == 'citizen' and req['user_id'] != session['user_id']:
            return jsonify({'success': False, 'message': 'Access denied.'}), 403

        # Status history
        cursor.execute("""
            SELECT esh.*, u.full_name as changed_by_name
            FROM emergency_status_history esh
            LEFT JOIN users u ON esh.changed_by = u.id
            WHERE esh.request_id = %s ORDER BY esh.created_at ASC
        """, (request_id,))
        history = cursor.fetchall()

        # Assigned teams
        cursor.execute("""
            SELECT ta.*, rt.team_name, rt.team_category, rt.phone as team_phone,
                   u.full_name as assigned_by_name
            FROM team_assignments ta
            JOIN response_teams rt ON ta.team_id = rt.id
            LEFT JOIN users u ON ta.assigned_by = u.id
            WHERE ta.request_id = %s
        """, (request_id,))
        teams = cursor.fetchall()

        # Serialize
        for k in ['created_at', 'updated_at']:
            if req.get(k): req[k] = req[k].strftime('%Y-%m-%d %H:%M:%S')
        for k in ['latitude', 'longitude']:
            if req.get(k): req[k] = float(req[k])
        for h in history:
            if h.get('created_at'): h['created_at'] = h['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        for t in teams:
            for k in ['assigned_at', 'completed_at']:
                if t.get(k): t[k] = t[k].strftime('%Y-%m-%d %H:%M:%S')

        req['status_history'] = history
        req['assigned_teams'] = teams

        return jsonify({'success': True, 'data': req}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# POST /api/requests – Submit emergency request
# ============================================================

@emergencies_bp.route('/api/requests', methods=['POST'])
@login_required
def create_request():
    """
    Submit a new emergency request. Accepts JSON or FormData (for image upload).
    Fields: citizen_name, contact_number, emergency_type, description, location,
            latitude, longitude, priority, is_sos, image (file)
    """
    conn = None
    cursor = None
    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.form.to_dict()
        else:
            data = request.get_json() or {}

        citizen_name = data.get('citizen_name', '').strip()
        contact_number = data.get('contact_number', '').strip()
        emergency_type = data.get('emergency_type', '').strip()
        description = data.get('description', '').strip()
        location = data.get('location', '').strip()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        priority = data.get('priority', 'Medium').strip()
        is_sos = str(data.get('is_sos', 'false')).lower() in ('true', '1', 'yes')

        valid_types = ['medical', 'fire', 'flood_rescue', 'trapped', 'other']
        errors = []
        if not citizen_name: errors.append('Citizen name is required.')
        if not contact_number: errors.append('Contact number is required.')
        if emergency_type not in valid_types:
            errors.append(f'Emergency type must be: {", ".join(valid_types)}')
        if not description and not is_sos: errors.append('Description is required.')
        if errors:
            return jsonify({'success': False, 'message': ' '.join(errors)}), 400

        # Handle image upload via FormData
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                fn = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                fp = os.path.join(Config.UPLOAD_FOLDER, fn)
                file.save(fp)
                image_path = fp

        if is_sos:
            priority = 'Critical'
            if not description:
                description = 'SOS Emergency Alert – Immediate assistance required!'

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            INSERT INTO emergency_requests
            (user_id, citizen_name, contact_number, emergency_type, description,
             location, latitude, longitude, image_path, status, priority, is_sos)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Reported',%s,%s)
        """, (
            session['user_id'], citizen_name, contact_number, emergency_type,
            description, location or None,
            float(latitude) if latitude else None,
            float(longitude) if longitude else None,
            image_path, priority, is_sos
        ))
        rid = cursor.lastrowid

        # Status history
        cursor.execute("""
            INSERT INTO emergency_status_history (request_id, old_status, new_status, changed_by, notes)
            VALUES (%s, NULL, 'Reported', %s, %s)
        """, (rid, session['user_id'],
              'SOS Emergency Alert submitted' if is_sos else 'Emergency request submitted'))

        # Notify admins
        cursor.execute("SELECT id FROM users WHERE role='admin' AND is_active=TRUE")
        label = '🆘 SOS ALERT' if is_sos else '🚨 New Emergency'
        for admin in cursor.fetchall():
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (%s,%s,%s,'emergency',%s)
            """, (admin['id'], f"{label}: {emergency_type.replace('_',' ').title()}",
                  f"{citizen_name} reported a {emergency_type.replace('_',' ')} at {location or 'Unknown'}.",
                  f"/emergencies?id={rid}"))

        conn.commit()
        msg = 'SOS Alert sent! Help is on the way.' if is_sos else 'Emergency request submitted successfully!'
        return jsonify({'success': True, 'message': msg, 'data': {'id': rid, 'status': 'Reported'}}), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# PUT /api/requests/<id>/status – Update status (workflow)
# ============================================================

@emergencies_bp.route('/api/requests/<int:request_id>/status', methods=['PUT'])
@role_required('admin', 'responder')
def update_request_status(request_id):
    """
    Update emergency request status. Enforces:
    Reported → Verified → Dispatched → Rescued → Closed
    JSON: {status, notes}
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required.'}), 400

        new_status = data.get('status', '').strip()
        notes = data.get('notes', '').strip()

        all_statuses = ['Reported', 'Verified', 'Dispatched', 'Rescued', 'Closed']
        if new_status not in all_statuses:
            return jsonify({'success': False, 'message': 'Invalid status.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, status, user_id FROM emergency_requests WHERE id=%s", (request_id,))
        req = cursor.fetchone()
        if not req:
            return jsonify({'success': False, 'message': 'Request not found.'}), 404

        old_status = req['status']
        if new_status not in VALID_TRANSITIONS.get(old_status, []):
            valid = ', '.join(VALID_TRANSITIONS.get(old_status, ['None']))
            return jsonify({'success': False,
                            'message': f'Cannot change {old_status} → {new_status}. Valid: {valid}'}), 400

        if new_status in ['Verified', 'Closed'] and session.get('role') != 'admin':
            return jsonify({'success': False, 'message': f'Only admins can set {new_status}.'}), 403

        cursor.execute("UPDATE emergency_requests SET status=%s WHERE id=%s", (new_status, request_id))

        cursor.execute("""
            INSERT INTO emergency_status_history (request_id, old_status, new_status, changed_by, notes)
            VALUES (%s,%s,%s,%s,%s)
        """, (request_id, old_status, new_status, session['user_id'], notes or None))

        # Free teams on rescue completion
        if new_status in ('Rescued', 'Closed'):
            cursor.execute("UPDATE team_assignments SET completed_at=NOW() WHERE request_id=%s AND completed_at IS NULL", (request_id,))
            cursor.execute("""
                UPDATE response_teams SET status='available'
                WHERE id IN (SELECT team_id FROM team_assignments WHERE request_id=%s)
            """, (request_id,))

        # Notify citizen
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (%s,%s,%s,'info',%s)
        """, (req['user_id'], f"Request #{request_id} Status Update",
              f"Status changed: {old_status} → {new_status}.", f"/emergencies?id={request_id}"))

        conn.commit()
        return jsonify({
            'success': True, 'message': f'Status updated to {new_status}.',
            'data': {'id': request_id, 'old_status': old_status, 'new_status': new_status}
        }), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# POST /api/requests/<id>/assign – Assign team (Admin)
# ============================================================

@emergencies_bp.route('/api/requests/<int:request_id>/assign', methods=['POST'])
@role_required('admin')
def assign_team(request_id):
    """
    Assign a response team to an emergency request.
    Auto-transitions Verified → Dispatched. JSON: {team_id, notes}
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data or not data.get('team_id'):
            return jsonify({'success': False, 'message': 'team_id is required.'}), 400

        team_id = int(data['team_id'])
        notes = data.get('notes', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, status, user_id FROM emergency_requests WHERE id=%s", (request_id,))
        req = cursor.fetchone()
        if not req:
            return jsonify({'success': False, 'message': 'Request not found.'}), 404
        if req['status'] in ('Rescued', 'Closed'):
            return jsonify({'success': False, 'message': 'Cannot assign to resolved request.'}), 400

        cursor.execute("SELECT id, team_name, status FROM response_teams WHERE id=%s", (team_id,))
        team = cursor.fetchone()
        if not team:
            return jsonify({'success': False, 'message': 'Team not found.'}), 404
        if team['status'] != 'available':
            return jsonify({'success': False, 'message': f'{team["team_name"]} is {team["status"]}.'}), 400

        cursor.execute("SELECT id FROM team_assignments WHERE request_id=%s AND team_id=%s AND completed_at IS NULL",
                       (request_id, team_id))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Team already assigned.'}), 409

        cursor.execute("INSERT INTO team_assignments (request_id,team_id,assigned_by,notes) VALUES(%s,%s,%s,%s)",
                       (request_id, team_id, session['user_id'], notes or None))
        cursor.execute("UPDATE response_teams SET status='deployed' WHERE id=%s", (team_id,))

        old_status = req['status']
        if old_status == 'Verified':
            cursor.execute("UPDATE emergency_requests SET status='Dispatched' WHERE id=%s", (request_id,))
            cursor.execute("""
                INSERT INTO emergency_status_history (request_id,old_status,new_status,changed_by,notes)
                VALUES(%s,%s,'Dispatched',%s,%s)
            """, (request_id, old_status, session['user_id'], f'Team {team["team_name"]} dispatched'))

            cursor.execute("""
                INSERT INTO notifications (user_id,title,message,type,link)
                VALUES(%s,%s,%s,'success',%s)
            """, (req['user_id'], f"Help dispatched! Request #{request_id}",
                  f"Team '{team['team_name']}' is on the way.", f"/emergencies?id={request_id}"))

        conn.commit()
        return jsonify({
            'success': True, 'message': f'Team "{team["team_name"]}" assigned.',
            'data': {'request_id': request_id, 'team_id': team_id, 'team_name': team['team_name']}
        }), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/requests/stats – Emergency statistics
# ============================================================

@emergencies_bp.route('/api/requests/stats', methods=['GET'])
@login_required
def get_request_stats():
    """Get emergency request statistics for the dashboard."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT status, COUNT(*) as c FROM emergency_requests GROUP BY status")
        by_status = {r['status']: r['c'] for r in cursor.fetchall()}

        cursor.execute("SELECT emergency_type, COUNT(*) as c FROM emergency_requests GROUP BY emergency_type")
        by_type = {r['emergency_type']: r['c'] for r in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) as c FROM emergency_requests WHERE is_sos=TRUE")
        sos = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) as c FROM emergency_requests WHERE status NOT IN ('Rescued','Closed')")
        pending = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) as c FROM emergency_requests")
        total = cursor.fetchone()['c']

        return jsonify({
            'success': True,
            'data': {'total': total, 'pending': pending, 'sos_count': sos,
                     'by_status': by_status, 'by_type': by_type}
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
