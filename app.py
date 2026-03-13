import streamlit as st
import pandas as pd
import datetime
from database import init_db, insert_measurement, get_all_measurements, verify_tampering
from boq_manager import get_or_create_boq, get_all_boqs, update_billing_and_boq
from excel_export import export_to_excel
from report_generator import generate_pdf_report
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="Blockchain Digital Measurement Book", layout="wide")

# Initialize DB on first load
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

if 'role' not in st.session_state:
    st.session_state.role = "Site Engineer"

st.sidebar.title("🔐 Role Selection")
role = st.sidebar.radio("Login As:", ["Site Engineer", "Manager"])

# Authenticate Manager
if role == "Manager":
    password = st.sidebar.text_input("Manager Password", type="password")
    if password == "Klecivil@123":
        st.session_state.role = "Manager"
        st.sidebar.success("Logged in as Manager")
    elif password:
        st.sidebar.error("Incorrect Password!")
        st.session_state.role = "Site Engineer"
        st.stop()
    else:
        st.session_state.role = "Site Engineer"
        st.stop()
else:
    st.session_state.role = "Site Engineer"


st.title("🏗️ Professional Blockchain-Enabled Digital Measurement Book")

st.info("🌐 **Cloud Ready:** This application is configured for global access from any device.")

# Determine Tabs based on Role
if st.session_state.role == "Site Engineer":
    tabs = st.tabs(["📝 Site Measurement Entry", "📊 Dashboard"])
else:
    tabs = st.tabs(["📊 Dashboard", "💼 Manager Billing Panel", "📥 Download Reports"])

# --- TAB: SITE MEASUREMENT ENTRY (Engineer Only) ---
if st.session_state.role == "Site Engineer":
    with tabs[0]:
        with st.container():
            st.header("📁 Project Information")
            col1, col2 = st.columns(2)
            with col1: 
                project_name = st.text_input("Project Name")
                boq_number = st.text_input("BOQ Number")
            with col2:
                contractor_name = st.text_input("Contractor Name")
                sub_contractor_name = st.text_input("Sub-Contractor Name")
                col2a, col2b = st.columns(2)
                with col2a: date_commencement = st.date_input("Date of Commencement")
                with col2b: finish_date = st.date_input("Finish Date")

        st.markdown("---")
        with st.container():
            st.header("📏 Measurement Details")
            
            # Auto current date logic
            current_date_str = datetime.datetime.today().strftime('%d-%m-%Y')
            st.info(f"**Date of Measurement:** {current_date_str} (Auto-generated)")
            date_measurement = datetime.date.today()
            
            description = st.text_area("Description of Work (Example: RCC Column Concrete for Ground Floor)", height=100)

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: num_items = st.number_input("Number (No. of items)", min_value=1.0, value=1.0, step=1.0)
            with c2: length = st.number_input("Length (m)", min_value=0.0, format="%.2f")
            with c3: breadth = st.number_input("Breadth (m)", min_value=0.0, format="%.2f")
            with c4: depth_height = st.number_input("Depth / Height (m)", min_value=0.0, format="%.2f")
            with c5: remarks = st.text_input("Remarks")
            
            calc_vol = num_items * (length if length else 1.0) * (breadth if breadth else 1.0) * (depth_height if depth_height else 1.0)
            if length == 0.0 and breadth == 0.0 and depth_height == 0.0:
                calc_vol = 0.0
            
            st.info(f"**Calculated Quantity (Contents):** {calc_vol:.3f}")
        
        st.markdown("---")
        with st.container():
            st.header("📷 Photo Evidence & Verification")
            
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                st.subheader("📍 Live GPS")
                try:
                    location = streamlit_geolocation()
                except Exception:
                    location = None
                    
                if location and location.get('latitude') and location.get('longitude'):
                    lat = location['latitude']
                    lon = location['longitude']
                    auto_gps = f"{lat},{lon}"
                    st.success(f"Captured: {auto_gps}")
                    st.markdown(f"[📍 View Maps](https://www.google.com/maps?q={lat},{lon})")
                else:
                    auto_gps = ""
                    st.info("Click the location button above to get automatic GPS.")
                    
                gps_coords = st.text_input("GPS Coordinates", value=auto_gps)
                
            with col_v2:
                st.subheader("📸 Engineer Verification")
                selfie_photo = st.camera_input("Engineer Verification Photo (Selfie)", key="selfie")
                
            with col_v3:
                st.subheader("📸 Site Work Photo")
                site_photo = st.camera_input("Site Work Photo", key="site")
                
        submit_btn = st.button("Submit Measurement", type="primary")
        
        if submit_btn:
            if not boq_number or not project_name or not contractor_name or not description or not gps_coords or not selfie_photo or not site_photo:
                st.error("Please fill all mandatory fields: BOQ Number, Project Name, Contractor Name, Description, GPS Coordinates, and Both Photos.")
            else:
                try:
                    get_or_create_boq(boq_number, project_name, contractor_name, sub_contractor_name, str(date_commencement), str(finish_date))
                    ts = datetime.datetime.now().isoformat()
                    selfie_bytes = selfie_photo.getvalue()
                    site_bytes = site_photo.getvalue()
                    
                    h_val = insert_measurement(
                        boq_number, project_name, contractor_name, sub_contractor_name, str(date_commencement), str(finish_date), str(date_measurement),
                        description, num_items, length, breadth, depth_height, calc_vol,
                        remarks, gps_coords, selfie_bytes, site_bytes, ts
                    )
                    st.success("✅ Measurement recorded securely with blockchain-style hash!")
                    st.info(f"**Generated Tamper-Proof Hash:** {h_val}")
                except Exception as e:
                    st.error(f"❌ Failed to submit measurement: {e}")

