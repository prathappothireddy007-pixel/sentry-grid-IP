"""
SentryGrid – Idempotent Database Migrations
===========================================
Safely creates new tables (hospitals, missing_persons, resource_movements)
and adds necessary audit columns without dropping or modifying existing data.
CSA4310 – Internet Programming
"""

import os
import sys

# Ensure parent directory (sentrygrid root) is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_db_connection, close_db_connection, _use_fallback

def run_migrations():
    print("=" * 65)
    print("  SentryGrid Database Migrations Runner")
    print("=" * 65)
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        is_sqlite = _use_fallback or hasattr(conn, 'conn')
        cursor = conn.cursor()

        print(f"[*] Detected database mode: {'SQLite Fallback' if is_sqlite else 'MySQL 8.0'}")

        # 1. Hospitals Table
        print("[1/4] Ensuring 'hospitals' table exists...")
        if is_sqlite:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hospitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                contact_phone TEXT,
                emergency_department INTEGER DEFAULT 1,
                total_beds INTEGER DEFAULT 0,
                available_beds INTEGER DEFAULT 0,
                trauma_level TEXT DEFAULT 'Level 1 Trauma Center',
                services TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            """)
        else:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hospitals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                address VARCHAR(500) NOT NULL,
                latitude DECIMAL(10, 8) NOT NULL,
                longitude DECIMAL(11, 8) NOT NULL,
                contact_phone VARCHAR(30),
                emergency_department BOOLEAN DEFAULT TRUE,
                total_beds INT DEFAULT 0,
                available_beds INT DEFAULT 0,
                trauma_level VARCHAR(50) DEFAULT 'Level 1 Trauma Center',
                services TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            """)

        # Seed sample hospitals if empty
        cursor.execute("SELECT COUNT(*) FROM hospitals")
        row = cursor.fetchone()
        hosp_count = row[0] if (row and not isinstance(row, dict)) else (row.get('COUNT(*)', 0) if row else 0)
        if hosp_count == 0:
            print("  -> Seeding demonstration hospitals...")
            sample_hospitals = [
                ('Rajiv Gandhi Government General Hospital (RGGGH)', 'EVR Periyar Salai, Park Town, Chennai, Tamil Nadu 600003', 13.0805, 80.2785, '044-25305000', 1, 850, 142, 'Level 1 Trauma Center', '24/7 ER, Cardiac ICU, Burn Care, Trauma Surgery, Blood Bank', 1),
                ('Apollo Speciality Hospital – Greams Road', '21 Greams Lane, Thousand Lights, Chennai, Tamil Nadu 600006', 13.0569, 80.2503, '044-28290200', 1, 560, 48, 'Level 1 Trauma Center', 'Emergency ICU, Neurosurgery, Organ Transplant, Hyperbaric Oxygen', 1),
                ('Government Kilpauk Medical College Hospital (KMC)', 'Poonamallee High Rd, Kilpauk, Chennai, Tamil Nadu 600010', 13.0806, 80.2435, '044-28364951', 1, 420, 85, 'Level 2 Trauma Center', 'Specialized Burns Unit, Pediatric Trauma, Orthopedic Emergency', 1),
                ('Kalyani General & Trauma Care Center', '142 Trunk Road, Velachery Sector, Chennai, Tamil Nadu 600042', 12.9810, 80.2215, '044-22448899', 1, 220, 31, 'Level 3 Community Trauma', 'Emergency Triage, Flood Casualty Care, Fracture Ward', 1),
                ('Fortis Malar Hospital – Adyar', '52 1st Main Rd, Gandhi Nagar, Adyar, Chennai, Tamil Nadu 600020', 13.0075, 80.2570, '044-42892222', 1, 180, 24, 'Level 2 Trauma Center', 'Cardiac Emergency, Emergency Dialysis, Critical Care', 1)
            ]
            q = "INSERT INTO hospitals (name, address, latitude, longitude, contact_phone, emergency_department, total_beds, available_beds, trauma_level, services, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            if is_sqlite: q = q.replace('%s', '?')
            for h in sample_hospitals:
                cursor.execute(q, h)
            conn.commit()

        # 2. Missing Persons Table
        print("[2/4] Ensuring 'missing_persons' table exists...")
        if is_sqlite:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS missing_persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_number TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                photo_path TEXT,
                last_seen_date TEXT,
                last_seen_location TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                description TEXT,
                emergency_request_id INTEGER,
                contact_name TEXT,
                contact_phone TEXT,
                status TEXT DEFAULT 'Reported',
                reported_by INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            """)
        else:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS missing_persons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                case_number VARCHAR(50) UNIQUE NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                age INT,
                gender VARCHAR(20),
                photo_path VARCHAR(500),
                last_seen_date DATETIME,
                last_seen_location VARCHAR(255) NOT NULL,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                description TEXT,
                emergency_request_id INT NULL,
                contact_name VARCHAR(100),
                contact_phone VARCHAR(30),
                status ENUM('Reported', 'Under Review', 'Search Active', 'Located', 'Closed', 'Invalid/Duplicate') DEFAULT 'Reported',
                reported_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (reported_by) REFERENCES users(id),
                FOREIGN KEY (emergency_request_id) REFERENCES emergency_requests(id) ON DELETE SET NULL
            );
            """)

        cursor.execute("SELECT COUNT(*) FROM missing_persons")
        row = cursor.fetchone()
        mp_count = row[0] if (row and not isinstance(row, dict)) else (row.get('COUNT(*)', 0) if row else 0)
        if mp_count == 0:
            print("  -> Seeding demonstration missing person cases...")
            sample_mp = [
                ('MP-2026-0001', 'Anandhi Selvam', 68, 'Female', None, '2026-11-01 16:30:00', 'Near Velachery Bus Terminus, Chennai', 12.975669, 80.218209, 'Height 5ft 2in, wearing green cotton saree, silver spectacles. Speaks Tamil. Hard of hearing and requires diabetic medication.', 2, 'Karthik Selvam (Son)', '9876500111', 'Search Active', 1),
                ('MP-2026-0002', 'Rohan Verma', 11, 'Male', None, '2026-11-01 17:15:00', 'Anna Nagar Tower Park entrance, Chennai', 13.085000, 80.210000, 'Height 4ft 5in, blue t-shirt and grey shorts. Separated from family during sudden cloudburst evacuation.', None, 'Meera Verma (Mother)', '9876500222', 'Reported', 3),
                ('MP-2026-0003', 'Muthu Krishnan', 45, 'Male', None, '2026-11-01 14:00:00', 'Marina Beach Lighthouse Promenade, Chennai', 13.038400, 80.280000, 'Height 5ft 8in, fisherman raincoat, brown trousers. Missing after storm surge struck docking jetty.', 1, 'Revathi Krishnan (Wife)', '9876500333', 'Under Review', 1)
            ]
            q = "INSERT INTO missing_persons (case_number, full_name, age, gender, photo_path, last_seen_date, last_seen_location, latitude, longitude, description, emergency_request_id, contact_name, contact_phone, status, reported_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            if is_sqlite: q = q.replace('%s', '?')
            for mp in sample_mp:
                cursor.execute(q, mp)
            conn.commit()

        # 3. Resource Movements Table
        print("[3/4] Ensuring 'resource_movements' audit table exists...")
        if is_sqlite:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS resource_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                destination_type TEXT,
                destination_id INTEGER,
                notes TEXT,
                performed_by INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """)
        else:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS resource_movements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                resource_id INT NOT NULL,
                movement_type ENUM('restock', 'allocated', 'dispatched', 'adjusted') NOT NULL,
                quantity INT NOT NULL,
                destination_type VARCHAR(50),
                destination_id INT NULL,
                notes TEXT,
                performed_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE,
                FOREIGN KEY (performed_by) REFERENCES users(id)
            );
            """)

        cursor.execute("SELECT COUNT(*) FROM resource_movements")
        row = cursor.fetchone()
        rm_count = row[0] if (row and not isinstance(row, dict)) else (row.get('COUNT(*)', 0) if row else 0)
        if rm_count == 0:
            print("  -> Seeding demonstration relief allocations...")
            sample_rm = [
                (1, 'restock', 100, 'direct', None, 'Central warehouse intake delivery - 100 Family Tents received', 1),
                (1, 'allocated', 30, 'shelter', 1, 'Dispatched 30 Tents to Anna Nagar Relief Camp due to overflow', 1),
                (3, 'allocated', 40, 'hospital', 1, 'Emergency trauma medicine kits delivered to RGGGH General Hospital', 1),
                (4, 'restock', 250, 'direct', None, 'Procured 250 cartons of bottled drinking water for monsoon relief', 1)
            ]
            q = "INSERT INTO resource_movements (resource_id, movement_type, quantity, destination_type, destination_id, notes, performed_by) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            if is_sqlite: q = q.replace('%s', '?')
            for rm in sample_rm:
                cursor.execute(q, rm)
            conn.commit()

        # 4. Optional column additions to emergency_requests (tracking_code, affected_count)
        print("[4/4] Checking and upgrading columns in 'emergency_requests'...")
        try:
            if not is_sqlite:
                cursor.execute("SHOW COLUMNS FROM emergency_requests LIKE 'tracking_code'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE emergency_requests ADD COLUMN tracking_code VARCHAR(50) NULL AFTER id")
                    cursor.execute("UPDATE emergency_requests SET tracking_code = CONCAT('SG-2026-', LPAD(id, 4, '0')) WHERE tracking_code IS NULL")
                    conn.commit()
                    print("  -> Added column 'tracking_code' to emergency_requests.")

                cursor.execute("SHOW COLUMNS FROM emergency_requests LIKE 'affected_count'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE emergency_requests ADD COLUMN affected_count INT DEFAULT 1 AFTER description")
                    conn.commit()
                    print("  -> Added column 'affected_count' to emergency_requests.")
            else:
                # SQLite column inspection
                cursor.execute("PRAGMA table_info(emergency_requests)")
                cols = [r[1] for r in cursor.fetchall()]
                if 'tracking_code' not in cols:
                    cursor.execute("ALTER TABLE emergency_requests ADD COLUMN tracking_code TEXT")
                    conn.commit()
                if 'affected_count' not in cols:
                    cursor.execute("ALTER TABLE emergency_requests ADD COLUMN affected_count INTEGER DEFAULT 1")
                    conn.commit()
        except Exception as col_err:
            print(f"  Column upgrade notice: {col_err}")

        print("\n[OK] All database migrations completed successfully!")
        return True
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        return False
    finally:
        close_db_connection(conn, cursor)

if __name__ == '__main__':
    run_migrations()
