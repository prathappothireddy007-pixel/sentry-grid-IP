"""
SentryGrid – Shelter Routes (MODULE 3)
=========================================
Shelter Information and Management.
Handles CRUD, nearby search with distance calculation.
Demonstrates: Geolocation API, REST API, JSON, GET/POST/PUT, AJAX.
"""

import math
import json
import urllib.request
import urllib.parse
from flask import Blueprint, request, jsonify, session
from config import get_db_connection, close_db_connection, haversine
from routes.auth import login_required, role_required

shelters_bp = Blueprint('shelters', __name__)

def format_datetime(val):
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val)


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
                if s.get(k): s[k] = format_datetime(s[k])
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
            if shelter.get(k): shelter[k] = format_datetime(shelter[k])
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


# ============================================================
# GET /api/hospitals – Medical & Trauma Centers Directory
# ============================================================

@shelters_bp.route('/api/hospitals', methods=['GET'])
@login_required
def get_hospitals():
    """
    List hospitals with bed availability and proximity sorting.
    Query params: lat, lon, emergency_dept (bool), trauma_level, min_beds, active (default true)
    """
    conn = None
    cursor = None
    try:
        user_lat = request.args.get('lat', type=float) or session.get('latitude')
        user_lon = request.args.get('lon', type=float) or session.get('longitude')
        active_only = request.args.get('active', 'true').lower() == 'true'
        emergency_dept = request.args.get('emergency_dept')
        trauma_level = request.args.get('trauma_level')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM hospitals WHERE 1=1"
        params = []

        if active_only:
            query += " AND is_active = TRUE"
        if emergency_dept is not None:
            query += " AND emergency_department = %s"
            params.append(1 if emergency_dept.lower() in ('true', '1') else 0)
        if trauma_level:
            query += " AND trauma_level = %s"
            params.append(trauma_level)

        cursor.execute(query, params)
        hospitals = cursor.fetchall()

        for h in hospitals:
            for k in ['created_at', 'updated_at']:
                if h.get(k): h[k] = format_datetime(h[k])
            for k in ['latitude', 'longitude']:
                if h.get(k): h[k] = float(h[k])

            # Calculate distance if user coords available
            if user_lat and user_lon and h.get('latitude') and h.get('longitude'):
                h['distance_km'] = haversine(user_lat, user_lon, h['latitude'], h['longitude'])
            else:
                h['distance_km'] = None

            # Calculate occupancy percentage
            total = h.get('total_beds', 0)
            avail = h.get('available_beds', 0)
            h['occupancy_rate'] = round(((total - avail) / total * 100), 1) if total > 0 else 0

        # Sort nearest first if coordinates present
        if user_lat and user_lon:
            hospitals.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else 99999)

        return jsonify({'success': True, 'count': len(hospitals), 'data': hospitals}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/hospitals/<id> – Hospital Details
# ============================================================

@shelters_bp.route('/api/hospitals/<int:hospital_id>', methods=['GET'])
@login_required
def get_hospital_detail(hospital_id):
    """Retrieve full detail for a single hospital."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM hospitals WHERE id = %s", (hospital_id,))
        h = cursor.fetchone()
        if not h:
            return jsonify({'success': False, 'message': 'Hospital not found.'}), 404

        for k in ['created_at', 'updated_at']:
            if h.get(k): h[k] = format_datetime(h[k])
        for k in ['latitude', 'longitude']:
            if h.get(k): h[k] = float(h[k])

        return jsonify({'success': True, 'data': h}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# POST /api/hospitals – Create Hospital (Admin Only)
# ============================================================

@shelters_bp.route('/api/hospitals', methods=['POST'])
@role_required('admin')
def create_hospital():
    """Register a new medical facility or hospital."""
    conn = None
    cursor = None
    try:
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        address = data.get('address', '').strip()
        lat = data.get('latitude')
        lon = data.get('longitude')

        if not name or not address or lat is None or lon is None:
            return jsonify({'success': False, 'message': 'Name, address, latitude, and longitude are required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            INSERT INTO hospitals (name, address, latitude, longitude, contact_phone, emergency_department, total_beds, available_beds, trauma_level, services, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            name, address, float(lat), float(lon),
            data.get('contact_phone', ''),
            1 if data.get('emergency_department', True) else 0,
            int(data.get('total_beds', 0)),
            int(data.get('available_beds', 0)),
            data.get('trauma_level', 'Level 2 Trauma Center'),
            data.get('services', 'Emergency Care'),
            1 if data.get('is_active', True) else 0
        ))
        conn.commit()
        hid = cursor.lastrowid

        return jsonify({'success': True, 'message': 'Hospital created.', 'data': {'id': hid}}), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# PUT /api/hospitals/<id> – Update Hospital Bed Capacity
# ============================================================

@shelters_bp.route('/api/hospitals/<int:hospital_id>', methods=['PUT'])
@role_required('admin')
def update_hospital(hospital_id):
    """Update hospital details, bed capacity, or operational status."""
    conn = None
    cursor = None
    try:
        data = request.get_json() or {}
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM hospitals WHERE id = %s", (hospital_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Hospital not found.'}), 404

        updates, values = [], []
        for f in ['name', 'address', 'contact_phone', 'trauma_level', 'services', 'is_active', 'emergency_department']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(data[f])
        for f in ['latitude', 'longitude']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(float(data[f]) if data[f] else None)
        for f in ['total_beds', 'available_beds']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(int(data[f]))

        if not updates:
            return jsonify({'success': False, 'message': 'No fields provided.'}), 400

        values.append(hospital_id)
        cursor.execute(f"UPDATE hospitals SET {', '.join(updates)} WHERE id = %s", values)
        conn.commit()

        return jsonify({'success': True, 'message': 'Hospital record updated.'}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/route – In-App Leaflet Navigation Polyline Routing
# ============================================================

@shelters_bp.route('/api/route', methods=['GET'])
@login_required
def get_evacuation_route():
    """
    Calculate navigational routing between origin and destination.
    Uses OSRM engine with resilient geodesic fallback.
    Query params: origin_lat, origin_lon, dest_lat, dest_lon, mode ('driving' or 'walking')
    """
    try:
        raw_o_lat = request.args.get('origin_lat') or request.args.get('start_lat')
        raw_o_lon = request.args.get('origin_lon') or request.args.get('start_lon')
        raw_d_lat = request.args.get('dest_lat') or request.args.get('end_lat')
        raw_d_lon = request.args.get('dest_lon') or request.args.get('end_lon')

        if not all([raw_o_lat, raw_o_lon, raw_d_lat, raw_d_lon]):
            return jsonify({'success': False, 'message': 'Origin and destination coordinates are required.'}), 400

        o_lat = float(raw_o_lat)
        o_lon = float(raw_o_lon)
        d_lat = float(raw_d_lat)
        d_lon = float(raw_d_lon)
        mode = request.args.get('mode', 'driving')
        if mode not in ('driving', 'walking'):
            mode = 'driving'

        osrm_url = f"https://router.project-osrm.org/route/v1/{mode}/{o_lon},{o_lat};{d_lon},{d_lat}?overview=full&geometries=geojson&steps=true"

        is_osrm = False
        route_data = {}

        try:
            req = urllib.request.Request(osrm_url, headers={'User-Agent': 'SentryGrid-Navigator/1.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                osrm_res = json.loads(resp.read().decode('utf-8'))
                if osrm_res.get('code') == 'Ok' and osrm_res.get('routes'):
                    r = osrm_res['routes'][0]
                    dist_km = round(r.get('distance', 0) / 1000.0, 2)
                    dur_mins = round(r.get('duration', 0) / 60.0, 1)
                    coords = r.get('geometry', {}).get('coordinates', [])
                    route_data = {
                        'distance_km': dist_km,
                        'duration_mins': dur_mins,
                        'coordinates': coords,  # [[lon, lat], ...]
                        'engine': 'OSRM Public Routing API (Real Street Network)',
                        'mode': mode
                    }
                    is_osrm = True
        except Exception as osrm_err:
            print(f"[OSRM Routing Notice]: {osrm_err}")

        if not is_osrm:
            # Geodesic fallback
            dist_km = haversine(o_lat, o_lon, d_lat, d_lon) or 5.0
            avg_speed = 40.0 if mode == 'driving' else 4.5
            dur_mins = round((dist_km / avg_speed) * 60.0, 1)
            route_data = {
                'distance_km': dist_km,
                'duration_mins': dur_mins,
                'coordinates': [[o_lon, o_lat], [d_lon, d_lat]],
                'engine': 'Geodesic Direct Vector (OSRM Offline Fallback)',
                'mode': mode
            }

        disclaimer = 'CRITICAL SAFETY NOTICE: This route calculation provides standard road navigation and DOES NOT reflect real-time flash floods, structural damage, or emergency barricades. Follow emergency authority instructions on site.'
        route_data['safety_advisory'] = disclaimer
        route_data['safety_disclaimer'] = disclaimer

        return jsonify({
            'success': True,
            'data': route_data,
            'safety_disclaimer': disclaimer,
            'safety_advisory': disclaimer
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Routing error: {str(e)}'}), 400