# --- TAB: DASHBOARD (Shared, but index varies) ---
dash_tab = tabs[1] if st.session_state.role == "Site Engineer" else tabs[0]
with dash_tab:
    st.header("Dashboard - Measurement Records")
    records = get_all_measurements()
    if records:
        df = pd.DataFrame(records)
        display_df = df[['id', 'boq_number', 'project_name', 'description', 'quantity', 'gps_coordinates', 'hash_value', 'status']].copy()
        display_df['Dimensions (L x B x D/H)'] = df.apply(lambda r: f"{r['length']}x{r['breadth']}x{r['depth_height']}", axis=1)
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No records found.")

# --- TAB: MANAGER BILLING PANEL (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[1]:
        st.header("💰 Manager Billing Panel")
        records = get_all_measurements()
        if records:
            record_options = {f"ID: {r['id']} - BOQ: {r['boq_number']} - {r['project_name']}": r for r in records}
            selected_label = st.selectbox("Select Measurement Record to Bill / Approve", list(record_options.keys()))
            sel_rec = record_options[selected_label]
            
            # Fetch latest BOQ details to pre-populate Previous Bill info
            boqs = get_all_boqs()
            boq_dict = {b['boq_number']: b for b in boqs}
            current_boq = boq_dict.get(sel_rec['boq_number'], {})
            
            with st.container():
                st.subheader("📁 Project & BOQ Information")
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Project Name:** {sel_rec['project_name']}")
                c1.write(f"**BOQ Number:** {sel_rec['boq_number']}")
                c2.write(f"**Contractor:** {sel_rec['contractor_name']}")
                c2.write(f"**Sub-Contractor:** {sel_rec['sub_contractor_name']}")
                c3.write(f"**Commencement:** {sel_rec['date_commencement']}")
                c3.write(f"**Finish Date:** {sel_rec['finish_date']}")
            
            st.markdown("---")
            with st.container():
                st.subheader("📏 Measurement Summary")
                m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
                m_c1.write(f"**Desc:** {sel_rec['description']}")
                m_c2.write(f"**Length:** {sel_rec['length']} m")
                m_c3.write(f"**Breadth:** {sel_rec['breadth']} m")
                m_c4.write(f"**Height:** {sel_rec['depth_height']} m")
                m_c5.info(f"**Quantity:** {sel_rec['quantity']}")
                
            st.markdown("---")
            
            with st.form("billing_form"):
                st.subheader("📜 Previous Bill Information (Read Only)")
                # Auto load from boq record
                def_prev_amt = sel_rec['prev_bill_amount'] if sel_rec['prev_bill_amount'] > 0 else current_boq.get('prev_bill_amount', 0.0)
                def_prev_no = sel_rec['prev_bill_number'] if sel_rec['prev_bill_number'] else current_boq.get('prev_bill_number', "N/A")
                def_prev_date_str = sel_rec['prev_bill_date'] if sel_rec['prev_bill_date'] else current_boq.get('prev_bill_date', "N/A")
                
                col_p1, col_p2, col_p3 = st.columns(3)
                col_p1.info(f"**Previous Bill Number:** {def_prev_no}")
                col_p2.info(f"**Previous Bill Date:** {def_prev_date_str}")
                col_p3.info(f"**Previous Bill Amount:** ₹ {float(def_prev_amt):.2f}")
                
                st.markdown("---")
                st.subheader("💰 Current Bill Details")
                
                # Auto populated read-only fields for current bill
                current_bill_date = datetime.datetime.today().strftime("%d-%m-%Y")
                col_c1, col_c2 = st.columns(2)
                col_c1.text_input("BOQ Number", sel_rec['boq_number'], disabled=True)
                col_c2.text_input("Current Bill Date", current_bill_date, disabled=True)
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    rate = st.number_input("Rate (₹)", min_value=0.0, format="%.2f", value=sel_rec['rate'] or 0.0)
                with col_b2:
                    amt = sel_rec['quantity'] * rate
                    st.success(f"**Current Bill Amount = ₹ {amt:.2f}**")
                    
                tot = float(def_prev_amt) + amt
                st.warning(f"**Total Payable Amount: ₹ {tot:.2f}**")
                
                update_btn = st.form_submit_button("Approve & Sync Bill to BOQ Master")
                if update_btn:
                    try:
                        update_billing_and_boq(sel_rec['id'], rate, amt, float(def_prev_amt), str(def_prev_date_str), str(def_prev_no), tot)
                        st.success("Billing details updated and BOQ Previous Bill values synchronized!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to update billing: {e}")
        else:
            st.info("No records available to bill.")

