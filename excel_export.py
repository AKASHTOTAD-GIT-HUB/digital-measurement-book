import io
import pandas as pd
import sqlite3

from database import DB_FILE

def export_to_excel(measurement_id=None):
    """
    Exports measurements to an Excel file.
    """
    conn = sqlite3.connect(DB_FILE)
    
    query = "SELECT * FROM measurements"
    params = ()
    if measurement_id:
        query += " WHERE id=?"
        params = (measurement_id,)
        
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        return None
        
    # Sheet 1: Measurement entries
    measurement_cols = [
        'id', 'boq_number', 'project_name', 'contractor_name', 'sub_contractor_name', 'date_commencement', 'finish_date', 'date_measurement',
        'description', 'number_items', 'length', 'breadth', 'depth_height', 'quantity',
        'remarks', 'gps_coordinates', 'hash_value', 'timestamp', 'status'
    ]
    df_measurements = df[measurement_cols].copy()
    
    # Sheet 2: Billing details
    billing_cols = [
        'boq_number', 'project_name', 'description', 'number_items', 'length', 'breadth', 'depth_height', 'quantity',
        'rate', 'amount', 'prev_bill_number', 'prev_bill_date', 'prev_bill_amount', 'total_payable'
    ]
    df_billing = df[billing_cols].copy()
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_measurements.to_excel(writer, index=False, sheet_name='Measurements')
        df_billing.to_excel(writer, index=False, sheet_name='Billing')
        
    return output.getvalue()
