import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import io
import os
import json
from dotenv import load_dotenv

# 🌐 Load environment variables
load_dotenv()

# 🔐 Initialize Firebase safely
try:
    firebase_key_raw = os.getenv("FIREBASE_KEY")
    if not firebase_key_raw:
        st.error("❌ FIREBASE_KEY not found in environment. Please check your .env or Render secret.")
        st.stop()

    firebase_creds = json.loads(firebase_key_raw)
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_creds)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    st.error(f"🔥 Firebase initialization failed: {e}")
    st.stop()

COLLECTION = "attendance_records"

st.set_page_config(page_title="Attendance App", layout="wide")
st.title("📋 Employee Attendance Sheet Generator")

# 🔁 Firestore Helpers
def reset_firestore():
    try:
        docs = db.collection(COLLECTION).stream()
        for doc in docs:
            db.collection(COLLECTION).document(doc.id).delete()
        st.session_state.clear()
        st.success("✅ Firestore data reset successfully.")
    except Exception as e:
        st.error(f"❌ Firestore reset error: {e}")

def fetch_firestore_records():
    try:
        docs = db.collection(COLLECTION).stream()
        return {doc.id: doc.to_dict() for doc in docs}
    except:
        return {}

def convert_to_python_types(data):
    return {
        k: (int(v) if isinstance(v, (np.integer, np.int64)) else float(v) if isinstance(v, np.floating) else v)
        for k, v in data.items()
    }

def save_record(index, data):
    clean_data = convert_to_python_types(data)
    db.collection(COLLECTION).document(str(index)).set(clean_data)

# 📁 Upload
uploaded_file = st.file_uploader("📄 Upload Excel with 'Employee Code' & 'Employee Name'", type=["xlsx"])
if st.button("🔄 Reset All Data"):
    reset_firestore()

# Auto-reset session on new file
if uploaded_file and "uploaded_filename" not in st.session_state:
    reset_firestore()
    st.session_state["current_index"] = 0
    st.session_state["uploaded_filename"] = uploaded_file.name

stored_data = fetch_firestore_records()
current_index = int(st.session_state.get("current_index", 0))

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = [col.strip() for col in df.columns]

        if 'Employee Code' not in df.columns or 'Employee Name' not in df.columns:
            st.error("❌ File must include 'Employee Code' and 'Employee Name'")
            st.stop()

        employee_list = df[['Employee Code', 'Employee Name']].drop_duplicates().reset_index(drop=True)
        st.session_state["employee_list"] = employee_list.to_dict("records")
        st.session_state["total_employees"] = len(employee_list)

        st.session_state["month"] = st.selectbox("🗓️ Month", list(range(1, 13)), index=datetime.now().month - 1)
        st.session_state["year"] = st.selectbox("📆 Year", list(range(2023, 2031)), index=1)

    except Exception as e:
        st.error(f"❌ Failed to read Excel: {e}")
        st.stop()
else:
    employee_list = pd.DataFrame(st.session_state.get("employee_list", []))

# ✍️ Entry Form
if not employee_list.empty and current_index < len(employee_list):
    emp = employee_list.iloc[current_index]
    st.subheader(f"🧑 {emp['Employee Name']} (Code: {emp['Employee Code']})")

    days_in_month = (datetime(st.session_state["year"], st.session_state["month"] % 12 + 1, 1) - timedelta(days=1)).day
    row_data = stored_data.get(str(current_index), {
        "Employee Code": emp["Employee Code"],
        "Employee Name": emp["Employee Name"]
    })

    total_ot = 0
    c_P = c_A = c_L = c_WO = c_HL = c_PH = 0

    for day in range(1, days_in_month + 1):
        date_str = f"{day:02d}-{st.session_state['month']:02d}"
        st.markdown(f"#### 📅 {date_str}")
        status = st.selectbox(f"Status for {date_str}", ["P", "A", "L", "WO", "HL", "PH"],
                              key=f"status_{day}",
                              index=["P", "A", "L", "WO", "HL", "PH"].index(row_data.get(f"{day:02d}_Status", "P")))

        if status == "P":
            c_P += 1
            default_ci = row_data.get(f"{day:02d}_Check-in", "09:00")
            default_co = row_data.get(f"{day:02d}_Check-out", "18:00")

            ci_str = st.text_input(f"⏰ Check-in ({date_str}) [HH:MM]", value=default_ci, key=f"ci_{day}")
            co_str = st.text_input(f"⏰ Check-out ({date_str}) [HH:MM]", value=default_co, key=f"co_{day}")

            try:
                dt_ci = datetime.strptime(ci_str, "%H:%M")
                dt_co = datetime.strptime(co_str, "%H:%M")
                if dt_co <= dt_ci:
                    dt_co += timedelta(days=1)
                hours = round((dt_co - dt_ci).total_seconds() / 3600, 2)
                ot = round(max(0, hours - 8), 2)
            except:
                st.warning("⚠️ Please enter valid time in HH:MM format.")
                ci_str, co_str, ot = "09:00", "18:00", 0

            ci, co = ci_str, co_str

        elif status == "A":
            c_A += 1
            ci = co = "00:00"
            ot = 0
        elif status == "L":
            c_L += 1
            ci = co = "00:00"
            ot = 0
        elif status == "WO":
            c_WO += 1
            ci, co, ot = "09:00", "17:00", 0
        elif status == "HL":
            c_HL += 1
            ci, co, ot = "09:00", "13:00", 0
        elif status == "PH":
            c_PH += 1
            ci = co = "00:00"
            ot = 0

        row_data[f"{day:02d}_Status"] = status
        row_data[f"{day:02d}_Check-in"] = ci
        row_data[f"{day:02d}_Check-out"] = co
        row_data[f"{day:02d}_OT"] = ot
        total_ot += ot

    row_data.update({
        "Total P": c_P, "Total A": c_A, "Total L": c_L,
        "Total WO": c_WO, "Total HL": c_HL, "Total PH": c_PH,
        "OT Hours": round(total_ot, 2)
    })

    save_record(current_index, row_data)

    sorted_row = dict(sorted(row_data.items(), key=lambda x: (not x[0].startswith(('Employee', 'Total', 'OT')), x[0])))
    st.markdown("### Preview Entry")
    st.dataframe(pd.DataFrame([sorted_row]), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏮️ Previous"):
            if current_index > 0:
                st.session_state["current_index"] = current_index - 1
                st.rerun()
    with col2:
        if st.button("✅ Save & Next"):
            st.session_state["current_index"] = current_index + 1
            st.rerun()

# ✅ Final Summary
stored_data = fetch_firestore_records()
if len(stored_data) > 0 and current_index >= len(stored_data):
    st.success("✅ All employees completed!")

    sorted_records = []
    for _, v in sorted(stored_data.items(), key=lambda x: int(x[0])):
        sorted_v = dict(sorted(v.items(), key=lambda x: (not x[0].startswith(('Employee', 'Total', 'OT')), x[0])))
        sorted_records.append(sorted_v)

    final_df = pd.DataFrame(sorted_records)
    st.dataframe(final_df, use_container_width=True)

    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
        final_df.to_excel(writer, index=False, sheet_name="Attendance")

    st.download_button("📥 Download Excel", data=towrite.getvalue(), file_name="final_attendance.xlsx")
