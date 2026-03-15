import streamlit as st
import pandas as pd
import datetime
from database import init_db, insert_measurement, get_all_measurements, verify_tampering, add_boq_description, get_all_boq_descriptions, edit_boq_description, delete_boq_description, soft_delete_measurement
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
    if not st.session_state.get('manager_auth', False):
        with st.sidebar.form("login_form"):
            password = st.text_input("Manager Password", type="password")
            submit_login = st.form_submit_button("Login")
            
        if submit_login:
            if password == "Klecivil@123":
                st.session_state.manager_auth = True
                st.session_state.role = "Manager"
                st.rerun()
            else:
                st.sidebar.error("Incorrect Password!")
                st.stop()
        else:
            st.stop()
    else:
        st.session_state.role = "Manager"
        if st.sidebar.button("Logout"):
            st.session_state.manager_auth = False
            st.rerun()
else:
    st.session_state.role = "Site Engineer"
    st.session_state.manager_auth = False


st.title("🏗️ Professional Blockchain-Enabled Digital Measurement Book")

st.info("🌐 **Cloud Ready:** This application is configured for global access from any device.")

# Determine Tabs based on Role
if st.session_state.role == "Site Engineer":
    tabs = st.tabs(["📝 Site Measurement Entry", "📊 Site Engineer Dashboard"])
else:
    tabs = st.tabs(["📊 Manager Dashboard", "📝 BOQ Management", "💼 Manager Billing Panel", "📥 Download Report"])

# --- TAB: BOQ MANAGEMENT (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[1]:
        st.header("📝 BOQ Description Management")
        st.write("Create sequential numeric BOQ numbers with permanent descriptions.")
        
        # Load existing descriptions
        boq_descs = get_all_boq_descriptions()
        if boq_descs:
            df_desc = pd.DataFrame(boq_descs)
            st.dataframe(df_desc, use_container_width=True, hide_index=True)
            next_boq = max([d['boq_number'] for d in boq_descs]) + 1
        else:
            st.info("No BOQ descriptions exist yet.")
            next_boq = 1
            
        with st.container():
            t1, t2, t3 = st.tabs(["➕ Add BOQ", "✏️ Edit BOQ", "🗑️ Delete BOQ"])
            
            with t1:
                with st.form("add_boq_form"):
                    st.subheader("➕ Add New BOQ Description")
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        new_boq_num = st.number_input("BOQ Number", min_value=next_boq, max_value=next_boq, value=next_boq, disabled=True)
                    with col2:
                        new_desc = st.text_input("Description of Work", placeholder="e.g. Excavation for foundation")
                        
                    submit_boq = st.form_submit_button("Save BOQ Description")
                    
                    if submit_boq:
                        if not new_desc.strip():
                            st.error("Description of Work cannot be empty.")
                        else:
                            success = add_boq_description(new_boq_num, new_desc.strip())
                            if success:
                                st.success(f"Successfully added BOQ #{new_boq_num}: {new_desc}")
                                st.rerun()
                            else:
                                st.error(f"BOQ Number {new_boq_num} already exists.")
            
            with t2:
                with st.form("edit_boq_form"):
                    st.subheader("✏️ Edit Existing BOQ Description")
                    if boq_descs:
                        boq_options = {d['boq_number']: d['description_of_work'] for d in boq_descs}
                        edit_num = st.selectbox("Select BOQ to Edit", list(boq_options.keys()))
                        edit_desc = st.text_input("New Description of Work", value=boq_options.get(edit_num, ""))
                        submit_edit = st.form_submit_button("Update BOQ")
                        
                        if submit_edit:
                            if not edit_desc.strip():
                                st.error("Description cannot be empty.")
                            else:
                                if edit_boq_description(edit_num, edit_desc.strip()):
                                    st.success("Successfully updated BOQ Description!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update BOQ.")
                    else:
                        st.info("No BOQ records to edit.")
            
            with t3:
                with st.form("delete_boq_form"):
                    st.subheader("🗑️ Delete Unused BOQ")
                    if boq_descs:
                        del_num = st.selectbox("Select BOQ to Delete", list(boq_options.keys()))
                        submit_del = st.form_submit_button("Delete BOQ")
                        if submit_del:
                            success, msg = delete_boq_description(del_num)
                            if success:
                                st.success("Successfully deleted BOQ!")
                                st.rerun()
                            else:
                                st.error(f"Cannot delete BOQ: {msg}")
                    else:
                        st.info("No BOQ records to delete.")

