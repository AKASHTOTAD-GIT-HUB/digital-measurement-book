import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from database import get_measurement_by_id, verify_tampering
import tempfile

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
    elements.append(Paragraph("<b>Measurement Book Export</b>", title_style))
    elements.append(Spacer(1, 10))
    
    # Project Info
    info_data = [
        ["Project Name:", record['project_name']],
        ["BOQ Number:", record['boq_number']],
        ["Contractor Name:", record['contractor_name']],
        ["Sub-Contractor Name:", record['sub_contractor_name']],
        ["Date of Commencement:", record['date_commencement']],
        ["Finish Date:", record['finish_date']],
        ["Date of Measurement:", record['date_measurement']],
        ["Status:", record['status']]
    ]
    
    info_table = Table(info_data, colWidths=[150, 350])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Measurement Details
    elements.append(Paragraph("<b>Measurement Entries</b>", heading_style))
    meas_data = [
        ["Description", "No", "L (m)", "B (m)", "D/H (m)", "Qty", "Remarks"]
    ]
    meas_data.append([
        Paragraph(str(record['description'] or ""), normal_style),
        str(record['number_items']),
        str(record['length']),
        str(record['breadth']),
        str(record['depth_height']),
        str(record['quantity']),
        Paragraph(str(record['remarks'] or ""), normal_style)
    ])
    
    meas_table = Table(meas_data, colWidths=[150, 30, 45, 45, 50, 50, 100])
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
    
    # Billing Details
    elements.append(Paragraph("<b>Billing Details</b>", heading_style))
    bill_data = [
        ["Rate", "Amount", "Prev Bill Amt", "Prev Bill No", "Prev Bill Date", "Total Payable"],
        [
            str(record['rate']),
            str(record['amount']),
            str(record['prev_bill_amount']),
            str(record['prev_bill_number'] or "-"),
            str(record['prev_bill_date'] or "-"),
            str(record['total_payable'])
        ]
    ]
    bill_table = Table(bill_data, colWidths=[80, 80, 90, 80, 90, 100])
    bill_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2a5298")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
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
