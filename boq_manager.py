import sqlite3
from database import DB_FILE

def get_or_create_boq(boq_number, project_name, project_id, contractor_name, sub_contractor_name, date_commencement, finish_date):
    """
    Retrieves a BOQ or creates it if it doesn't exist.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT * FROM boqs WHERE boq_number=?", (boq_number,))
    columns = [description[0] for description in c.description] if c.description else []
    row = c.fetchone()
    
    if not row:
        c.execute('''
            INSERT INTO boqs (boq_number, project_name, project_id, contractor_name, sub_contractor_name, date_commencement, finish_date, prev_bill_date, prev_bill_number, prev_bill_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, '', '', 0.0)
        ''', (boq_number, project_name, project_id, contractor_name, sub_contractor_name, date_commencement, finish_date))
        conn.commit()
        # Fetch the newly created record
        c.execute("SELECT * FROM boqs WHERE boq_number=?", (boq_number,))
        row = c.fetchone()
        
    conn.close()
    if row:
        return dict(zip(columns, row))
    return None

def get_latest_bill_for_project_boq(project_id, boq_number):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT bill_no, bill_date, amount FROM billing WHERE project_id=? AND boq_number=? ORDER BY id DESC LIMIT 1", (project_id, str(boq_number)))
    row = c.fetchone()
    conn.close()
    if row:
        return {'bill_no': row[0], 'bill_date': row[1], 'amount': row[2]}
    return None

def get_latest_bill_for_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT bill_no, bill_date, amount FROM billing WHERE project_id=? AND status='Approved' ORDER BY id DESC LIMIT 1", (project_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {'bill_no': row[0], 'bill_date': row[1], 'amount': row[2]}
    return None

def get_all_boqs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boqs ORDER BY CAST(boq_number AS INTEGER) ASC")
    columns = [description[0] for description in c.description]
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append(dict(zip(columns, row)))
    return results

def get_boq(boq_number):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boqs WHERE boq_number=?", (boq_number,))
    columns = [description[0] for description in c.description]
    row = c.fetchone()
    conn.close()
    
    if row:
        return dict(zip(columns, row))
    return None

def update_billing_and_boq(measurement_id, project_id, rate, quantity, amount, prev_bill_amount, prev_bill_date, prev_bill_number, total_payable):
    """
    Updates the measurement record with billing info, AND updates the master BOQ
    record so the next bill pulls these newly updated 'previous' values.
    Also inserts into the new project-specific billing table.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Update measurement
    c.execute('''
        UPDATE measurements 
        SET rate=?, amount=?, prev_bill_amount=?, prev_bill_date=?, prev_bill_number=?, total_payable=?, status='Approved'
        WHERE id=?
    ''', (rate, amount, prev_bill_amount, prev_bill_date, prev_bill_number, total_payable, measurement_id))
    
    # 3. Get the boq_number for this measurement to update the BOQ master
    c.execute("SELECT boq_number FROM measurements WHERE id=?", (measurement_id,))
    res = c.fetchone()
    boq_num = res[0] if res else "Unknown"
    
    # 2. Compute project-level Bill Number dynamically and Insert into billing
    c.execute("SELECT COUNT(*) FROM billing WHERE project_id=?", (project_id,))
    bill_count = c.fetchone()[0]
    new_prev_bill_number = f"Bill {bill_count + 1}"
    
    from datetime import date
    today_str = date.today().isoformat()
    
    c.execute('''
        INSERT INTO billing (project_id, boq_number, bill_no, bill_date, bill_name, amount, rate, quantity, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Approved')
    ''', (project_id, boq_num, new_prev_bill_number, today_str, f"Bill for Measurement {measurement_id}", total_payable, rate, quantity))

    if res:
        # Make the current bill the "previous bill" for the next measurement
        c.execute('''
            UPDATE boqs
            SET prev_bill_date=?, prev_bill_number=?, prev_bill_amount=?
            WHERE boq_number=?
        ''', (today_str, new_prev_bill_number, total_payable, boq_num))
        
    conn.commit()
    conn.close()

def create_project_bill_by_id(project_id, boq_number, rate, quantity, current_amount, total_payable, measurement_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Compute project-level Bill Number dynamically using MAX
    c.execute("SELECT MAX(CAST(SUBSTR(bill_no, 6) AS INTEGER)) FROM billing WHERE project_id=? AND bill_no LIKE 'Bill %'", (project_id,))
    max_val = c.fetchone()[0]
    next_num = (max_val if max_val else 0) + 1
    new_prev_bill_number = f"Bill {next_num}"
    
    from datetime import date
    today_str = date.today().isoformat()
    
    c.execute('''
        INSERT INTO billing (project_id, boq_number, bill_no, bill_date, bill_name, amount, rate, quantity, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Approved')
    ''', (project_id, str(boq_number), new_prev_bill_number, today_str, f"Bill for BOQ {boq_number} (ID {measurement_id})", total_payable, rate, quantity))

    # Update the single selected measurement to billed
    c.execute('''
        UPDATE measurements 
        SET rate=?, amount=?, prev_bill_amount=?, prev_bill_date=?, prev_bill_number=?, total_payable=?, billed=1, status='billed'
        WHERE id=? AND project_id=? AND billed=0
    ''', (rate, current_amount, total_payable - current_amount, today_str, new_prev_bill_number, total_payable, measurement_id, project_id))
    
    # Update master BOQ record
    c.execute('''
        UPDATE boqs
        SET prev_bill_date=?, prev_bill_number=?, prev_bill_amount=?
        WHERE boq_number=? AND project_id=?
    ''', (today_str, new_prev_bill_number, total_payable, str(boq_number), project_id))
    
    conn.commit()
    conn.close()

def get_total_approved_amount_for_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM billing WHERE project_id=? AND status='Approved'", (project_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res and res[0] else 0.0

def get_unbilled_quantity_for_boq(project_id, boq_number):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT SUM(quantity)
        FROM measurements
        WHERE project_id = ? AND boq_number = ? AND status = 'Approved' AND billed = 0
    ''', (project_id, str(boq_number)))
    res = c.fetchone()
    conn.close()
    return res[0] if res and res[0] else 0.0

def get_unbilled_measurements_for_project_id_selection(project_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, boq_number, quantity
        FROM measurements
        WHERE project_id = ? AND status IN ('Pending', 'Approved') AND is_deleted = 0 AND billed = 0
        ORDER BY id ASC
    ''', (project_id,))
    rows = c.fetchall()
    conn.close()
    return [{'id': r[0], 'boq_number': r[1], 'quantity': r[2] or 0.0} for r in rows]
