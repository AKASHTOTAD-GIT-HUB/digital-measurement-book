import streamlit as st
import pandas as pd
import datetime
from database import init_db, insert_measurement, get_all_measurements, verify_tampering, add_boq_description, get_boq_descriptions_for_project, get_boq_description, edit_boq_description, delete_boq_description, soft_delete_measurement, add_project, edit_project, soft_delete_project, get_all_projects
from boq_manager import get_or_create_boq, get_all_boqs, update_billing_and_boq, get_latest_bill_for_project_boq, create_project_bill_by_id, get_total_approved_amount_for_project, get_latest_bill_for_project, get_unbilled_quantity_for_boq, get_unbilled_measurements_for_project_id_selection
from excel_export import export_to_excel
from report_generator import generate_pdf_report
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="Blockchain Digital Measurement Book", layout="wide")

# Initialize DB on first load
if 'db_initialized' not in st.session_state:
    # --- STANDALONE IMAGE VIEWER ROUTING ---
    import os
    if "view_image_id" in st.query_params:
        meas_id = st.query_params.get("view_image_id")
        img_type = st.query_params.get("type", "site")
        st.header(f"Uploaded Image (Measurement ID: {meas_id})")
        import sqlite3
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        col = 'engineer_image' if img_type == 'engineer' else 'site_image'
        c.execute(f"SELECT {col} FROM measurements WHERE id=?", (meas_id,))
        res = c.fetchone()
        conn.close()
        if res and res[0] and os.path.exists(res[0]):
            st.image(res[0])
        else:
            st.error("Image file not found on disk.")
        if st.button("Back to Dashboard"):
            st.query_params.clear()
            st.rerun()
        st.stop()

    # --- INIT DB ---
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
st.markdown("### Project-Based Digital Measurement Book - Live Version")

st.info("🌐 **Cloud Ready:** This application is configured for global access from any device.")

# --- GLOBAL PROJECT SELECTION ---
projects = get_all_projects()
selected_project = None
project_options = {}

if st.session_state.role == "Site Engineer":
    active_projects = [p for p in projects if p.get('status', 'active') == 'active']
    if not active_projects:
        st.error("No Active Projects Available")
    else:
        project_options = {p['project_name']: p for p in active_projects}
        sel_proj_label = st.selectbox("🏗️ Select Project", list(project_options.keys()))
        selected_project = project_options[sel_proj_label]
else:
    if not projects:
        st.warning("No Projects Available.")
    else:
        for p in projects:
            lbl = f"{p['project_name']} (Inactive)" if p.get('status') == 'inactive' else p['project_name']
            project_options[lbl] = p
            
        sel_proj_label = st.selectbox("🏗️ Select Project", list(project_options.keys()))
        selected_project = project_options[sel_proj_label]

# Determine Tabs based on Role
if st.session_state.role == "Site Engineer":
    tabs = st.tabs(["📝 Site Measurement Entry", "📊 Site Engineer Dashboard"])
else:
    tabs = st.tabs(["📊 Manager Dashboard", "📝 BOQ Management", "🏢 Project Management", "💼 Manager Billing Panel", "📥 Download Report"])

# --- TAB: BOQ MANAGEMENT (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[1]:
        st.header("📝 BOQ Description Management")
        st.write("Manage BOQ numbers with permanent descriptions for the selected project.")
        
        if not selected_project:
            st.warning("⚠️ Please select a project from the top dropdown to manage its BOQs.")
        else:
            p_id = selected_project['id']
            # Load existing descriptions for the selected project
            boq_descs = get_boq_descriptions_for_project(p_id)
            if boq_descs:
                df_desc = pd.DataFrame(boq_descs)[['boq_number', 'description']]
                st.dataframe(df_desc, use_container_width=True, hide_index=True)
            else:
                st.info("No BOQ descriptions exist yet for this project.")
                
            with st.container():
                t1, t2, t3 = st.tabs(["➕ Add BOQ", "✏️ Edit BOQ", "🗑️ Delete BOQ"])
                
                with t1:
                    with st.form("add_boq_form"):
                        st.subheader("➕ Add New BOQ Description")
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            new_boq_num = st.text_input("BOQ Number", placeholder="e.g. 1")
                        with col2:
                            new_desc = st.text_input("Description of Work", placeholder="e.g. Excavation")
                            
                        submit_boq = st.form_submit_button("Save BOQ Description")
                        
                        if submit_boq:
                            if not new_boq_num.strip():
                                st.error("BOQ Number cannot be empty.")
                            elif not new_desc.strip():
                                st.error("Description of Work cannot be empty.")
                            else:
                                success, msg = add_boq_description(p_id, new_boq_num.strip(), new_desc.strip())
                                if success:
                                    st.success(f"Successfully added BOQ #{new_boq_num}: {new_desc}")
                                    st.rerun()
                                else:
                                    st.error(msg)
                
                with t2:
                    with st.form("edit_boq_form"):
                        st.subheader("✏️ Edit Existing BOQ Description")
                        if boq_descs:
                            boq_options = {str(d['boq_number']): d for d in boq_descs}
                            edit_num = st.selectbox("Select BOQ to Edit", list(boq_options.keys()))
                            edit_desc = st.text_input("New Description of Work", value=boq_options[edit_num]["description"])
                            submit_edit = st.form_submit_button("Update BOQ")
                            
                            if submit_edit:
                                if not edit_desc.strip():
                                    st.error("Description cannot be empty.")
                                else:
                                    if edit_boq_description(p_id, edit_num, edit_desc.strip()):
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
                                success, msg = delete_boq_description(p_id, del_num)
                                if success:
                                    st.success("Successfully deleted BOQ!")
                                    st.rerun()
                                else:
                                    st.error(f"Cannot delete BOQ: {msg}")
                        else:
                            st.info("No BOQ records to delete.")

