"""
SentryGrid – Resource Management Routes (MODULE 3)
=====================================================
Manages disaster relief resources: CRUD, restock, low-stock alerts.
Demonstrates: REST API, GET/POST/PUT/DELETE, JSON, AJAX.
"""

from flask import Blueprint, request, jsonify, session
from config import get_db_connection, close_db_connection
from routes.auth import login_required, role_required

resources_bp = Blueprint('resources', __name__)

def format_datetime(val):
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val)


@resources_bp.route('/api/resources', methods=['GET'])
@login_required
def get_resources():
    """List resources with optional category filter. Highlights low stock."""
    conn = None
    cursor = None
    try:
        category = request.args.get('category')
        low_stock = request.args.get('low_stock', 'false').lower() == 'true'

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM resources WHERE 1=1"
        params = []
        if category:
            query += " AND category = %s"
            params.append(category)
        if low_stock:
            query += " AND quantity <= min_threshold"
        query += " ORDER BY category, name"

        cursor.execute(query, params)
        resources = cursor.fetchall()

        for r in resources:
            for k in ['created_at', 'updated_at', 'last_restocked']:
                if r.get(k): r[k] = format_datetime(r[k])
            r['is_low_stock'] = r['quantity'] <= r['min_threshold']

        return jsonify({'success': True, 'data': resources}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@resources_bp.route('/api/resources', methods=['POST'])
@role_required('admin')
def create_resource():
    """Add a new resource. Admin only. JSON: {name, category, quantity, unit, min_threshold, location}"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required.'}), 400

        name = data.get('name', '').strip()
        category = data.get('category', '').strip()
        valid_cats = ['shelter', 'medical', 'food_water', 'rescue_equipment']

        if not name:
            return jsonify({'success': False, 'message': 'Resource name is required.'}), 400
        if category not in valid_cats:
            return jsonify({'success': False, 'message': f'Category must be: {", ".join(valid_cats)}'}), 400

        unit = data.get('unit', '').strip()
        if not unit:
            return jsonify({'success': False, 'message': 'Unit is required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO resources (name, category, quantity, unit, min_threshold, location)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            name, category,
            int(data.get('quantity', 0)),
            unit,
            int(data.get('min_threshold', 10)),
            data.get('location', '').strip() or None
        ))
        rid = cursor.lastrowid
        conn.commit()
        return jsonify({'success': True, 'message': 'Resource added.', 'data': {'id': rid}}), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@resources_bp.route('/api/resources/<int:resource_id>', methods=['PUT'])
@role_required('admin')
def update_resource(resource_id):
    """Update a resource quantity, threshold, or details. Admin only."""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM resources WHERE id=%s", (resource_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Resource not found.'}), 404

        updates, values = [], []
        for f in ['name', 'category', 'unit', 'location']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(data[f])
        for f in ['quantity', 'min_threshold']:
            if f in data:
                updates.append(f"{f} = %s")
                values.append(int(data[f]))

        if not updates:
            return jsonify({'success': False, 'message': 'No fields to update.'}), 400

        values.append(resource_id)
        cursor.execute(f"UPDATE resources SET {', '.join(updates)} WHERE id=%s", values)
        conn.commit()
        return jsonify({'success': True, 'message': 'Resource updated.'}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@resources_bp.route('/api/resources/<int:resource_id>/restock', methods=['PUT'])
@role_required('admin')
def restock_resource(resource_id):
    """Restock a resource – add quantity. Admin only. JSON: {quantity}"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data or 'quantity' not in data:
            return jsonify({'success': False, 'message': 'Quantity is required.'}), 400

        add_qty = int(data['quantity'])
        if add_qty <= 0:
            return jsonify({'success': False, 'message': 'Quantity must be positive.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, name, quantity FROM resources WHERE id=%s", (resource_id,))
        res = cursor.fetchone()
        if not res:
            return jsonify({'success': False, 'message': 'Resource not found.'}), 404

        new_qty = res['quantity'] + add_qty
        cursor.execute("UPDATE resources SET quantity=%s, last_restocked=NOW() WHERE id=%s",
                       (new_qty, resource_id))
        conn.commit()

        return jsonify({
            'success': True,
            'message': f'{res["name"]} restocked. New quantity: {new_qty}.',
            'data': {'id': resource_id, 'new_quantity': new_qty}
        }), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@resources_bp.route('/api/resources/<int:resource_id>', methods=['DELETE'])
@role_required('admin')
def delete_resource(resource_id):
    """Delete a resource. Admin only."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM resources WHERE id=%s", (resource_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Resource not found.'}), 404

        cursor.execute("DELETE FROM resources WHERE id=%s", (resource_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Resource deleted.'}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


@resources_bp.route('/api/resources/stats', methods=['GET'])
@login_required
def get_resource_stats():
    """Resource statistics for dashboard."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) as c FROM resources")
        total = cursor.fetchone()['c']
        cursor.execute("SELECT COUNT(*) as c FROM resources WHERE quantity <= min_threshold")
        low = cursor.fetchone()['c']
        cursor.execute("SELECT category, COUNT(*) as items, SUM(quantity) as total_qty FROM resources GROUP BY category")
        by_cat = []
        for r in cursor.fetchall():
            by_cat.append({'category': r['category'], 'items': r['items'], 'total_quantity': int(r['total_qty'] or 0)})

        return jsonify({
            'success': True,
            'data': {'total': total, 'low_stock': low, 'by_category': by_cat}
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)
