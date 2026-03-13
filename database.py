import sqlite3
import hashlib
import json
import time

DB_FILE = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # BOQ Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS boqs (
            boq_number TEXT PRIMARY KEY,
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
            FOREIGN KEY (boq_number) REFERENCES boqs (boq_number)
        )
    ''')
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

def insert_measurement(boq_number, project_name, contractor_name, sub_contractor_name, date_commencement, finish_date, date_measurement, 
                       description, number_items, length, breadth, depth_height, quantity, 
                       remarks, gps_coordinates, selfie_image, site_photo_image, timestamp):
    
    hash_value = generate_hash(boq_number, project_name, description, length, breadth, depth_height, quantity, gps_coordinates, timestamp)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO measurements (
            boq_number, project_name, contractor_name, sub_contractor_name, date_commencement, finish_date, date_measurement,
            description, number_items, length, breadth, depth_height, quantity,
            remarks, gps_coordinates, selfie_image, site_photo_image, hash_value, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (boq_number, project_name, contractor_name, sub_contractor_name, date_commencement, finish_date, date_measurement,
          description, number_items, length, breadth, depth_height, quantity,
          remarks, gps_coordinates, selfie_image, site_photo_image, hash_value, timestamp))
    conn.commit()
    conn.close()
    return hash_value

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

if __name__ == '__main__':
    init_db()
