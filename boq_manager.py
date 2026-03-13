import sqlite3
from database import DB_FILE

def get_or_create_boq(boq_number, project_name, contractor_name, sub_contractor_name, date_commencement, finish_date):
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
            INSERT INTO boqs (boq_number, project_name, contractor_name, sub_contractor_name, date_commencement, finish_date, prev_bill_date, prev_bill_number, prev_bill_amount)
            VALUES (?, ?, ?, ?, ?, ?, '', '', 0.0)
        ''', (boq_number, project_name, contractor_name, sub_contractor_name, date_commencement, finish_date))
        conn.commit()
        # Fetch the newly created record
        c.execute("SELECT * FROM boqs WHERE boq_number=?", (boq_number,))
        row = c.fetchone()
        
    conn.close()
    if row:
        return dict(zip(columns, row))
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

def update_billing_and_boq(measurement_id, rate, amount, prev_bill_amount, prev_bill_date, prev_bill_number, total_payable):
    """
    Updates the measurement record with billing info, AND updates the master BOQ
    record so the next bill pulls these newly updated 'previous' values.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Update measurement
    c.execute('''
        UPDATE measurements 
        SET rate=?, amount=?, prev_bill_amount=?, prev_bill_date=?, prev_bill_number=?, total_payable=?, status='Approved'
        WHERE id=?
    ''', (rate, amount, prev_bill_amount, prev_bill_date, prev_bill_number, total_payable, measurement_id))
    
    # 2. Get the boq_number for this measurement to update the BOQ master
    c.execute("SELECT boq_number FROM measurements WHERE id=?", (measurement_id,))
    res = c.fetchone()
    if res:
        boq_num = res[0]
        # Make the current bill the "previous bill" for the next measurement
        # Normally the "current bill number" or date would be generated today.
        # Since the UI inputs prev_bill_number for this bill, the next "prev bill" 
        # should technically be the ONE WE JUST CREATED.
        
        # We will assume that `prev_bill_date` from the UI refers to the date of the PREVIOUS bill.
        # So we need to set the BOQ's prev_bill_date to TODAY, prev_bill_number to something, and prev_bill_amount to total_payable.
        # Let's say `total_payable` becomes the new `prev_bill_amount`.
        # For simplicity, let's just use the current date as the new prev_bill_date.
        from datetime import date
        today_str = date.today().isoformat()
        
        # Let's generate a "bill number" if not provided, or just use measurement id prefix
        new_prev_bill_number = f"BILL-{measurement_id}"
        
        c.execute('''
            UPDATE boqs
            SET prev_bill_date=?, prev_bill_number=?, prev_bill_amount=?
            WHERE boq_number=?
        ''', (today_str, new_prev_bill_number, total_payable, boq_num))
        
    conn.commit()
    conn.close()
