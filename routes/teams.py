"""
SentryGrid – Response Teams Routes
=====================================
Manages response teams: CRUD, availability tracking.
"""

from flask import Blueprint, request, jsonify, session
from config import get_db_connection, close_db_connection
from routes.auth import login_required, role_required

teams_bp = Blueprint('teams', __name__)

def format_datetime(val):
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val)


@teams_bp.route('/api/teams', methods=['GET'])
@login_required
def get_teams():
    """List all response teams with optional status filter."""
    conn = None
    cursor = None
    try:
        status = request.args.get('status')
        category = request.args.get('category')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM response_teams WHERE 1=1"
        params = []
        if status:
            query += " AND status = %s"
            params.append(status)
        if category:
            query += " AND team_category = %s"
            params.append(category)
        query += " ORDER BY team_name"

        cursor.execute(query, params)
        teams = cursor.fetchall()
        for t in teams:
            for k in ['created_at', 'updated_at']:
                if t.get(k): t[k] = format_datetime(t[k])
            for k in ['latitude', 'longitude']:
                if t.get(k): t[k] = float(t[k])

        return jsonify({'success': True, 'data': teams}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@teams_bp.route('/api/teams', methods=['POST'])
@role_required('admin')
def create_team():
    """Create a new response team. Admin only. JSON: {team_name, team_category, team_leader, member_count, phone, base_location, latitude, longitude}"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required.'}), 400

        team_name = data.get('team_name', '').strip()
        team_category = data.get('team_category', '').strip()
        valid_cats = ['medical', 'fire', 'flood_rescue', 'search_rescue', 'general']

        if not team_name:
            return jsonify({'success': False, 'message': 'Team name is required.'}), 400
        if team_category not in valid_cats:
            return jsonify({'success': False, 'message': f'Category must be: {", ".join(valid_cats)}'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO response_teams (team_name, team_category, team_leader, member_count, phone, base_location, latitude, longitude)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            team_name, team_category,
            data.get('team_leader', '').strip() or None,
            int(data.get('member_count', 0)),
            data.get('phone', '').strip() or None,
            data.get('base_location', '').strip() or None,
            float(data['latitude']) if data.get('latitude') else None,
            float(data['longitude']) if data.get('longitude') else None
        ))
        tid = cursor.lastrowid
        conn.commit()
        return jsonify({'success': True, 'message': 'Team created.', 'data': {'id': tid}}), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@teams_bp.route('/api/teams/<int:team_id>', methods=['PUT'])
@role_required('admin')
def update_team(team_id):
    """Update a response team. Admin only."""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM response_teams WHERE id=%s", (team_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Team not found.'}), 404

        updates, values = [], []
        for f in ['team_name', 'team_category', 'team_leader', 'phone', 'base_location', 'status']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(data[f])
        if 'member_count' in data:
            updates.append("member_count = %s")
            values.append(int(data['member_count']))
        for f in ['latitude', 'longitude']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(float(data[f]) if data[f] else None)

        if not updates:
            return jsonify({'success': False, 'message': 'No fields to update.'}), 400

        values.append(team_id)
        cursor.execute(f"UPDATE response_teams SET {', '.join(updates)} WHERE id=%s", values)
        conn.commit()
        return jsonify({'success': True, 'message': 'Team updated.'}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@teams_bp.route('/api/teams/stats', methods=['GET'])
@login_required
def get_team_stats():
    """Team statistics for dashboard."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT status, COUNT(*) as c FROM response_teams GROUP BY status")
        by_status = {r['status']: r['c'] for r in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) as c FROM response_teams")
        total = cursor.fetchone()['c']
        return jsonify({'success': True, 'data': {'total': total, 'by_status': by_status}}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