# --- TAB: SITE MEASUREMENT ENTRY (Engineer Only) ---
if st.session_state.role == "Site Engineer":
    with tabs[0]:
        with st.form("measurement_form"):
            st.header("📁 Project Information")
            col1, col2 = st.columns(2)
            with col1: 
                project_name = st.text_input("Project Name")
                
                # Fetch available BOQs for dropdown
                boq_descs = get_all_boq_descriptions()
                boq_options = {d['boq_number']: d['description_of_work'] for d in boq_descs}
                
                if boq_options:
                    boq_number = st.selectbox("BOQ Number", list(boq_options.keys()))
                else:
                    st.warning("No BOQs configured. Manager must add BOQs first.")
                    boq_number = None
                    
            with col2:
                contractor_name = st.text_input("Contractor Name")
                sub_contractor_name = st.text_input("Sub-Contractor Name")
                col2a, col2b = st.columns(2)
                with col2a: date_commencement = st.date_input("Date of Commencement")
                with col2b: finish_date = st.date_input("Finish Date")

            st.markdown("---")
            st.header("📏 Measurement Details")
            
            # Auto current date logic
            current_date_str = datetime.datetime.today().strftime('%d-%m-%Y')
            st.info(f"**Date of Measurement:** {current_date_str} (Auto-generated)")
            date_measurement = datetime.date.today()
            
            # Auto-fill description based on selected BOQ
            if boq_number and boq_number in boq_options:
                description = boq_options[boq_number]
                st.text_area("Description of Work (Auto-filled by BOQ)", value=description, disabled=True, height=100)
            else:
                description = ""
                st.text_area("Description of Work", value="Select a valid BOQ Number above", disabled=True, height=100)

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: num_items = st.number_input("Number (No. of items)", min_value=1.0, value=1.0, step=1.0)
            with c2: length = st.number_input("Length (m)", min_value=0.0, format="%.2f")
            with c3: breadth = st.number_input("Breadth (m)", min_value=0.0, format="%.2f")
            with c4: depth_height = st.number_input("Depth / Height (m)", min_value=0.0, format="%.2f")
            with c5: remarks = st.text_input("Remarks")
            
            calc_vol = num_items * (length if length else 1.0) * (breadth if breadth else 1.0) * (depth_height if depth_height else 1.0)
            if length == 0.0 and breadth == 0.0 and depth_height == 0.0:
                calc_vol = 0.0
            
            st.info(f"**Calculated Quantity:** {calc_vol:.3f}")
            
            st.markdown("---")
            st.header("📷 Photo Evidence & Verification")
            
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                st.subheader("📍 Live GPS")
                try:
                    location = streamlit_geolocation()
                except Exception:
                    location = None
                    
                if location and location.get('latitude') and location.get('longitude'):
                    auto_gps = f"{location['latitude']},{location['longitude']}"
                    st.success(f"Captured: {auto_gps}")
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
                
            submit_btn = st.form_submit_button("Submit Measurement", type="primary")
            
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
                            str(boq_number), project_name, contractor_name, sub_contractor_name, str(date_commencement), str(finish_date), str(date_measurement),
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
    st.header(f"📊 {'Site Engineer ' if st.session_state.role == 'Site Engineer' else ''}Dashboard - Measurement Records")
    records = get_all_measurements()
    if records:
        df = pd.DataFrame(records)
        display_df = df[['id', 'boq_number', 'description', 'length', 'breadth', 'depth_height', 'quantity', 'date_measurement', 'status', 'is_deleted']].copy()
        
        # Apply stylings using pandas style to handle strikethrough for UI natively
        def style_rows(row):
            if row['status'] == 'Approved':
                return ['background-color: #d4edda; color: #155724; font-weight: bold'] * len(row)
            elif row['is_deleted'] == 1 or row['status'] == 'Deleted':
                return ['text-decoration: line-through; color: #721c24; background-color: #f8d7da'] * len(row)
            else:
                return [''] * len(row)

        st.dataframe(display_df.style.apply(style_rows, axis=1), use_container_width=True, hide_index=True)
        
        # Add Soft Delete UI for Site Engineers
        if st.session_state.role == "Site Engineer":
            st.markdown("---")
            st.subheader("🗑️ Delete Pending Measurement")
            
            # Filter solely pending items physically available
            pending_records = [r for r in records if r['status'] == 'Pending' and r['is_deleted'] == 0]
            if pending_records:
                del_opts = {f"ID {r['id']} | BOQ {r['boq_number']} | Date: {r['date_measurement']}": r['id'] for r in pending_records}
                selected_del = st.selectbox("Select Measurement to Delete", list(del_opts.keys()))
                if st.button("Delete Measurement", type="secondary"):
                    succ, msg = soft_delete_measurement(del_opts[selected_del])
                    if succ:
                        st.error("Measurement logically marked as deleted!")
                        st.rerun()
                    else:
                        st.warning(msg)
            else:
                st.info("No pending measurements eligible for deletion.")
            
    else:
        st.info("No records found.")

