import sqlite3
import hashlib
import json
import time

DB_FILE = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Projects Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT UNIQUE,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
    ''')

    # BOQ Descriptions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS boq_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            boq_number TEXT,
            description TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # BOQ Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS boqs (
            boq_number TEXT PRIMARY KEY,
            project_id INTEGER,
            project_name TEXT,
            contractor_name TEXT,
            sub_contractor_name TEXT,
            date_commencement TEXT,
            finish_date TEXT,
            prev_bill_date TEXT,
            prev_bill_number TEXT,
            prev_bill_amount REAL DEFAULT 0
        )
    ''')
    
    # Managers Authentication Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS managers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password_hash TEXT,
            otp TEXT,
            otp_expiry REAL,
            failed_attempts INTEGER DEFAULT 0
        )
    ''')
    
    # Measurements table
    c.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_number TEXT,
            project_id INTEGER,
            project_name TEXT,
            contractor_name TEXT,
            sub_contractor_name TEXT,
            date_commencement TEXT,
            finish_date TEXT,
            date_measurement TEXT,
            description TEXT,
            number_items REAL,
            length REAL,
            breadth REAL,
            depth_height REAL,
            quantity REAL,
            remarks TEXT,
            gps_coordinates TEXT,
            selfie_image BLOB,
            site_photo_image BLOB,
            hash_value TEXT,
            timestamp TEXT,
            
            -- Billing fields
            rate REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            prev_bill_amount REAL DEFAULT 0,
            prev_bill_date TEXT,
            prev_bill_number TEXT,
            total_payable REAL DEFAULT 0,
            
            -- Status 
            status TEXT DEFAULT 'Pending',
            is_deleted INTEGER DEFAULT 0,
            FOREIGN KEY (boq_number) REFERENCES boqs (boq_number)
        )
    ''')

    # Billing Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            bill_no TEXT,
            bill_date TEXT,
            bill_name TEXT,
            amount REAL,
            status TEXT DEFAULT 'Approved',
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    ''')
    
    # Ensure project_id column exists on old DBs
    for table in ['measurements', 'boqs']:
        c.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in c.fetchall()]
        if 'project_id' not in columns:
            c.execute(f"ALTER TABLE {table} ADD COLUMN project_id INTEGER")
            
    # Data migration
    from datetime import datetime
    try:
        c.execute("SELECT DISTINCT project_name FROM measurements WHERE project_name IS NOT NULL")
        existing_projects = c.fetchall()
        for (p_name,) in existing_projects:
            c.execute("INSERT OR IGNORE INTO projects (project_name, status, created_at) VALUES (?, 'active', ?)", 
                      (p_name, datetime.now().isoformat()))
        
        c.execute("SELECT id, project_name FROM projects")
        projects = c.fetchall()
        for p_id, p_name in projects:
            c.execute("UPDATE measurements SET project_id = ? WHERE project_name = ? AND project_id IS NULL", (p_id, p_name))
            c.execute("UPDATE boqs SET project_id = ? WHERE project_name = ? AND project_id IS NULL", (p_id, p_name))
            
        # Migrate boq_descriptions schema if necessary
        c.execute("PRAGMA table_info(boq_descriptions)")
        boq_cols = [col[1] for col in c.fetchall()]
        if 'project_id' not in boq_cols:
            c.execute('ALTER TABLE boq_descriptions RENAME TO boq_descriptions_old')
            c.execute('''
                CREATE TABLE boq_descriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    boq_number TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'active'
                )
            ''')
            c.execute('''
                INSERT INTO boq_descriptions (boq_number, description)
                SELECT CAST(boq_number AS TEXT), description_of_work FROM boq_descriptions_old
            ''')
            
            # Assume first project for orphaned descriptions
            c.execute("SELECT id FROM projects LIMIT 1")
            first_p = c.fetchone()
            if first_p:
                c.execute("UPDATE boq_descriptions SET project_id = ?", (first_p[0],))
                
        c.execute("PRAGMA table_info(boq_descriptions)")
        boq_cols_new = [col[1] for col in c.fetchall()]
        if 'status' not in boq_cols_new:
            c.execute("ALTER TABLE boq_descriptions ADD COLUMN status TEXT DEFAULT 'active'")
            
    except Exception as e:
        print(f"Migration error: {e}")
        
    conn.commit()
    
    # Insert default manager if none exists
    c.execute("SELECT COUNT(*) FROM managers")
    if c.fetchone()[0] == 0:
        default_email = "manager@klecivil.com"
        default_pw = "Klecivil@123"
        hashed_pw = hashlib.sha256(default_pw.encode()).hexdigest()
        c.execute('''
            INSERT INTO managers (email, password_hash, failed_attempts)
            VALUES (?, ?, 0)
        ''', (default_email, hashed_pw))
        conn.commit()
        
    conn.close()

def generate_hash(boq_number, project_name, description, length, breadth, depth_height, quantity, gps, timestamp):
    record_string = f"{boq_number}{project_name}{length}{breadth}{depth_height}{quantity}{gps}{timestamp}"
    return hashlib.sha256(record_string.encode()).hexdigest()

def insert_measurement(boq_number, project_name, project_id, contractor_name, sub_contractor_name, date_commencement, finish_date, date_measurement, 
                       description, number_items, length, breadth, depth_height, quantity, 
                       remarks, gps_coordinates, selfie_image, site_photo_image, timestamp):
    
    hash_value = generate_hash(boq_number, project_name, description, length, breadth, depth_height, quantity, gps_coordinates, timestamp)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO measurements (
            boq_number, project_name, project_id, contractor_name, sub_contractor_name, date_commencement, finish_date, date_measurement,
            description, number_items, length, breadth, depth_height, quantity,
            remarks, gps_coordinates, selfie_image, site_photo_image, hash_value, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (boq_number, project_name, project_id, contractor_name, sub_contractor_name, date_commencement, finish_date, date_measurement,
          description, number_items, length, breadth, depth_height, quantity,
          remarks, gps_coordinates, selfie_image, site_photo_image, hash_value, timestamp))
    conn.commit()
    conn.close()
    return hash_value

def add_boq_description(project_id, boq_number, description):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Check if BOQ number already exists for this project
    c.execute("SELECT id FROM boq_descriptions WHERE project_id=? AND boq_number=?", (project_id, str(boq_number)))
    if c.fetchone():
        conn.close()
        return False, "BOQ number already exists for this project."
        
    try:
        c.execute('''
            INSERT INTO boq_descriptions (project_id, boq_number, description)
            VALUES (?, ?, ?)
        ''', (project_id, str(boq_number), description))
        conn.commit()
        success = True
        msg = "Success"
    except Exception as e:
        success = False
        msg = str(e)
    conn.close()
    return success, msg

def edit_boq_description(project_id, boq_number, new_description):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE boq_descriptions
            SET description = ?
            WHERE project_id = ? AND boq_number = ?
        ''', (new_description, project_id, str(boq_number)))
        conn.commit()
        success = True
    except Exception:
        success = False
    conn.close()
    return success

