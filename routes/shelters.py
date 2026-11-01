"""
SentryGrid – Shelter Routes (MODULE 3)
=========================================
Shelter Information and Management.
Handles CRUD, nearby search with distance calculation.
Demonstrates: Geolocation API, REST API, JSON, GET/POST/PUT, AJAX.
"""

import math
from flask import Blueprint, request, jsonify, session
from config import get_db_connection, close_db_connection
from routes.auth import login_required, role_required

shelters_bp = Blueprint('shelters', __name__)


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance (km) between two GPS coordinates using Haversine formula."""
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)


@shelters_bp.route('/api/shelters', methods=['GET'])
@login_required
def get_shelters():
    """
    List shelters. If lat/lon provided, sort by distance (nearest first).
    Query params: lat, lon, active (default true)
    """
    conn = None
    cursor = None
    try:
        user_lat = request.args.get('lat', type=float)
        user_lon = request.args.get('lon', type=float)
        active_only = request.args.get('active', 'true').lower() == 'true'

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM shelters WHERE 1=1"
        params = []
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY name"

        cursor.execute(query, params)
        shelters = cursor.fetchall()

        for s in shelters:
            for k in ['created_at', 'updated_at']:
                if s.get(k): s[k] = s[k].strftime('%Y-%m-%d %H:%M:%S')
            for k in ['latitude', 'longitude']:
                if s.get(k): s[k] = float(s[k])
            s['available_capacity'] = s['total_capacity'] - s['current_occupancy']

            # Calculate distance if user coordinates provided
            if user_lat and user_lon and s.get('latitude') and s.get('longitude'):
                s['distance_km'] = haversine(user_lat, user_lon, s['latitude'], s['longitude'])
            else:
                s['distance_km'] = None

            # Get facilities for this shelter
            cursor.execute("SELECT * FROM shelter_facilities WHERE shelter_id = %s", (s['id'],))
            s['facilities'] = cursor.fetchall()

        # Sort by distance if coordinates provided
        if user_lat and user_lon:
            shelters.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else 99999)

        return jsonify({'success': True, 'data': shelters}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@shelters_bp.route('/api/shelters/<int:shelter_id>', methods=['GET'])
@login_required
def get_shelter(shelter_id):
    """Get a single shelter with facilities."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM shelters WHERE id=%s", (shelter_id,))
        shelter = cursor.fetchone()
        if not shelter:
            return jsonify({'success': False, 'message': 'Shelter not found.'}), 404

        for k in ['created_at', 'updated_at']:
            if shelter.get(k): shelter[k] = shelter[k].strftime('%Y-%m-%d %H:%M:%S')
        for k in ['latitude', 'longitude']:
            if shelter.get(k): shelter[k] = float(shelter[k])
        shelter['available_capacity'] = shelter['total_capacity'] - shelter['current_occupancy']

        cursor.execute("SELECT * FROM shelter_facilities WHERE shelter_id=%s", (shelter_id,))
        shelter['facilities'] = cursor.fetchall()

        return jsonify({'success': True, 'data': shelter}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@shelters_bp.route('/api/shelters', methods=['POST'])
@role_required('admin')
def create_shelter():
    """Create a new shelter. Admin only."""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required.'}), 400

        name = data.get('name', '').strip()
        address = data.get('address', '').strip()
        if not name or not address:
            return jsonify({'success': False, 'message': 'Name and address are required.'}), 400

        lat = data.get('latitude')
        lon = data.get('longitude')
        if not lat or not lon:
            return jsonify({'success': False, 'message': 'Latitude and longitude are required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shelters (name, address, latitude, longitude, total_capacity, current_occupancy, contact_phone, contact_email)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            name, address, float(lat), float(lon),
            int(data.get('total_capacity', 100)),
            int(data.get('current_occupancy', 0)),
            data.get('contact_phone', '').strip() or None,
            data.get('contact_email', '').strip() or None
        ))
        sid = cursor.lastrowid

        # Add facilities
        facilities = data.get('facilities', [])
        for f in facilities:
            if f.strip():
                cursor.execute("INSERT INTO shelter_facilities (shelter_id, facility_name) VALUES (%s,%s)",
                             (sid, f.strip()))

        conn.commit()
        return jsonify({'success': True, 'message': 'Shelter created.', 'data': {'id': sid}}), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@shelters_bp.route('/api/shelters/<int:shelter_id>', methods=['PUT'])
@role_required('admin')
def update_shelter(shelter_id):
    """Update a shelter. Admin only."""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM shelters WHERE id=%s", (shelter_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Shelter not found.'}), 404

        updates, values = [], []
        for f in ['name', 'address', 'contact_phone', 'contact_email', 'is_active']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(data[f])
        for f in ['latitude', 'longitude']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(float(data[f]) if data[f] else None)
        for f in ['total_capacity', 'current_occupancy']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(int(data[f]))

        if not updates:
            return jsonify({'success': False, 'message': 'No fields to update.'}), 400

        values.append(shelter_id)
        cursor.execute(f"UPDATE shelters SET {', '.join(updates)} WHERE id=%s", values)
        conn.commit()
        return jsonify({'success': True, 'message': 'Shelter updated.'}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
