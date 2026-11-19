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

        # Log movement audit
        cursor.execute("""
            INSERT INTO resource_movements 
            (resource_id, movement_type, quantity, destination_type, destination_id, notes, performed_by)
            VALUES (%s, 'restock', %s, 'inventory', NULL, %s, %s)
        """, (resource_id, add_qty, data.get('notes', 'Stock replenished via console'), session['user_id']))

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


@resources_bp.route('/api/resources/<int:resource_id>/allocate', methods=['POST'])
@role_required('admin')
def allocate_resource(resource_id):
    """
    Allocate stock to a shelter, hospital, or field squad.
    Guarantees no negative inventory balance and records immutable movement log.
    JSON: {quantity, destination_type, destination_id, notes}
    """
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data or 'quantity' not in data:
            return jsonify({'success': False, 'message': 'Allocation quantity is required.'}), 400

        qty_to_allocate = int(data['quantity'])
        if qty_to_allocate <= 0:
            return jsonify({'success': False, 'message': 'Allocation quantity must be greater than zero.'}), 400

        dest_type = data.get('destination_type', 'shelter')
        dest_id = data.get('destination_id')
        notes = data.get('notes', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, name, quantity, unit FROM resources WHERE id=%s", (resource_id,))
        res = cursor.fetchone()
        if not res:
            return jsonify({'success': False, 'message': 'Resource not found.'}), 404

        if res['quantity'] < qty_to_allocate:
            return jsonify({
                'success': False,
                'message': f"Insufficient stock. Requested {qty_to_allocate} {res['unit']}, but only {res['quantity']} {res['unit']} available."
            }), 400

        new_qty = res['quantity'] - qty_to_allocate
        cursor.execute("UPDATE resources SET quantity=%s WHERE id=%s", (new_qty, resource_id))

        cursor.execute("""
            INSERT INTO resource_movements 
            (resource_id, movement_type, quantity, destination_type, destination_id, notes, performed_by)
            VALUES (%s, 'allocated', %s, %s, %s, %s, %s)
        """, (resource_id, qty_to_allocate, dest_type, dest_id, notes or None, session['user_id']))

        conn.commit()
        return jsonify({
            'success': True,
            'message': f"Successfully dispatched {qty_to_allocate} {res['unit']} of {res['name']}.",
            'data': {
                'id': resource_id,
                'allocated_quantity': qty_to_allocate,
                'remaining_stock': new_qty
            }
        }), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'Allocation failed: {str(e)}'}), 500
    finally:
        close_db_connection(conn, cursor)


@resources_bp.route('/api/resources/movements', methods=['GET'])
@login_required
def get_resource_movements():
    """
    Fetch complete audit trail of resource restocks and allocations.
    Returns chronological ledger with user names, destination details, and timestamps.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        res_id = request.args.get('resource_id')
        m_type = request.args.get('movement_type')

        query = """
            SELECT rm.id, rm.resource_id, rm.movement_type, rm.quantity,
                   rm.destination_type, rm.destination_id, rm.notes, rm.created_at,
                   r.name as resource_name, r.category as resource_category, r.unit,
                   u.full_name as performed_by_name, u.role as performed_by_role
            FROM resource_movements rm
            JOIN resources r ON rm.resource_id = r.id
            JOIN users u ON rm.performed_by = u.id
            WHERE 1=1
        """
        params = []
        if res_id:
            query += " AND rm.resource_id = %s"
            params.append(int(res_id))
        if m_type:
            query += " AND rm.movement_type = %s"
            params.append(m_type)

        query += " ORDER BY rm.created_at DESC LIMIT 100"
        cursor.execute(query, params)
        movements = cursor.fetchall()

        for m in movements:
            if m.get('created_at'):
                m['created_at'] = format_datetime(m['created_at'])

        return jsonify({'success': True, 'data': movements}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to retrieve audit trail: {str(e)}'}), 500
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
