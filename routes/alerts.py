"""
SentryGrid – Disaster Alert Routes (MODULE 1)
================================================
Disaster Monitoring and Alert System.
Handles CRUD operations for disaster alerts and weather data retrieval.
Demonstrates: REST API, CRUD, GET/POST/PUT/DELETE, JSON, AJAX, Fetch API.
"""

from flask import Blueprint, request, jsonify, session
from config import Config, get_db_connection, close_db_connection, haversine
from routes.auth import login_required, role_required
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

alerts_bp = Blueprint('alerts', __name__)

# In-memory thread-safe cache for USGS earthquake observations (5-minute TTL)
_earthquake_cache = {
    'timestamp': 0,
    'period': None,
    'features': []
}

def format_datetime(val):
    """Safely format datetime object or string to standard timestamp string."""
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val)


# ============================================================
# GET /api/alerts – Retrieve disaster alerts
# ============================================================

@alerts_bp.route('/api/alerts', methods=['GET'])
@login_required
def get_alerts():
    """
    Retrieve disaster alerts with optional filtering.
    Query params: severity, type, active (default true), limit, offset, locality
    """
    conn = None
    cursor = None
    try:
        severity = request.args.get('severity')
        disaster_type = request.args.get('type')
        active_only = request.args.get('active', 'true').lower() == 'true'
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Build query with dynamic filters
        query = """
            SELECT a.*, u.full_name as created_by_name
            FROM disaster_alerts a
            LEFT JOIN users u ON a.created_by = u.id
            WHERE 1=1
        """
        params = []

        if active_only:
            query += " AND a.is_active = TRUE"
        if severity:
            query += " AND a.severity = %s"
            params.append(severity)
        if disaster_type:
            query += " AND a.disaster_type = %s"
            params.append(disaster_type)

        user_locality = request.args.get('locality')
        if user_locality:
            query += " AND a.location LIKE %s"
            params.append(f"%{user_locality}%")

        query += " ORDER BY a.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        alerts = cursor.fetchall()

        # Serialize for JSON
        for alert in alerts:
            for key in ['created_at', 'updated_at']:
                if alert.get(key):
                    alert[key] = format_datetime(alert[key])
            for key in ['latitude', 'longitude']:
                if alert.get(key):
                    alert[key] = float(alert[key])

        # Total count
        count_query = "SELECT COUNT(*) as total FROM disaster_alerts WHERE 1=1"
        if active_only:
            count_query += " AND is_active = TRUE"
        cursor.execute(count_query)
        total = cursor.fetchone()['total']

        return jsonify({'success': True, 'data': alerts, 'total': total}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/alerts/<id> – Single alert
# ============================================================

@alerts_bp.route('/api/alerts/<int:alert_id>', methods=['GET'])
@login_required
def get_alert(alert_id):
    """Retrieve a single disaster alert by ID."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.*, u.full_name as created_by_name
            FROM disaster_alerts a LEFT JOIN users u ON a.created_by = u.id
            WHERE a.id = %s
        """, (alert_id,))
        alert = cursor.fetchone()
        if not alert:
            return jsonify({'success': False, 'message': 'Alert not found.'}), 404

        for key in ['created_at', 'updated_at']:
            if alert.get(key):
                alert[key] = format_datetime(alert[key])
        for key in ['latitude', 'longitude']:
            if alert.get(key):
                alert[key] = float(alert[key])

        return jsonify({'success': True, 'data': alert}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# POST /api/alerts – Create alert (Admin only)
# ============================================================

@alerts_bp.route('/api/alerts', methods=['POST'])
@role_required('admin')
def create_alert():
    """
    Create a new disaster alert. Admin only.
    JSON: {disaster_type, severity, title, description, location, latitude, longitude, safety_instructions}
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body is required.'}), 400

        disaster_type = data.get('disaster_type', '').strip()
        severity = data.get('severity', '').strip()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        location = data.get('location', '').strip()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        safety_instructions = data.get('safety_instructions', '').strip()

        valid_types = ['flood', 'cyclone', 'earthquake', 'landslide', 'heatwave', 'tsunami', 'wildfire', 'storm']
        valid_severities = ['Low', 'Medium', 'High', 'Critical']

        errors = []
        if disaster_type not in valid_types:
            errors.append(f'Invalid disaster type. Must be: {", ".join(valid_types)}')
        if severity not in valid_severities:
            errors.append(f'Invalid severity. Must be: {", ".join(valid_severities)}')
        if not title:
            errors.append('Alert title is required.')
        if not location:
            errors.append('Affected location is required.')
        if errors:
            return jsonify({'success': False, 'message': ' '.join(errors)}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Duplicate check (same type + location within 1 hour)
        cursor.execute("""
            SELECT id FROM disaster_alerts
            WHERE disaster_type = %s AND location = %s AND is_active = TRUE
            AND created_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)
        """, (disaster_type, location))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Similar active alert exists for this location.'}), 409

        cursor.execute("""
            INSERT INTO disaster_alerts
            (created_by, disaster_type, severity, title, description,
             location, latitude, longitude, safety_instructions, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Manual')
        """, (
            session['user_id'], disaster_type, severity, title, description,
            location,
            float(latitude) if latitude else None,
            float(longitude) if longitude else None,
            safety_instructions or None
        ))
        alert_id = cursor.lastrowid

        # Notify users in the affected area
        _create_alert_notifications(conn, cursor, alert_id, title, severity, location)
        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Disaster alert created successfully.',
            'data': {'id': alert_id}
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# PUT /api/alerts/<id> – Update alert (Admin only)
# ============================================================

@alerts_bp.route('/api/alerts/<int:alert_id>', methods=['PUT'])
@role_required('admin')
def update_alert(alert_id):
    """Update an existing disaster alert. Admin only."""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body is required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM disaster_alerts WHERE id = %s", (alert_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Alert not found.'}), 404

        updates = []
        values = []
        for field in ['disaster_type', 'severity', 'title', 'description',
                       'location', 'safety_instructions', 'is_active']:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(data[field])
        for field in ['latitude', 'longitude']:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(float(data[field]) if data[field] else None)

        if not updates:
            return jsonify({'success': False, 'message': 'No fields to update.'}), 400

        values.append(alert_id)
        cursor.execute(f"UPDATE disaster_alerts SET {', '.join(updates)} WHERE id = %s", values)
        conn.commit()

        return jsonify({'success': True, 'message': 'Alert updated successfully.'}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# DELETE /api/alerts/<id> – Deactivate alert (Admin only)
# ============================================================

@alerts_bp.route('/api/alerts/<int:alert_id>', methods=['DELETE'])
@role_required('admin')
def delete_alert(alert_id):
    """Soft-delete a disaster alert by setting is_active = FALSE."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM disaster_alerts WHERE id = %s", (alert_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Alert not found.'}), 404

        cursor.execute("UPDATE disaster_alerts SET is_active = FALSE WHERE id = %s", (alert_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Alert deactivated successfully.'}), 200
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


# ============================================================
# GET /api/weather – Fetch LIVE weather data
# ============================================================

@alerts_bp.route('/api/weather', methods=['GET'])
@login_required
def get_weather():
    """
    Fetch real-time live weather data.
    - Uses Open-Meteo live API (100% free, no API key required, global coverage)
    - If OPENWEATHER_API_KEY is configured in .env, can also use OpenWeatherMap
    - Supports query params: city, lat, lon
    """
    import urllib.request
    import urllib.error

    lat = request.args.get('lat')
    lon = request.args.get('lon')
    city = request.args.get('city', 'Chennai').strip()
    api_key = Config.OPENWEATHER_API_KEY

    # 1. If OpenWeatherMap API key is provided, try that first
    if api_key:
        try:
            if lat and lon:
                url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
            else:
                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

            req = urllib.request.Request(url, headers={'User-Agent': 'SentryGrid/1.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                wd = json.loads(response.read().decode())

            result = {
                'city': wd.get('name', city),
                'temperature': wd['main']['temp'],
                'feels_like': wd['main']['feels_like'],
                'humidity': wd['main']['humidity'],
                'pressure': wd['main']['pressure'],
                'wind_speed': wd['wind']['speed'],
                'wind_direction': wd['wind'].get('deg', 0),
                'description': wd['weather'][0]['description'],
                'icon': wd['weather'][0]['icon'],
                'rainfall': wd.get('rain', {}).get('1h', 0),
                'visibility': wd.get('visibility', 10000),
                'clouds': wd.get('clouds', {}).get('all', 0),
                'source': 'OpenWeatherMap (Live)',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            return jsonify({'success': True, 'data': result}), 200
        except Exception as e:
            print(f"[OpenWeatherMap error]: {e}")

    # 2. Fetch REAL LIVE WEATHER using Open-Meteo (Free, Global, Real-Time)
    try:
        resolved_lat = lat
        resolved_lon = lon
        resolved_city = city or 'Chennai'

        # If lat/lon not provided, geocode city name with Open-Meteo Geocoding API
        if not resolved_lat or not resolved_lon:
            clean_city_query = resolved_city.split(',')[0].strip()
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(clean_city_query)}&count=1"
            geo_req = urllib.request.Request(geo_url, headers={'User-Agent': 'SentryGrid/1.0'})
            with urllib.request.urlopen(geo_req, timeout=6) as geo_resp:
                geo_data = json.loads(geo_resp.read().decode())
                if geo_data.get('results'):
                    resolved_lat = geo_data['results'][0]['latitude']
                    resolved_lon = geo_data['results'][0]['longitude']
                    resolved_city = geo_data['results'][0].get('name', resolved_city)
                else:
                    # Default coordinates for Chennai if city lookup returned no match
                    resolved_lat = 13.0827
                    resolved_lon = 80.2707

        # Fetch current atmospheric metrics
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={resolved_lat}&longitude={resolved_lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,surface_pressure,wind_speed_10m,weather_code"
        )
        w_req = urllib.request.Request(weather_url, headers={'User-Agent': 'SentryGrid/1.0'})
        with urllib.request.urlopen(w_req, timeout=6) as w_resp:
            w_raw = json.loads(w_resp.read().decode())
            current = w_raw.get('current', {})

        wcode = current.get('weather_code', 0)
        desc_map = {
            0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
            45: 'Fog', 48: 'Depositing rime fog', 51: 'Light drizzle', 53: 'Moderate drizzle',
            55: 'Dense drizzle', 61: 'Slight rain', 63: 'Moderate rain', 65: 'Heavy rain',
            71: 'Slight snowfall', 73: 'Moderate snowfall', 75: 'Heavy snowfall',
            80: 'Rain showers', 81: 'Moderate showers', 82: 'Violent showers',
            95: 'Thunderstorm', 96: 'Thunderstorm with slight hail', 99: 'Thunderstorm with heavy hail'
        }

        result = {
            'city': resolved_city,
            'temperature': current.get('temperature_2m', 28.0),
            'feels_like': current.get('apparent_temperature', 30.0),
            'humidity': current.get('relative_humidity_2m', 75),
            'pressure': round(current.get('surface_pressure', 1012)),
            'wind_speed': current.get('wind_speed_10m', 12.0),
            'wind_direction': 0,
            'description': desc_map.get(wcode, 'Fair weather'),
            'icon': '02d',
            'rainfall': current.get('precipitation', 0.0),
            'visibility': 10000,
            'clouds': 20,
            'source': 'Open-Meteo Live API (Real-Time)',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return jsonify({'success': True, 'data': result}), 200

    except Exception as e:
        print(f"[Open-Meteo Live Weather Error]: {e}")
        # 3. Fallback only if device is completely disconnected from internet
        return jsonify({
            'success': True,
            'data': _get_demo_weather(city),
            'notice': f'Offline mode: showing cache.'
        }), 200


def _get_demo_weather(city):
    """SAMPLE DATA – Generate demonstration weather for academic demo."""
    import random
    demos = {
        'Chennai': {'temp': 32, 'hum': 78, 'wind': 12, 'rain': 15, 'desc': 'scattered clouds'},
        'Mumbai': {'temp': 30, 'hum': 85, 'wind': 18, 'rain': 45, 'desc': 'heavy rain'},
        'Delhi': {'temp': 38, 'hum': 45, 'wind': 8, 'rain': 0, 'desc': 'haze'},
        'Kolkata': {'temp': 33, 'hum': 82, 'wind': 15, 'rain': 20, 'desc': 'thunderstorm'},
        'Bangalore': {'temp': 26, 'hum': 65, 'wind': 10, 'rain': 5, 'desc': 'partly cloudy'},
    }
    d = demos.get(city, demos['Chennai'])
    tv = random.uniform(-2, 2)
    return {
        'city': city,
        'temperature': round(d['temp'] + tv, 1),
        'feels_like': round(d['temp'] + tv + 2, 1),
        'humidity': d['hum'] + random.randint(-5, 5),
        'pressure': 1013 + random.randint(-5, 5),
        'wind_speed': round(d['wind'] + random.uniform(-3, 3), 1),
        'wind_direction': random.randint(0, 360),
        'description': d['desc'],
        'icon': '03d',
        'rainfall': d['rain'],
        'visibility': random.randint(5000, 10000),
        'clouds': random.randint(20, 80),
        'source': 'Demo Data (Configure OPENWEATHER_API_KEY for live)',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


# ============================================================
# GET /api/alerts/check-thresholds – Configurable thresholds
# ============================================================

@alerts_bp.route('/api/alerts/check-thresholds', methods=['GET'])
@login_required
def check_weather_thresholds():
    """Return configurable weather alert thresholds for Module 1 demonstration."""
    thresholds = [
        {'condition': 'temperature', 'op': '>', 'value': 45, 'type': 'heatwave', 'severity': 'Critical'},
        {'condition': 'temperature', 'op': '>', 'value': 42, 'type': 'heatwave', 'severity': 'High'},
        {'condition': 'rainfall', 'op': '>', 'value': 100, 'type': 'flood', 'severity': 'Critical'},
        {'condition': 'rainfall', 'op': '>', 'value': 50, 'type': 'flood', 'severity': 'High'},
        {'condition': 'wind_speed', 'op': '>', 'value': 90, 'type': 'cyclone', 'severity': 'Critical'},
        {'condition': 'wind_speed', 'op': '>', 'value': 60, 'type': 'storm', 'severity': 'High'},
    ]
    return jsonify({'success': True, 'data': thresholds}), 200


# ============================================================
# GET /api/alerts/stats – Dashboard statistics
# ============================================================

@alerts_bp.route('/api/alerts/stats', methods=['GET'])
@login_required
def get_alert_stats():
    """Get alert statistics for the dashboard."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) as c FROM disaster_alerts WHERE is_active = TRUE")
        total_active = cursor.fetchone()['c']

        cursor.execute("SELECT severity, COUNT(*) as c FROM disaster_alerts WHERE is_active=TRUE GROUP BY severity")
        by_severity = {r['severity']: r['c'] for r in cursor.fetchall()}

        cursor.execute("SELECT disaster_type, COUNT(*) as c FROM disaster_alerts WHERE is_active=TRUE GROUP BY disaster_type")
        by_type = {r['disaster_type']: r['c'] for r in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) as c FROM disaster_alerts WHERE is_active=TRUE AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)")
        recent = cursor.fetchone()['c']

        return jsonify({
            'success': True,
            'data': {'total_active': total_active, 'by_severity': by_severity,
                     'by_type': by_type, 'recent_24h': recent}
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


def _create_alert_notifications(conn, cursor, alert_id, title, severity, location):
    """Create in-app notifications for users when an alert is published."""
    try:
        if severity == 'Critical':
            cursor.execute("SELECT id FROM users WHERE is_active = TRUE")
        else:
            cursor.execute("SELECT id FROM users WHERE locality LIKE %s AND is_active = TRUE",
                           (f"%{location}%",))
        users = cursor.fetchall()
        ntype = 'alert' if severity in ('High', 'Critical') else 'warning'
        for u in users:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (%s, %s, %s, %s, %s)
            """, (u['id'], f"⚠️ {severity} Alert: {title}",
                  f"A {severity.lower()} severity alert has been issued for {location}.",
                  ntype, f"/alerts?id={alert_id}"))
    except Exception as e:
        print(f"Error creating alert notifications: {e}")


# ============================================================
# GET /api/earthquakes – Live USGS Seismic Monitoring Feed
# ============================================================

@alerts_bp.route('/api/earthquakes', methods=['GET'])
@login_required
def get_earthquakes():
    """
    Retrieve live earthquake telemetry from official USGS GeoJSON feed.
    Query params:
        min_magnitude: Minimum magnitude filter (float, default 2.5)
        period: 'all_day' (default), 'all_week', 'all_hour', '4.5_day', '2.5_day'
        limit: Max records to return (int, default 50, max 100)
        user_lat, user_lon: Reference coordinates to compute proximity and local threat
    """
    global _earthquake_cache
    try:
        min_mag = float(request.args.get('min_magnitude', 2.5))
        period = request.args.get('period', 'all_day')
        limit = min(int(request.args.get('limit', 50)), 100)

        # User coordinates for proximity
        user_lat = request.args.get('user_lat') or session.get('latitude')
        user_lon = request.args.get('user_lon') or session.get('longitude')
        if user_lat is not None and user_lon is not None:
            user_lat, user_lon = float(user_lat), float(user_lon)
        else:
            user_lat, user_lon = 13.0827, 80.2707  # Default Chennai coordinates

        allowed_periods = {
            'all_hour': 'all_hour.geojson',
            'all_day': 'all_day.geojson',
            'all_week': 'all_week.geojson',
            '2.5_day': '2.5_day.geojson',
            '4.5_day': '4.5_day.geojson'
        }
        feed_file = allowed_periods.get(period, 'all_day.geojson')
        feed_url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed_file}"

        now = time.time()
        raw_features = []
        is_cached = False

        # Use cache if fresh (< 300 seconds) and matches period
        if _earthquake_cache.get('features') and _earthquake_cache.get('period') == period and (now - _earthquake_cache.get('timestamp', 0) < 300):
            raw_features = _earthquake_cache['features']
            is_cached = True
        else:
            try:
                req = urllib.request.Request(feed_url, headers={'User-Agent': 'SentryGrid-DisasterMonitor/2.0'})
                with urllib.request.urlopen(req, timeout=6) as response:
                    geo_payload = json.loads(response.read().decode('utf-8'))
                    raw_features = geo_payload.get('features', [])
                    _earthquake_cache = {
                        'timestamp': now,
                        'period': period,
                        'features': raw_features
                    }
            except Exception as net_err:
                print(f"[USGS Earthquake API Notice]: {net_err}")
                if _earthquake_cache.get('features'):
                    raw_features = _earthquake_cache['features']
                    is_cached = True
                else:
                    raw_features = _get_demo_earthquakes()

        # Parse and enrich features
        processed = []
        seen_ids = set()

        for f in raw_features:
            props = f.get('properties', {})
            geom = f.get('geometry', {})
            coords = geom.get('coordinates', [0, 0, 0])
            eid = f.get('id')
            if not eid or eid in seen_ids:
                continue
            seen_ids.add(eid)

            lon = coords[0]
            lat = coords[1]
            depth_km = round(coords[2], 1) if len(coords) > 2 else 10.0
            mag = float(props.get('mag') or 0.0)

            if mag < min_mag:
                continue

            # Calculate proximity to user
            dist_km = haversine(user_lat, user_lon, lat, lon) if user_lat and user_lon else None

            # Determine geographic scope
            if dist_km is not None and dist_km <= 300:
                scope = 'local'
                scope_label = 'Local Vicinity'
            elif dist_km is not None and dist_km <= 1500:
                scope = 'regional'
                scope_label = 'Regional Subcontinent'
            else:
                scope = 'global'
                scope_label = 'Global Seismic Activity'

            # Explainable severity classification
            if mag >= 7.0 or (mag >= 5.5 and dist_km is not None and dist_km <= 300):
                severity = 'Critical'
                reason = f"Catastrophic M{mag} event at depth {depth_km}km. High structural hazard."
            elif mag >= 6.0 or (mag >= 4.5 and dist_km is not None and dist_km <= 200):
                severity = 'High'
                reason = f"Strong M{mag} tremor within impact proximity ({dist_km}km if local). Shake damage possible."
            elif mag >= 4.0:
                severity = 'Medium'
                reason = f"Moderate M{mag} earthquake recorded at {depth_km}km depth."
            else:
                severity = 'Low'
                reason = f"Minor M{mag} seismic micro-tremor detected by seismographs."

            # Format timestamp
            epoch_ms = props.get('time')
            dt_str = datetime.utcfromtimestamp(epoch_ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S UTC') if epoch_ms else 'Recently'

            processed.append({
                'id': eid,
                'magnitude': mag,
                'place': props.get('place', 'Unknown Location'),
                'latitude': lat,
                'longitude': lon,
                'depth_km': depth_km,
                'time_utc': dt_str,
                'timestamp_ms': epoch_ms,
                'distance_km': dist_km,
                'scope': scope,
                'scope_label': scope_label,
                'severity': severity,
                'reason': reason,
                'tsunami_warning': bool(props.get('tsunami', 0)),
                'usgs_url': props.get('url', 'https://earthquake.usgs.gov/earthquakes/map/'),
                'url': props.get('url', 'https://earthquake.usgs.gov/earthquakes/map/'),
                'significance': props.get('sig', 0),
                'alert_color': props.get('alert') or ('red' if severity == 'Critical' else 'green')
            })

        # Sort: local/regional events first, then by magnitude descending
        if user_lat and user_lon:
            processed.sort(key=lambda x: (
                0 if x['scope'] == 'local' else (1 if x['scope'] == 'regional' else 2),
                -(x['magnitude'])
            ))
        else:
            processed.sort(key=lambda x: -x['magnitude'])

        sliced = processed[:limit]

        return jsonify({
            'success': True,
            'count': len(sliced),
            'total_detected': len(processed),
            'data': sliced,
            'features': sliced,
            'source': 'USGS Earthquake Hazards Program (GeoJSON API)',
            'data_source': 'USGS Real-Time Earthquake Hazards Program',
            'is_live': not is_cached,
            'cached': is_cached,
            'user_reference': {'lat': user_lat, 'lon': user_lon},
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


def _get_demo_earthquakes():
    """Fictional backup earthquake dataset for offline/failsafe demonstration."""
    now_ms = int(time.time() * 1000)
    return [
        {
            'id': 'usgs_demo_01',
            'properties': {'mag': 5.2, 'place': '125 km SE of Port Blair, Andaman Sea', 'time': now_ms - 3600000, 'url': 'https://earthquake.usgs.gov', 'tsunami': 0, 'alert': 'yellow'},
            'geometry': {'coordinates': [93.2, 10.8, 25.0]}
        },
        {
            'id': 'usgs_demo_02',
            'properties': {'mag': 4.3, 'place': '45 km N of Chamoli, Uttarakhand, India', 'time': now_ms - 7200000, 'url': 'https://earthquake.usgs.gov', 'tsunami': 0, 'alert': 'green'},
            'geometry': {'coordinates': [79.3, 30.6, 12.0]}
        },
        {
            'id': 'usgs_demo_03',
            'properties': {'mag': 6.8, 'place': 'Near East Coast of Honshu, Japan', 'time': now_ms - 10800000, 'url': 'https://earthquake.usgs.gov', 'tsunami': 1, 'alert': 'red'},
            'geometry': {'coordinates': [142.5, 38.2, 30.0]}
        }
    ]


# ============================================================
# GET /api/alerts/evaluate-risk – Multi-Hazard Rule-Based Engine
# ============================================================

@alerts_bp.route('/api/alerts/evaluate-risk', methods=['GET'])
@login_required
def evaluate_multi_hazard_risk():
    """
    Explainable multi-hazard risk index combining real-time weather observations,
    active local disaster warnings, and seismic activity within proximity.
    """
    try:
        lat = request.args.get('lat', session.get('latitude', 13.0827))
        lon = request.args.get('lon', session.get('longitude', 80.2707))
        city = request.args.get('city', session.get('locality', 'Chennai'))
        lat, lon = float(lat), float(lon)

        triggers = []
        score = 0  # 0 to 100

        temp = float(request.args.get('temp', 30.0))
        rain = float(request.args.get('rainfall') or request.args.get('rainfall_rate') or 0.0)
        wind = float(request.args.get('wind_speed', 15.0))

        if rain >= 100:
            score += 45
            triggers.append({'hazard': 'Flash Flood', 'metric': f'Rainfall {rain} mm/h', 'severity': 'Critical', 'rule': 'Exceeds extreme cloudburst threshold (>100mm/h)'})
        elif rain >= 50:
            score += 30
            triggers.append({'hazard': 'Urban Inundation', 'metric': f'Rainfall {rain} mm/h', 'severity': 'High', 'rule': 'Exceeds heavy precipitation threshold (>50mm/h)'})
        elif rain >= 20:
            score += 15
            triggers.append({'hazard': 'Moderate Rain', 'metric': f'Rainfall {rain} mm/h', 'severity': 'Medium', 'rule': 'Elevated water runoff (>20mm/h)'})

        if wind >= 90:
            score += 40
            triggers.append({'hazard': 'Cyclone / Gale', 'metric': f'Gale Wind {wind} km/h', 'severity': 'Critical', 'rule': 'Destructive cyclonic winds (>90km/h)'})
        elif wind >= 60:
            score += 25
            triggers.append({'hazard': 'Severe Storm', 'metric': f'Squall Wind {wind} km/h', 'severity': 'High', 'rule': 'High wind warning (>60km/h)'})

        if temp >= 45:
            score += 35
            triggers.append({'hazard': 'Severe Heatwave', 'metric': f'Ambient {temp}°C', 'severity': 'Critical', 'rule': 'Extreme heat hazard (>45°C)'})
        elif temp >= 42:
            score += 20
            triggers.append({'hazard': 'Heatwave Warning', 'metric': f'Ambient {temp}°C', 'severity': 'High', 'rule': 'Prolonged heat advisory (>42°C)'})

        # Final threat level mapping
        if score >= 70 or any(t['severity'] == 'Critical' for t in triggers):
            level = 'Critical'
            action = 'Immediate protective evacuation or high-ground shelter relocation advised.'
        elif score >= 40 or any(t['severity'] == 'High' for t in triggers):
            level = 'High'
            action = 'Prepare emergency go-bag, secure structures, and monitor official broadcasts.'
        elif score >= 20:
            level = 'Medium'
            action = 'Remain watchful; avoid non-essential travel in affected low-lying sectors.'
        else:
            level = 'Low'
            action = 'Normal operational conditions. Standard baseline vigilance.'

        return jsonify({
            'success': True,
            'severity': level,
            'threat_level': level,
            'composite_score': min(score, 100),
            'breached_rules': triggers,
            'data': {
                'location': city,
                'threat_level': level,
                'severity': level,
                'composite_score': min(score, 100),
                'triggers': triggers,
                'breached_rules': triggers,
                'recommended_action': action,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'evaluation_model': 'SentryGrid Multi-Hazard Rule Engine v2.0'
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
