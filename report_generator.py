import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from database import get_measurement_by_id, verify_tampering
import tempfile
from boq_manager import get_total_approved_amount_for_project

def generate_pdf_report(measurement_id):
    record = get_measurement_by_id(measurement_id)
    if not record:
        return None
        
    is_valid, expected, actual = verify_tampering(measurement_id)
    
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        alignment=1, # Center
        spaceAfter=20
    )
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Header
    elements.append(Paragraph("<b>PUBLIC WORKS DEPARTMENT</b>", title_style))
    elements.append(Paragraph("<b>Project Billing Report</b>", title_style))
    elements.append(Spacer(1, 10))
    
    # FETCH EXACT BILLING INFO if this is a billed measurement
    import sqlite3
    import database
    
    bill_no = record.get('prev_bill_number')
    pdf_qty = record.get('quantity', 0)
    pdf_rate = record.get('rate', 0)
    pdf_curr_bill = record.get('amount', 0)
    
    prev_b_no = "N/A"
    prev_b_date = "N/A"
    prev_b_amt = 0.0
    
    if bill_no and bill_no != "-":
        conn = sqlite3.connect(database.DB_FILE)
        c = conn.cursor()
        
        # 1. Fetch THIS bill's actual consolidated values
        c.execute("SELECT quantity, rate, amount FROM billing WHERE project_id=? AND bill_no=?", (record['project_id'], bill_no))
        bill_row = c.fetchone()
        if bill_row:
            pdf_qty = bill_row[0]
            pdf_rate = bill_row[1]
            pdf_curr_bill = bill_row[2]
            
        # 2. Fetch the true PREVIOUS bill for this exact Project
        c.execute("SELECT bill_no, bill_date, amount FROM billing WHERE project_id=? AND id < (SELECT id FROM billing WHERE project_id=? AND bill_no=?) ORDER BY id DESC LIMIT 1", (record['project_id'], record['project_id'], bill_no))
        prev_row = c.fetchone()
        if prev_row:
            prev_b_no = prev_row[0]
            prev_b_date = prev_row[1]
            prev_b_amt = prev_row[2]
            
        conn.close()
    
    # 📄 HEADER:
    info_data = [
        ["Project Name:", record['project_name']],
        ["BOQ Number:", record['boq_number']],
        ["Bill Number:", bill_no or "N/A"],
        ["Date:", record['prev_bill_date'] or record['date_measurement']]
    ]
    info_table = Table(info_data, colWidths=[150, 350])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # 👷 DETAILS:
    elements.append(Paragraph("<b>Contractor Details</b>", heading_style))
    det_data = [
        ["Contractor Name:", record['contractor_name']],
        ["Subcontractor Name:", record['sub_contractor_name']],
        ["Measurement Date:", record['date_measurement']]
    ]
    det_table = Table(det_data, colWidths=[150, 350])
    det_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(det_table)
    elements.append(Spacer(1, 20))
    
    # 📊 TABLE:
    elements.append(Paragraph("<b>Billing Description</b>", heading_style))
    meas_data = [
        ["Selected BOQ ID", "Quantity (from that BOQ only)", "Rate", "Current Bill Amount"],
        [str(record['boq_number']), f"{pdf_qty:.3f}", f"₹ {float(pdf_rate):.2f}", f"₹ {float(pdf_curr_bill):.2f}"]
    ]
    meas_table = Table(meas_data, colWidths=[110, 160, 70, 110])
    meas_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4a4a4a")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f5f5f5")),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    elements.append(meas_table)
    elements.append(Spacer(1, 20))
    
    # 💰 BILL SUMMARY:
    elements.append(Paragraph("<b>Bill Summary</b>", heading_style))
    total_approved = get_total_approved_amount_for_project(record['project_id'])
    bill_data = [
        ["Previous Bill No:", str(prev_b_no)],
        ["Previous Bill Date:", str(prev_b_date)],
        ["Previous Bill Amount:", f"₹ {float(prev_b_amt):.2f}"],
        ["Current Bill Amount:", f"₹ {float(pdf_curr_bill):.2f}"],
        ["Total Approved Amount:", f"₹ {float(total_approved):.2f}"]
    ]
    bill_table = Table(bill_data, colWidths=[200, 200])
    bill_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f9f9f9")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(bill_table)
    elements.append(Spacer(1, 20))
    
    # Site Verification and Blockchain
    elements.append(Paragraph("<b>Site Verification & Blockchain Record</b>", heading_style))
    veri_data = [
        ["GPS Coordinates:", record['gps_coordinates']],
        ["Timestamp:", record['timestamp']],
        ["Blockchain Hash:", record['hash_value']],
        ["Tamper Check:", "Valid" if is_valid else "⚠ TAMPERED"]
    ]
    veri_table = Table(veri_data, colWidths=[150, 350])
    veri_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1,3), (1,3), colors.green if is_valid else colors.red),
    ]))
    elements.append(veri_table)
    elements.append(Spacer(1, 20))
    
    # Image
    if record.get('selfie_image'):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                tmp.write(record['selfie_image'])
                tmp_path = tmp.name
                
            elements.append(Paragraph("<b>Engineer Verification (Selfie):</b>", styles['Heading4']))
            img = Image(tmp_path, width=200, height=200)
            elements.append(img)
            elements.append(Spacer(1, 10))
            
        except Exception as e:
            elements.append(Paragraph(f"<i>Could not load selfie photo: {e}</i>", normal_style))

    if record.get('site_photo_image'):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                tmp.write(record['site_photo_image'])
                tmp_path = tmp.name
                
            elements.append(Paragraph("<b>Site Work Photo:</b>", styles['Heading4']))
            img = Image(tmp_path, width=300, height=200)
            elements.append(img)
            
        except Exception as e:
            elements.append(Paragraph(f"<i>Could not load site photo: {e}</i>", normal_style))
            
    doc.build(elements)
    return output.getvalue()
