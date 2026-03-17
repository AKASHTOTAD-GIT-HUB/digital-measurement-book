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

def get_latest_bill_for_project(project_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT bill_no, bill_date, amount FROM billing WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {'bill_no': row[0], 'bill_date': row[1], 'amount': row[2]}
    return None

def get_all_boqs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM boqs")
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

def update_billing_and_boq(measurement_id, project_id, rate, amount, prev_bill_amount, prev_bill_date, prev_bill_number, total_payable):
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
    
    # 2. Insert into billing
    from datetime import date
    today_str = date.today().isoformat()
    new_prev_bill_number = f"BILL-{measurement_id}"
    
    c.execute('''
        INSERT INTO billing (project_id, bill_no, bill_date, bill_name, amount, status)
        VALUES (?, ?, ?, ?, ?, 'Approved')
    ''', (project_id, new_prev_bill_number, today_str, f"Bill for Measurement {measurement_id}", total_payable))

    # 3. Get the boq_number for this measurement to update the BOQ master
    c.execute("SELECT boq_number FROM measurements WHERE id=?", (measurement_id,))
    res = c.fetchone()
    if res:
        boq_num = res[0]
        # Make the current bill the "previous bill" for the next measurement
        c.execute('''
            UPDATE boqs
            SET prev_bill_date=?, prev_bill_number=?, prev_bill_amount=?
            WHERE boq_number=?
        ''', (today_str, new_prev_bill_number, total_payable, boq_num))
        
    conn.commit()
    conn.close()