# --- TAB: PROJECT MANAGEMENT (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[2]:
        st.header("🏢 Project Management")
        st.write("Manage all construction projects in the system.")
        
        if projects:
            df_proj = pd.DataFrame(projects)
            def style_proj_rows(row):
                if row['status'] == 'inactive':
                    return ['color: #6c757d; background-color: #f8f9fa'] * len(row)
                return [''] * len(row)
            st.dataframe(df_proj.style.apply(style_proj_rows, axis=1), use_container_width=True, hide_index=True)
        else:
            st.info("No projects created yet.")
            
        with st.container():
            pt1, pt2, pt3 = st.tabs(["➕ Add Project", "✏️ Edit Project", "🗑️ Soft Delete Project"])
            
            with pt1:
                with st.form("add_proj_form"):
                    new_proj_name = st.text_input("New Project Name")
                    if st.form_submit_button("Add Project"):
                        if not new_proj_name.strip():
                            st.error("Project name cannot be empty.")
                        else:
                            succ, msg = add_project(new_proj_name.strip())
                            if succ:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
            
            with pt2:
                with st.form("edit_proj_form"):
                    if projects:
                        edit_sel = st.selectbox("Select Project to Edit", list(project_options.keys()))
                        new_name = st.text_input("New Name for Project")
                        if st.form_submit_button("Update Project"):
                            if not new_name.strip():
                                st.error("Name cannot be empty.")
                            else:
                                p_id = (project_options or {}).get(edit_sel, {}).get('id')
                                succ, msg = edit_project(p_id, new_name.strip())
                                if succ:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    else:
                        st.info("No projects to edit.")
                        st.form_submit_button("Update Project", disabled=True)
                        
            with pt3:
                with st.form("del_proj_form"):
                    if projects:
                        active_only_proj = {k: v for k, v in project_options.items() if v and isinstance(v, dict) and v.get('status', 'active') == 'active'}
                        if active_only_proj:
                            del_sel = st.selectbox("Select Project to Soft Delete", list(active_only_proj.keys()))
                            if st.form_submit_button("Delete (Soft)"):
                                p_id = active_only_proj.get(del_sel, {}).get('id')
                                if soft_delete_project(p_id):
                                    st.success("Project marked as inactive.")
                                    st.rerun()
                                else:
                                    st.error("Failed to delete project.")
                        else:
                            st.info("No active projects to delete.")
                            st.form_submit_button("Delete", disabled=True)
                    else:
                        st.info("No projects available.")
                        st.form_submit_button("Delete", disabled=True)

