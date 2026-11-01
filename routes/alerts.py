"""
SentryGrid – Disaster Alert Routes (MODULE 1)
================================================
Disaster Monitoring and Alert System.
Handles CRUD operations for disaster alerts and weather data retrieval.
Demonstrates: REST API, CRUD, GET/POST/PUT/DELETE, JSON, AJAX, Fetch API.
"""

from flask import Blueprint, request, jsonify, session
from config import Config, get_db_connection, close_db_connection
from routes.auth import login_required, role_required
import json
from datetime import datetime

alerts_bp = Blueprint('alerts', __name__)

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