# --- TAB: MANAGER BILLING PANEL (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[2]:
        st.header("💰 Manager Billing Panel")
        records = get_all_measurements()
        # Exclude softly deleted measurements from billing possibilities entirely
        records = [r for r in records if r.get('is_deleted', 0) == 0]
        if records:
            record_options = {f"ID: {r['id']} - BOQ: {r['boq_number']} - {r['project_name']}": r for r in records}
            selected_label = st.selectbox("Select Measurement Record to Review & Bill", list(record_options.keys()))
            sel_rec = record_options[selected_label]
            
            # Fetch latest BOQ details to pre-populate Previous Bill info
            boqs = get_all_boqs()
            boq_dict = {b['boq_number']: b for b in boqs}
            current_boq = boq_dict.get(sel_rec['boq_number'], {})
            
            st.markdown("---")
            with st.container():
                st.subheader("📋 Measurement Summary")
                m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
                m_c1.write(f"**BOQ No:** {sel_rec['boq_number']}")
                m_c2.write(f"**Description:** {sel_rec['description']}")
                m_c3.write(f"**Status:** {sel_rec['status']}")
                m_c4.write(f"**Measurement Date:** {sel_rec['date_measurement']}")
                m_c5.info(f"**Quantity:** {sel_rec['quantity']}")
                
            st.markdown("---")
            
            with st.form("billing_form"):
                st.subheader("📜 Bill Calculation")
                # Auto load from boq record
                def_prev_amt = sel_rec['prev_bill_amount'] if sel_rec['prev_bill_amount'] > 0 else current_boq.get('prev_bill_amount', 0.0)
                def_prev_no = sel_rec['prev_bill_number'] if sel_rec['prev_bill_number'] else current_boq.get('prev_bill_number', "N/A")
                
                # Auto populated read-only fields for current bill
                current_bill_date = datetime.datetime.today().strftime("%d-%m-%Y")
                col_c1, col_c2 = st.columns(2)
                col_c1.text_input("BOQ Number Selected", sel_rec['boq_number'], disabled=True)
                col_c2.text_input("Current Bill Date", current_bill_date, disabled=True)
                
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    rate = st.number_input("Rate (₹)", min_value=0.0, format="%.2f", value=sel_rec['rate'] or 0.0)
                with col_b2:
                    amt = sel_rec['quantity'] * rate
                    st.success(f"**Current Bill Amount = ₹ {amt:.2f}**")
                with col_b3:
                    st.info(f"**Previous Bill Amount = ₹ {float(def_prev_amt):.2f}**")
                    
                tot = float(def_prev_amt) + amt
                st.warning(f"**Total Payable Amount: ₹ {tot:.2f}**")
                
                is_approved = (sel_rec['status'] == "Approved")
                if is_approved:
                    st.success("✅ This measurement has already been Approved and is Locked.")
                    
                # The submit button MUST be unconditionally rendered inside an st.form!
                update_btn = st.form_submit_button("Approve Bill", disabled=is_approved)
                
                if update_btn and not is_approved:
                    try:
                        update_billing_and_boq(sel_rec['id'], rate, amt, float(def_prev_amt), current_bill_date, def_prev_no, tot)
                        st.success("Billing details updated, Bill Approved, and Measurement successfully Locked!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to approve bill: {e}")
        else:
            st.info("No records available to bill.")

# --- TAB: DOWNLOAD REPORT (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[3]:
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