# --- TAB: SITE MEASUREMENT ENTRY (Engineer Only) ---
if st.session_state.role == "Site Engineer":
    with tabs[0]:
        st.header("📝 Site Measurement Entry")
        
        # 1. Selection Block OUTSIDE the form to enable immediate Reactivity
        st.subheader("📁 Project & BOQ Information")
        col1, col2 = st.columns(2)
        
        with col1:
            project_name_disp = selected_project['project_name'] if selected_project else "No Project Selected"
            st.text_input("Active Project", value=project_name_disp, disabled=True)
            
            if selected_project:
                st.session_state.selected_project_id = selected_project['id']
                st.session_state.selected_project_name = selected_project['project_name']
                
                boq_descs = get_boq_descriptions_for_project(selected_project['id'])
                boq_list = [d['boq_number'] for d in boq_descs]
                
                if boq_list:
                    if "selected_boq" not in st.session_state:
                         st.session_state.selected_boq = None
                    
                    selected_boq = st.selectbox("BOQ Number", boq_list, key="selected_boq")
                    boq_number = str(selected_boq) if selected_boq is not None else None
                    work_name_input = st.text_input("Work Name", placeholder="e.g. Earthwork")
                else:
                    st.warning("No BOQs configured for this project. Manager must add BOQs first.")
                    boq_number = None
                    work_name_input = ""
            else:
                st.session_state.selected_project_id = None
                boq_list = []
                boq_number = None
                work_name_input = ""

        with col2:
            if boq_number:
                description = get_boq_description(st.session_state.selected_project_id, boq_number)
            else:
                description = ""
            
            # Debug logging requested by user
            st.write("Project ID:", st.session_state.selected_project_id)
            st.write("Selected BOQ:", boq_number)
            st.write("Fetched Description:", description)
            
            st.text_area("Selected BOQ Context", value=description, disabled=True, height=120)

        # 2. Measurement Submission block INSIDE the form
        if boq_number:
            with st.form("site_engineer_form"):
                st.header("📏 Measurement Details")
                # Auto current date logic
                current_date_str = datetime.datetime.today().strftime('%d-%m-%Y')
                st.info(f"**Date of Measurement:** {current_date_str} (Auto-generated)")
                date_measurement = datetime.date.today()
                
                fc1, fc2, fc3 = st.columns(3)
                with fc1: contractor_name = st.text_input("Contractor Name")
                with fc2: sub_contractor_name = st.text_input("Sub-Contractor Name")
                with fc3:
                    date_commencement = st.date_input("Date of Commencement")
                    finish_date = st.date_input("Finish Date")
                    
                st.markdown("---")

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
                    
                # Submit Button explicitly inside the form construct
                submit_btn = st.form_submit_button("Submit Measurement", type="primary")
                
            # Handle submit OUTSIDE the form structure
            if submit_btn:
                if not st.session_state.selected_project_id:
                    st.error("You must select an active project first.")
                elif not contractor_name or not description or not gps_coords or not selfie_photo or not site_photo:
                    st.error("Please fill all mandatory fields: Contractor Name, Description, GPS Coordinates, and Both Photos.")
                else:
                    try:
                        p_id = st.session_state.selected_project_id
                        p_name = st.session_state.selected_project_name
                        # Ensure BOQ exists in boqs table for tracking
                        get_or_create_boq(boq_number, p_name, p_id, contractor_name, sub_contractor_name, str(date_commencement), str(finish_date))
                        ts = datetime.datetime.now().isoformat()
                        selfie_bytes = selfie_photo.getvalue()
                        site_bytes = site_photo.getvalue()
                        
                        import os
                        import time
                        if not os.path.exists("uploads"):
                            os.makedirs("uploads")
                        site_image_path = f"uploads/site_photo_{p_id}_{int(time.time())}.jpg"
                        engineer_image_path = f"uploads/engineer_photo_{p_id}_{int(time.time())}.jpg"
                        with open(site_image_path, "wb") as f:
                            f.write(site_bytes)
                        with open(engineer_image_path, "wb") as f:
                            f.write(selfie_bytes)
                            
                        gps_link = f"https://www.google.com/maps?q={gps_coords}" if gps_coords else ""
                        
                        h_val = insert_measurement(
                            str(boq_number), p_name, p_id, contractor_name, sub_contractor_name, str(date_commencement), str(finish_date), str(date_measurement),
                            description, num_items, length, breadth, depth_height, calc_vol,
                            remarks, gps_coords, selfie_bytes, site_bytes, ts, gps_link, engineer_image_path, site_image_path, work_name_input
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
    if selected_project:
        records = [r for r in records if r.get('project_id') == selected_project['id']]
    else:
        records = []
        
    if records:
        df = pd.DataFrame(records)
        display_df = df[['id', 'boq_number', 'work_name', 'description', 'length', 'breadth', 'depth_height', 'quantity', 'date_measurement', 'gps_link', 'engineer_image', 'site_image', 'status', 'is_deleted']].copy()
        display_df.rename(columns={'gps_link': 'Location'}, inplace=True)
        display_df['Engineer Image'] = display_df['id'].apply(lambda x: f"/?view_image_id={x}&type=engineer")
        display_df['Site Work Image'] = display_df['id'].apply(lambda x: f"/?view_image_id={x}&type=site")
        display_df.drop(columns=['engineer_image', 'site_image'], inplace=True, errors='ignore')
        
        # Apply stylings using pandas style to handle strikethrough for UI natively
        def style_rows(row):
            status_val = str(row.get('status', '')).capitalize()
            if status_val in ['Approved', 'Billed']:
                return ['background-color: #d4edda; color: #155724; font-weight: bold'] * len(row)
            elif row['is_deleted'] == 1 or status_val == 'Deleted':
                return ['text-decoration: line-through; color: #721c24; background-color: #f8d7da'] * len(row)
            else:
                return [''] * len(row)
        
        display_df['status'] = display_df['status'].str.capitalize()

        st.dataframe(
            display_df.style.apply(style_rows, axis=1), 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Location": st.column_config.LinkColumn("Location", display_text="View Location"),
                "Engineer Image": st.column_config.LinkColumn("Engineer Image", display_text="View Image"),
                "Site Work Image": st.column_config.LinkColumn("Site Work Image", display_text="View Image")
            }
        )
        
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
        st.info("No records found for the selected project.")

