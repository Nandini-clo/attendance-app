import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import os
import json
import base64

# Load .env if running locally
from dotenv import load_dotenv
load_dotenv()

# Firebase config
import firebase_admin
from firebase_admin import credentials, firestore

# Constants
BACKUP_FILE = "attendance_backup.json"

# --- Initialize Firebase ---
def init_firebase():
    firebase_key_b64 = os.getenv("FIREBASE_KEY_B64")
    if not firebase_key_b64:
        st.error("❌ Firebase key not found in environment. Please set FIREBASE_KEY_B64 on Render or in .env.")
        st.stop()

    try:
        firebase_json = base64.b64decode(firebase_key_b64).decode("utf-8")
        firebase_dict = json.loads(firebase_json)
        cred = credentials.Certificate(firebase_dict)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        return firestore.client()
    except Exception as e:
        st.error(f"❌ Firebase initialization failed: {e}")
        st.stop()

# --- Load or Initialize Backup ---
def load_backup():
    if not os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "w") as f:
            json.dump({}, f)
    with open(BACKUP_FILE, "r") as f:
        return json.load(f)

def save_backup(data_dict):
    with open(BACKUP_FILE, "w") as f:
        json.dump(data_dict, f)

# --- Main App ---
def main():
    st.set_page_config(page_title="📋 Employee Attendance Sheet Generator", layout="centered")
    st.title("📋 Employee Attendance Sheet Generator")

    db = init_firebase()

    # Load backup
    final_data_dict = load_backup()

    # Month and year selection
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    selected_month = st.selectbox("📆 Select Month", months, index=datetime.now().month - 1)
    selected_year = st.selectbox("📅 Select Year", list(range(2022, 2031)), index=datetime.now().year - 2022)
    month_year_key = f"{selected_month}-{selected_year}"

    # Entry form
    st.subheader("➕ Add Attendance Entry")
    employee_name = st.text_input("👩‍💼 Enter Employee Name")
    in_time = st.time_input("⏰ In Time", value=datetime.now().time())
    out_time = st.time_input("⏳ Out Time", value=(datetime.now() + timedelta(hours=8)).time())
    date = st.date_input("📅 Date", value=datetime.now().date())

    if st.button("✅ Save Entry"):
        entry = {
            "Employee Name": employee_name,
            "Date": str(date),
            "In Time": str(in_time),
            "Out Time": str(out_time),
            "Month": selected_month,
            "Year": selected_year
        }

        if month_year_key not in final_data_dict:
            final_data_dict[month_year_key] = []

        final_data_dict[month_year_key].append(entry)
        save_backup(final_data_dict)

        # Save to Firebase
        try:
            db.collection("attendance").add(entry)
            st.success("✅ Entry saved locally and to Firebase!")
        except Exception as e:
            st.warning(f"⚠️ Entry saved locally but not to Firebase: {e}")

    # Show Data
    if month_year_key in final_data_dict and final_data_dict[month_year_key]:
        st.subheader(f"📊 Attendance Data for {month_year_key}")
        df = pd.DataFrame(final_data_dict[month_year_key])
        st.dataframe(df)

        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)

        st.download_button(
            label="⬇️ Download Excel",
            data=buffer,
            file_name=f"attendance_{month_year_key}.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info(f"No entries found for {month_year_key}.")

if __name__ == "__main__":
    main()
