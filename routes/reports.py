"""
SentryGrid – Reports and Analytics Routes
============================================
Summary reports, statistics, and CSV export.
"""

from flask import Blueprint, request, jsonify, session, Response
from config import get_db_connection, close_db_connection
from routes.auth import login_required, role_required
import csv
import io
from datetime import datetime

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/api/reports/summary', methods=['GET'])
@login_required
def get_summary_report():
    """
    Get a comprehensive summary report for the dashboard.
    Includes alert stats, request stats, team stats, resource stats.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Alert stats
        cursor.execute("SELECT COUNT(*) as c FROM disaster_alerts WHERE is_active=TRUE")
        active_alerts = cursor.fetchone()['c']

        # Emergency request stats
        cursor.execute("SELECT COUNT(*) as c FROM emergency_requests")
        total_requests = cursor.fetchone()['c']
        cursor.execute("SELECT COUNT(*) as c FROM emergency_requests WHERE status NOT IN ('Rescued','Closed')")
        pending_requests = cursor.fetchone()['c']
        cursor.execute("SELECT COUNT(*) as c FROM emergency_requests WHERE status IN ('Rescued','Closed')")
        resolved_requests = cursor.fetchone()['c']
        cursor.execute("SELECT COUNT(*) as c FROM emergency_requests WHERE is_sos=TRUE")
        sos_count = cursor.fetchone()['c']

        # Requests by type
        cursor.execute("SELECT emergency_type, COUNT(*) as c FROM emergency_requests GROUP BY emergency_type")
        requests_by_type = {r['emergency_type']: r['c'] for r in cursor.fetchall()}

        # Requests by status
        cursor.execute("SELECT status, COUNT(*) as c FROM emergency_requests GROUP BY status")
        requests_by_status = {r['status']: r['c'] for r in cursor.fetchall()}

        # Team stats
        cursor.execute("SELECT status, COUNT(*) as c FROM response_teams GROUP BY status")
        teams_by_status = {r['status']: r['c'] for r in cursor.fetchall()}

        # Resource stats
        cursor.execute("SELECT COUNT(*) as c FROM resources WHERE quantity <= min_threshold")
        low_stock = cursor.fetchone()['c']
        cursor.execute("SELECT category, SUM(quantity) as total FROM resources GROUP BY category")
        resources_by_cat = {r['category']: int(r['total']) for r in cursor.fetchall()}

        # Shelter stats
        cursor.execute("SELECT COUNT(*) as c FROM shelters WHERE is_active=TRUE")
        active_shelters = cursor.fetchone()['c']
        cursor.execute("SELECT COALESCE(SUM(total_capacity),0) as cap, COALESCE(SUM(current_occupancy),0) as occ FROM shelters WHERE is_active=TRUE")
        shelter_row = cursor.fetchone()
        shelter_capacity = int(shelter_row['cap'])
        shelter_occupancy = int(shelter_row['occ'])

        # Alerts by severity (for chart)
        cursor.execute("SELECT severity, COUNT(*) as c FROM disaster_alerts WHERE is_active=TRUE GROUP BY severity")
        alerts_by_severity = {r['severity']: r['c'] for r in cursor.fetchall()}

        return jsonify({
            'success': True,
            'data': {
                'alerts': {'active': active_alerts, 'by_severity': alerts_by_severity},
                'requests': {
                    'total': total_requests, 'pending': pending_requests,
                    'resolved': resolved_requests, 'sos_count': sos_count,
                    'by_type': requests_by_type, 'by_status': requests_by_status
                },
                'teams': teams_by_status,
                'resources': {'low_stock': low_stock, 'by_category': resources_by_cat},
                'shelters': {
                    'active': active_shelters,
                    'total_capacity': shelter_capacity,
                    'current_occupancy': shelter_occupancy,
                    'available': shelter_capacity - shelter_occupancy
                },
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@reports_bp.route('/api/reports/csv', methods=['GET'])
@role_required('admin')
def export_csv():
    """Export emergency requests as a downloadable CSV file. Admin only."""
    conn = None
    cursor = None
    try:
        report_type = request.args.get('type', 'requests')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == 'requests':
            writer.writerow(['ID', 'Citizen', 'Contact', 'Type', 'Location', 'Status', 'Priority', 'SOS', 'Created'])
            cursor.execute("""
                SELECT id, citizen_name, contact_number, emergency_type, location, status, priority, is_sos, created_at
                FROM emergency_requests ORDER BY created_at DESC
            """)
            for r in cursor.fetchall():
                writer.writerow([r['id'], r['citizen_name'], r['contact_number'],
                                r['emergency_type'], r['location'], r['status'],
                                r['priority'], 'Yes' if r['is_sos'] else 'No',
                                r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r['created_at'] else ''])
        elif report_type == 'resources':
            writer.writerow(['ID', 'Name', 'Category', 'Quantity', 'Unit', 'Min Threshold', 'Location', 'Status'])
            cursor.execute("SELECT * FROM resources ORDER BY category, name")
            for r in cursor.fetchall():
                status = 'LOW STOCK' if r['quantity'] <= r['min_threshold'] else 'OK'
                writer.writerow([r['id'], r['name'], r['category'], r['quantity'],
                                r['unit'], r['min_threshold'], r['location'], status])
        elif report_type == 'alerts':
            writer.writerow(['ID', 'Type', 'Severity', 'Title', 'Location', 'Active', 'Created'])
            cursor.execute("SELECT * FROM disaster_alerts ORDER BY created_at DESC")
            for r in cursor.fetchall():
                writer.writerow([r['id'], r['disaster_type'], r['severity'], r['title'],
                                r['location'], 'Yes' if r['is_active'] else 'No',
                                r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r['created_at'] else ''])

        csv_content = output.getvalue()
        output.close()

        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=sentrygrid_{report_type}_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@reports_bp.route('/api/reports', methods=['GET'])
@login_required
def get_disaster_reports():
    """Get stored disaster reports."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT dr.*, u.full_name as generated_by_name
            FROM disaster_reports dr
            LEFT JOIN users u ON dr.generated_by = u.id
            ORDER BY dr.created_at DESC
        """)
        reports = cursor.fetchall()
        for r in reports:
            if r.get('created_at'):
                r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify({'success': True, 'data': reports}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