# --- TAB: MANAGER BILLING PANEL (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[3]:
        st.header("💰 Manager Billing Panel")
        records = get_all_measurements()
        # Exclude softly deleted measurements from billing possibilities entirely
        if selected_project:
            records = [r for r in records if r.get('is_deleted', 0) == 0 and r.get('project_id') == selected_project['id']]
            unbilled_meas = get_unbilled_measurements_for_project_id_selection(selected_project['id'])
            
            if unbilled_meas:
                meas_options = {f"{m['id']} - BOQ {m['boq_number']}": m for m in unbilled_meas}
                selected_option = st.selectbox("Select Measurement ID to Bill", list(meas_options.keys()), index=None, placeholder="Select Measurement ID")
                
                if not selected_option:
                    st.warning("⚠️ Please select Measurement ID")
                else:
                    selected_m = meas_options[selected_option]
                    selected_id = selected_m['id']
                    selected_boq = selected_m['boq_number']
                    unbilled_qty = selected_m['quantity']
                    
                    st.markdown("---")
                    
                    # Removing st.form to allow instant reactivity of Rate calculation
                    with st.container():
                        st.subheader("📋 Previous Bill Details")
                        last_bill = get_latest_bill_for_project(selected_project['id'])
                        
                        if last_bill and isinstance(last_bill, dict):
                            prev_bill_no = last_bill.get('bill_no', 'N/A')
                            prev_bill_date = last_bill.get('bill_date', 'N/A')
                            prev_bill_amt = last_bill.get('amount', 0.0)
                        else:
                            prev_bill_no = "N/A"
                            prev_bill_date = "N/A"
                            prev_bill_amt = "NA"
                            
                        col_p1, col_p2, col_p3 = st.columns(3)
                        col_p1.text_input("Previous Bill Number", value=prev_bill_no, disabled=True)
                        col_p2.text_input("Previous Bill Date", value=prev_bill_date, disabled=True)
                        col_p3.text_input("Previous Bill Amount", value=str(prev_bill_amt), disabled=True)
    
                        st.markdown("---")
                        st.subheader("📜 Current Bill Calculation")
                        
                        st.info(f"**Selected ID:** {selected_id}\n\n**Corresponding BOQ Number:** {selected_boq}")
                        st.write(f"**Quantity from that ID:** {unbilled_qty:.3f}")
                        
                        rate = st.number_input("Rate (₹ per unit)", min_value=0.0, format="%.2f", step=1.0)
                        current_bill_amount = unbilled_qty * rate
                        
                        st.success(f"**Calculated Current Bill = ₹ {current_bill_amount:.2f}**")
                        
                        tot_approved = get_total_approved_amount_for_project(selected_project['id'])
                        st.info(f"**Total Approved Amount (Till Now) = ₹ {tot_approved:.2f}**")
                        
                        safe_prev_amt = 0.0 if prev_bill_amt == "NA" else float(prev_bill_amt)
                        total_payable = safe_prev_amt + current_bill_amount
                        
                        disable_approve = unbilled_qty <= 0
                        if disable_approve:
                            st.warning("⚠️ No measurements found for this BOQ")
                            
                        update_btn = st.button("Approve Bill", disabled=disable_approve, type="primary")
                        
                        if update_btn and not disable_approve:
                            try:
                                create_project_bill_by_id(selected_project['id'], selected_boq, rate, unbilled_qty, current_bill_amount, total_payable, selected_id)
                                st.success("✅ Bill successfully generated, locked, and appended to the Project Billing ledger!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Failed to approve bill: {e}")
            else:
                st.info("No unbilled measurements found for the selected project.")
        else:
            st.info("Please select an active project to calculate billing.")

# --- TAB: DOWNLOAD REPORT (Manager Only) ---
if st.session_state.role == "Manager":
    with tabs[4]:
        st.header("📄 Export Official Reports")
        records = get_all_measurements()
        if selected_project:
            records = [r for r in records if r.get('project_id') == selected_project['id']]
        else:
            records = []
            
        if records:
            st.subheader("Excel Export")
            st.write("Contains all measurements and billing sheets for the selected project.")
            excel_data = export_to_excel(project_id=(selected_project or {}).get('id'))
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
            st.info("No records available for the selected project.")

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
