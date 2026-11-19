"""
SentryGrid – Missing Persons Management Routes (MODULE 3 EXTENSION)
===================================================================
Handles missing person case intake, identity records, search status lifecycle,
and privacy-preserving case tracking.
Demonstrates: REST API, File Uploads, Role-Based Access Control, Privacy Masking.
CSA4310 – Internet Programming
"""

import os
import random
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
from config import Config, get_db_connection, close_db_connection, allowed_file, haversine
from routes.auth import login_required, role_required

missing_persons_bp = Blueprint('missing_persons', __name__)

def format_datetime(val):
    """Safely format datetime object or string to standard timestamp string."""
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val)

VALID_STATUSES = ['Reported', 'Under Review', 'Search Active', 'Located', 'Closed', 'Invalid/Duplicate']


# ============================================================
# GET /api/missing-persons – Search and list missing person cases
# ============================================================

@missing_persons_bp.route('/api/missing-persons', methods=['GET'])
@login_required
def get_missing_persons():
    """
    Search and list missing person cases with privacy masking.
    Query params: status, q (search name/location/desc), lat, lon, limit, offset
    """
    conn = None
    cursor = None
    try:
        status_f = request.args.get('status')
        search_q = request.args.get('q', '').strip()
        user_lat = request.args.get('lat')
        user_lon = request.args.get('lon')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT mp.*, u.full_name as reporter_name, u.role as reporter_role
            FROM missing_persons mp
            LEFT JOIN users u ON mp.reported_by = u.id
            WHERE 1=1
        """
        params = []

        if status_f and status_f in VALID_STATUSES:
            query += " AND mp.status = %s"
            params.append(status_f)

        if search_q:
            term = f"%{search_q}%"
            query += " AND (mp.full_name LIKE %s OR mp.last_seen_location LIKE %s OR mp.description LIKE %s OR mp.case_number LIKE %s)"
            params.extend([term, term, term, term])

        query += " ORDER BY mp.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        cases = cursor.fetchall()

        current_user_id = session.get('user_id')
        current_role = session.get('role')

        # Privacy Masking & Geodesic enrichment
        for c in cases:
            for k in ['created_at', 'updated_at', 'last_seen_date']:
                if c.get(k):
                    c[k] = format_datetime(c[k])

            # Calculate distance if user coords provided
            if user_lat and user_lon and c.get('latitude') and c.get('longitude'):
                c['distance_km'] = haversine(user_lat, user_lon, c['latitude'], c['longitude'])
            else:
                c['distance_km'] = None

            # PRIVACY PROTECTION: Mask contact phone for citizens who are not case owner
            is_privileged = current_role in ('admin', 'responder') or (c.get('reported_by') == current_user_id)
            if not is_privileged and c.get('contact_phone'):
                raw_phone = str(c['contact_phone'])
                if len(raw_phone) > 4:
                    c['contact_phone'] = raw_phone[:3] + '****' + raw_phone[-2:]
                else:
                    c['contact_phone'] = 'Protected'

        # Total counts
        cursor.execute("SELECT COUNT(*) as total FROM missing_persons")
        total = cursor.fetchone()['total']

        return jsonify({'success': True, 'count': len(cases), 'total': total, 'data': cases}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/missing-persons/<id> – Case details
# ============================================================

@missing_persons_bp.route('/api/missing-persons/<int:case_id>', methods=['GET'])
@login_required
def get_missing_person_detail(case_id):
    """Retrieve full details of a single missing-person case."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT mp.*, u.full_name as reporter_name, u.role as reporter_role, u.phone as reporter_phone,
                   er.emergency_type as linked_emergency_type, er.location as linked_emergency_location
            FROM missing_persons mp
            LEFT JOIN users u ON mp.reported_by = u.id
            LEFT JOIN emergency_requests er ON mp.emergency_request_id = er.id
            WHERE mp.id = %s
        """, (case_id,))
        case = cursor.fetchone()

        if not case:
            return jsonify({'success': False, 'message': 'Missing person case record not found.'}), 404

        for k in ['created_at', 'updated_at', 'last_seen_date']:
            if case.get(k):
                case[k] = format_datetime(case[k])

        # Privacy check
        current_user_id = session.get('user_id')
        current_role = session.get('role')
        is_privileged = current_role in ('admin', 'responder') or (case.get('reported_by') == current_user_id)
        if not is_privileged:
            raw_phone = str(case.get('contact_phone', ''))
            if len(raw_phone) > 4:
                case['contact_phone'] = raw_phone[:3] + '****' + raw_phone[-2:]
            else:
                case['contact_phone'] = 'Protected'

        return jsonify({'success': True, 'data': case}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# POST /api/missing-persons – Register new missing person case
# ============================================================

@missing_persons_bp.route('/api/missing-persons', methods=['POST'])
@login_required
def create_missing_person():
    """Register a new missing-person case with optional photo."""
    conn = None
    cursor = None
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        if not data and request.form:
            data = request.form.to_dict()
        data = data or {}

        full_name = data.get('full_name', '').strip()
        last_seen_location = data.get('last_seen_location', '').strip()

        if not full_name or not last_seen_location:
            return jsonify({'success': False, 'message': 'Full name and last-seen location are required.'}), 400

        age = data.get('age')
        age = int(age) if age is not None and str(age).isdigit() else None
        gender = data.get('gender', 'Unknown')
        description = data.get('description', '').strip()
        last_seen_date = data.get('last_seen_date') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        contact_name = data.get('contact_name', session.get('full_name', 'Family Contact')).strip()
        contact_phone = data.get('contact_phone', session.get('phone', '')).strip()

        # GPS Coordinates
        lat = data.get('latitude')
        lon = data.get('longitude')
        lat = float(lat) if lat else None
        lon = float(lon) if lon else None

        # Emergency request link
        er_id = data.get('emergency_request_id')
        er_id = int(er_id) if er_id and str(er_id).isdigit() else None

        # Photo upload handling
        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                fn = secure_filename(f"mp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                save_path = os.path.join(Config.UPLOAD_FOLDER, fn)
                file.save(save_path)
                photo_path = f"/static/uploads/{fn}" if not os.getenv('VERCEL') else f"/tmp/uploads/{fn}"

        # Generate unique case number: MP-2026-XXXX
        case_num = f"MP-{datetime.now().year}-{random.randint(1000, 9999)}"

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            INSERT INTO missing_persons (
                case_number, full_name, age, gender, photo_path, last_seen_date,
                last_seen_location, latitude, longitude, description,
                emergency_request_id, contact_name, contact_phone, status, reported_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Reported', %s)
        """, (
            case_num, full_name, age, gender, photo_path, last_seen_date,
            last_seen_location, lat, lon, description,
            er_id, contact_name, contact_phone, session['user_id']
        ))
        conn.commit()
        case_id = cursor.lastrowid

        # Notify administrators
        cursor.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = TRUE")
        admins = cursor.fetchall()
        for a in admins:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (%s, %s, %s, 'warning', %s)
            """, (a['id'], f"New Missing Person Case: {full_name}",
                  f"Case {case_num} reported in {last_seen_location}. Please review.",
                  f"/missing-persons?id={case_id}"))
        conn.commit()

        return jsonify({
            'success': True,
            'message': f"Case {case_num} filed successfully for {full_name}.",
            'case_id': case_id,
            'case_number': case_num,
            'data': {'id': case_id, 'case_number': case_num}
        }), 201

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# PUT /api/missing-persons/<id>/status – Update case lifecycle
# ============================================================

@missing_persons_bp.route('/api/missing-persons/<int:case_id>/status', methods=['PUT'])
@login_required
def update_missing_person_status(case_id):
    """
    Update case status workflow.
    Allowed roles: admin, responder (or case owner can close/resolve).
    """
    conn = None
    cursor = None
    try:
        data = request.get_json() or {}
        new_status = data.get('status')
        notes = data.get('notes', '').strip()

        if not new_status or new_status not in VALID_STATUSES:
            return jsonify({'success': False, 'message': f'Invalid status. Allowed: {", ".join(VALID_STATUSES)}'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM missing_persons WHERE id = %s", (case_id,))
        case = cursor.fetchone()
        if not case:
            return jsonify({'success': False, 'message': 'Case not found.'}), 404

        current_role = session.get('role')
        current_user = session.get('user_id')

        # Role validation
        if current_role not in ('admin', 'responder') and case['reported_by'] != current_user:
            return jsonify({'success': False, 'message': 'Access denied. Only rescue officials or the case reporter can update status.'}), 403

        cursor.execute("""
            UPDATE missing_persons SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s
        """, (new_status, case_id))
        conn.commit()

        # Send notification to the reporter
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (%s, %s, %s, 'info', %s)
        """, (
            case['reported_by'],
            f"Update on Case {case['case_number']}",
            f"Case status changed from {case['status']} to {new_status}. {notes}",
            f"/missing-persons?id={case_id}"
        ))
        conn.commit()

        return jsonify({
            'success': True,
            'message': f"Case {case['case_number']} status updated to {new_status}.",
            'case_id': case_id,
            'new_status': new_status
        }), 200

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/missing-persons/stats – KPI summary counts
# ============================================================

@missing_persons_bp.route('/api/missing-persons/stats', methods=['GET'])
@login_required
def get_missing_person_stats():
    """Retrieve statistical counters for missing persons."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) as total FROM missing_persons")
        total = cursor.fetchone()['total']

        cursor.execute("""
            SELECT status, COUNT(*) as c FROM missing_persons GROUP BY status
        """)
        by_status = {r['status']: r['c'] for r in cursor.fetchall()}

        active_searches = by_status.get('Search Active', 0) + by_status.get('Under Review', 0) + by_status.get('Reported', 0)
        located = by_status.get('Located', 0)

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'active_searches': active_searches,
                'located': located,
                'by_status': by_status
            }
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