# --- TAB: DOWNLOAD REPORTS (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[2]:
        st.header("📄 Export Official Reports")
        records = get_all_measurements()
        if records:
            st.subheader("Excel Export")
            st.write("Contains all measurements and billing sheets.")
            excel_data = export_to_excel()
            if excel_data:
                st.download_button("📥 Download Master Excel Report", data=excel_data, file_name="measurement_master.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            st.markdown("---")
            st.subheader("PDF Export (KPWD format)")
            record_options = {f"ID: {r['id']} - BOQ: {r['boq_number']}": r for r in records}
            selected_pdf = st.selectbox("Select Measurement for PDF Report", list(record_options.keys()))
            sel_id = record_options[selected_pdf]['id']
            
            # Tamper Verification
            try:
                is_valid, exp_h, act_h = verify_tampering(sel_id)
                if not is_valid:
                    st.error("⚠ Data Tampering Detected in this Record! The PDF will show tampered status.")
                else:
                    st.success("✅ Blockchain Verification Passed. Record is intact.")
            except Exception as e:
                st.warning(f"Could not verify tamper status: {e}")
            
            try:
                pdf_data = generate_pdf_report(sel_id)
                if pdf_data:
                    st.download_button(f"📥 Download PDF Report for ID {sel_id}", data=pdf_data, file_name=f"measurement_{sel_id}.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"❌ PDF generation failed: {e}")
        else:
            st.info("No records available.")

# --- MOBILE APP DOWNLOAD SECTION ---
st.markdown("---")
st.header("📱 Download Android App")
import os
apk_path = "DigitalMeasurementBook.apk"
if os.path.exists(apk_path):
    with open(apk_path, "rb") as file:
        st.download_button(
            label="📥 Download APK",
            data=file,
            file_name="DigitalMeasurementBook.apk",
            mime="application/vnd.android.package-archive",
            type="primary"
        )
else:
    st.warning("APK file not found. Please compile the Android project first.")