def delete_boq_description(project_id, boq_number):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Check if any measurements exist (including soft-deleted ones)
    c.execute("SELECT COUNT(*) FROM measurements WHERE project_id=? AND boq_number=?", (project_id, str(boq_number)))
    count = c.fetchone()[0]
    if count > 0:
        conn.close()
        return False, "Cannot delete BOQ because it has associated measurements."
        
    try:
        c.execute("UPDATE boq_descriptions SET status='inactive' WHERE project_id=? AND boq_number=?", (project_id, str(boq_number)))
        conn.commit()
        success = True
        msg = "BOQ deleted effectively."
    except Exception as e:
        success = False
        msg = str(e)
    conn.close()
    return success, msg

def get_boq_description(project_id, boq_number):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("""
        SELECT description 
        FROM boq_descriptions
        WHERE project_id = ?
        AND boq_number = ?
        AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
    """, (project_id, str(boq_number)))

    result = c.fetchone()
    conn.close()

    if result:
        return result[0]
    else:
        return "No Description Available"

def get_boq_descriptions_for_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT boq_number, description 
        FROM boq_descriptions
        WHERE project_id = ? AND status = 'active'
        ORDER BY CAST(boq_number AS INTEGER) ASC
    """, (project_id,))
    columns = [description[0] for description in c.description]
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append(dict(zip(columns, row)))
    return results

def get_all_measurements():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM measurements")
    columns = [description[0] for description in c.description]
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append(dict(zip(columns, row)))
    return results

def get_measurement_by_id(measurement_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM measurements WHERE id=?", (measurement_id,))
    columns = [description[0] for description in c.description]
    row = c.fetchone()
    conn.close()
    
    if row:
        return dict(zip(columns, row))
    return None

def soft_delete_measurement(measurement_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Only allow delete if status is not Approved
    c.execute("SELECT status FROM measurements WHERE id=?", (measurement_id,))
    res = c.fetchone()
    if not res:
        conn.close()
        return False, "Measurement not found."
    if res[0] == 'Approved':
        conn.close()
        return False, "Cannot delete an approved measurement."
        
    c.execute("UPDATE measurements SET is_deleted=1, status='Deleted' WHERE id=?", (measurement_id,))
    conn.commit()
    conn.close()
    return True, "Measurement successfully marked as deleted."

def verify_tampering(measurement_id):
    record = get_measurement_by_id(measurement_id)
    if not record:
        return False, "Record not found", None
        
    expected_hash = record['hash_value']
    actual_hash = generate_hash(
        record['boq_number'],
        record['project_name'], 
        record['description'], 
        record['length'], 
        record['breadth'], 
        record['depth_height'], 
        record['quantity'], 
        record['gps_coordinates'], 
        record['timestamp']
    )
    
    is_valid = expected_hash == actual_hash
    return is_valid, expected_hash, actual_hash

# --- Project Management Functions ---

def add_project(project_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    from datetime import datetime
    try:
        c.execute("INSERT INTO projects (project_name, status, created_at) VALUES (?, 'active', ?)", 
                  (project_name, datetime.now().isoformat()))
        conn.commit()
        success = True
        msg = "Project added successfully."
    except sqlite3.IntegrityError:
        success = False
        msg = "Project name already exists."
    conn.close()
    return success, msg

def edit_project(project_id, new_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("UPDATE projects SET project_name = ? WHERE id = ?", (new_name, project_id))
        c.execute("UPDATE measurements SET project_name = ? WHERE project_id = ?", (new_name, project_id))
        c.execute("UPDATE boqs SET project_name = ? WHERE project_id = ?", (new_name, project_id))
        conn.commit()
        success = True
        msg = "Project updated successfully."
    except sqlite3.IntegrityError:
        success = False
        msg = "Project name already exists."
    except Exception as e:
        success = False
        msg = str(e)
    conn.close()
    return success, msg

def soft_delete_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("UPDATE projects SET status = 'inactive' WHERE id = ?", (project_id,))
        conn.commit()
        success = True
    except Exception:
        success = False
    conn.close()
    return success

def get_all_projects(active_only=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if active_only:
        c.execute("SELECT * FROM projects WHERE status = 'active' ORDER BY project_name ASC")
    else:
        c.execute("SELECT * FROM projects ORDER BY project_name ASC")
    columns = [description[0] for description in c.description] if c.description else []
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append(dict(zip(columns, row)))
    return results

if __name__ == '__main__':
    init_db()
