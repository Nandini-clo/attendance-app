# ✅ Final Revised Code with OT Logic + Google Sheets + Safe Save Backup (Optimized)
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore,initialize_app
import io
import json
import os
import calendar
from dotenv import load_dotenv
from sheets_backup import append_to_sheet
load_dotenv()  # Loads .env in local dev

import ast
# other imports remain the same...
def _extract_json_like(s: str) -> str | None:
    if not isinstance(s, str):
        return None
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start:end+1]
    return None

def _normalize_private_key(key_dict):
    """Fix newline issues in private_key for Google service accounts."""
    if isinstance(key_dict, dict) and "private_key" in key_dict and isinstance(key_dict["private_key"], str):
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    return key_dict

def load_json_key(key_name):
    """
    Robust loader for JSON-like secrets from st.secrets or env vars.
    Returns a dict or raises a RuntimeError with helpful preview.
    """
    # 1) Try Streamlit secrets
    if key_name in st.secrets:
        val = st.secrets[key_name]
        if isinstance(val, dict):
            return _normalize_private_key(val)
        if isinstance(val, str):
            # Try direct JSON
            try:
                parsed = json.loads(val)
                return _normalize_private_key(parsed)
            except Exception:
                pass
            # Try extracting {...} and parsing
            extracted = _extract_json_like(val)
            if extracted:
                try:
                    parsed = json.loads(extracted)
                    return _normalize_private_key(parsed)
                except Exception:
                    pass
            # Try Python literal eval
            try:
                parsed = ast.literal_eval(val)
                return _normalize_private_key(parsed)
            except Exception:
                if extracted:
                    try:
                        parsed = ast.literal_eval(extracted)
                        return _normalize_private_key(parsed)
                    except Exception:
                        pass
            preview = repr(val)[:1000]
            raise RuntimeError(
                f"{key_name} in st.secrets could not be parsed as JSON or Python literal.\n"
                f"Preview (first 1000 chars):\n{preview}\n\n"
                "Hint: place valid JSON in secrets.toml (wrap with triple quotes) or provide the env var."
            )
        # unexpected type
        raise RuntimeError(f"{key_name} found in st.secrets but is not dict/string (type={type(val)}).")

    # 2) Fallback: environment variable
    env_val = os.getenv(key_name)
    if not env_val:
        return None
    # attempt same strategies on env var
    try:
        parsed = json.loads(env_val)
        return _normalize_private_key(parsed)
    except Exception:
        pass
    extracted = _extract_json_like(env_val)
    if extracted:
        try:
            parsed = json.loads(extracted)
            return _normalize_private_key(parsed)
        except Exception:
            pass
    try:
        parsed = ast.literal_eval(env_val)
        return _normalize_private_key(parsed)
    except Exception as e:
        raise RuntimeError(f"{key_name} exists in env but is not valid JSON/dict: {e}")

# ---- Load keys ----
sheets_key = load_json_key("SHEETS_KEY")
firebase_key = load_json_key("FIREBASE_KEY")

if sheets_key is None:
    st.error("❌ Failed to load SHEETS_KEY from secrets or .env.")
    st.stop()
if firebase_key is None:
    st.error("❌ Failed to load FIREBASE_KEY from secrets or .env.")
    st.stop()
cred = credentials.Certificate(firebase_key)
# ---- Create credentials and init Firebase ----
# ✅ Initialize Firebase App safely
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

# ✅ Initialize Firestore DB
db = firestore.client()

docs = db.collection('test_collection').stream()
for doc in docs:
    print(f'{doc.id} => {doc.to_dict()}')



try:
    # Convert HH:MM to float-style number
    ci = float(ci_str.replace(":", "."))
    co = float(co_str.replace(":", "."))

    # Handle overnight shift
    if co < ci:
        co += 24.0

    # Treat check-in/out as float numbers, then calculate worked time
    worked_time = round(co - ci, 2)
    raw_ot = worked_time - 8

    # OT calculation logic
    if raw_ot <= 0.4:
        ot = 0
    elif 0.5 <= raw_ot <= 0.7:
        ot = 0.5
    elif 0.8 <= raw_ot <= 1.0:
        ot = 1
    else:
        ot = round(raw_ot * 2) / 2

    # Night shift check
    night_shift = is_night_shift(ci_str, co_str)

except:
    st.warning(" Please enter valid time in HH:MM format.")
    ci_str, co_str, ot, night_shift = "09:00", "18:00", 0, False


COLLECTION = "attendance_records"

st.set_page_config(page_title="Sheet1", layout="wide")
st.title("📋 Employee Attendance Sheet Generator")

# 🔧 Firestore helpers
def reset_firestore():
    try:
        docs = db.collection(COLLECTION).stream()
        for doc in docs:
            db.collection(COLLECTION).document(doc.id).delete()
        st.session_state.clear()
        st.success("✅ Firestore data reset successfully.")
    except Exception as e:
        st.error(f"❌ Firestore reset error: {e}")

@st.cache_data(ttl=300)
def fetch_firestore_records():
    try:
        st.write("📡 Trying to connect to Firestore...")
        docs = db.collection(COLLECTION).stream()
        st.write("✅ Successfully fetched Firestore records.")
        return {doc.id: doc.to_dict() for doc in docs}
    except Exception as e:
        st.error(f"🔥 Error fetching Firestore data: {e}")
        return {}

def convert_to_python_types(data):
    return {
        k: (int(v) if isinstance(v, (np.integer, np.int64)) else float(v) if isinstance(v, np.floating) else v)
        for k, v in data.items()
    }

# ✅ Updated Only This Function
def safe_save(index, data):
    clean_data = convert_to_python_types(data)
    firestore_success = False
    sheets_success = False
    try:
        db.collection(COLLECTION).document(str(index)).set(clean_data, merge=True)
        firestore_success = True
    except Exception as e:
        st.warning(f"⚠️ Firestore save failed: {e}")
    try:
      append_to_sheet("Attendance_Backup", list(clean_data.values()))  # ✅ CORRECT
      sheets_success = True
    except Exception as e:
        st.warning(f"⚠️ Google Sheets backup failed: {e}")

    fetch_firestore_records.clear()

    if not firestore_success and not sheets_success:
        st.error("❌ Save failed. No backup was created.")
    elif not firestore_success:
        st.warning("✅ Saved to Google Sheets. But Firestore failed.")
    elif not sheets_success:
        st.warning("✅ Saved to Firebase. But Google Sheets backup failed.")
    else:
        st.success("✅ Saved in both Firebase & Google Sheets")

# 🔁 OT Logic

def calculate_custom_ot(hours):
    base = 8
    raw_ot = hours - base
    if raw_ot <= 0:
        return 0
    int_part = int(raw_ot)
    decimal = raw_ot - int_part
    decimal_str = f"{decimal:.2f}".split(".")[1]
    if len(decimal_str.rstrip("0")) == 1:
        dec = int(decimal_str[0])
        if dec <= 4: return int_part
        elif 5 <= dec <= 7: return int_part + 0.5
        else: return int_part + 1
    else:
        dec = int(decimal_str[:2])
        if dec <= 49: return int_part
        elif 50 <= dec <= 70: return int_part + 0.5
        else: return int_part + 1

def time_str_to_float_str(time_str):
    h, m = map(int, time_str.split(":"))
    return float(f"{h}.{str(m).zfill(2)[0]}")

def is_night_shift(ci_str, co_str):
    try:
        ci = float(ci_str.replace(":", "."))
        co = float(co_str.replace(":", "."))
        if co < ci:
            co += 24.0
        return ci >= 20.0 or co <= 8.0
    except:
        return False

# 📁 Upload Excel
uploaded_file = st.file_uploader("📄 Upload Excel with 'Employee Code' & 'Employee Name'", type=["xlsx"])
if st.button("🔄 Reset All Data"):
    reset_firestore()

stored_data = fetch_firestore_records()
current_index = int(st.session_state.get("current_index", 0))

if uploaded_file:
    if "uploaded_filename" not in st.session_state or st.session_state["uploaded_filename"] != uploaded_file.name:
        st.session_state["uploaded_filename"] = uploaded_file.name
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = [col.strip() for col in df.columns]
            if 'Employee Code' not in df.columns or 'Employee Name' not in df.columns:
                st.error("❌ File must include 'Employee Code' and 'Employee Name")
                st.stop()
            employee_list = df[['Employee Code', 'Employee Name']].drop_duplicates().reset_index(drop=True)
            st.session_state["employee_list"] = employee_list.to_dict("records")
            st.session_state["total_employees"] = len(employee_list)
        except Exception as e:
            st.error(f"❌ Failed to read Excel: {e}")
            st.stop()

if "month" not in st.session_state:
    st.session_state["month"] = datetime.now().month
if "year" not in st.session_state:
    st.session_state["year"] = datetime.now().year

st.session_state["month"] = st.selectbox("🗓️ Month", list(range(1, 13)), index=st.session_state["month"] - 1)
st.session_state["year"] = st.selectbox("📆 Year", list(range(2023, 2031)), index=st.session_state["year"] - 2023)

employee_list = pd.DataFrame(st.session_state.get("employee_list", []))

if not employee_list.empty and current_index < len(employee_list):
    emp = employee_list.iloc[current_index]
    st.subheader(f"🧑 {emp['Employee Name']} (Code: {emp['Employee Code']})")

    days_in_month = calendar.monthrange(st.session_state["year"], st.session_state["month"])[1]
    row_data = stored_data.get(str(current_index), {
        "Employee Code": emp["Employee Code"],
        "Employee Name": emp["Employee Name"]
    }).copy()

    total_ot = 0
    c_P = c_A = c_L = c_WO = c_HL = c_PH = 0

    for day in range(1, days_in_month + 1):
        date_str = f"{day:02d}-{st.session_state['month']:02d}"
        with st.expander(f"🗕️ Entry for {date_str}"):
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
                    ci = float(ci_str.replace(":", "."))
                    co = float(co_str.replace(":", "."))
                    if co < ci:
                        co += 24.0
                    hours = round(co - ci, 2)
                    ot = calculate_custom_ot(hours)
                    night_shift = is_night_shift(ci_str, co_str)
                except:
                    st.warning("⚠️ Please enter valid time in HH:MM format.")
                    ci_str, co_str, ot, night_shift = "09:00", "18:00", 0, False
                ci, co = ci_str, co_str
                row_data[f"{day:02d}_Night"] = "Yes" if night_shift else "No"
            else:
                if status == "A": c_A += 1
                elif status == "L": c_L += 1
                elif status == "WO": c_WO += 1
                elif status == "HL": c_HL += 1
                elif status == "PH": c_PH += 1
                ci = co = "00:00"
                ot = 0
                if status == "WO": co = "17:00"
                if status == "HL": co = "13:00"
                row_data[f"{day:02d}_Night"] = "No"

            row_data[f"{day:02d}_Status"] = status
            row_data[f"{day:02d}_Check-in"] = ci
            row_data[f"{day:02d}_Check-out"] = co
            row_data[f"{day:02d}_OT"] = ot
            total_ot += ot

    for day in range(days_in_month + 1, 32):
        for key in ["Status", "Check-in", "Check-out", "OT", "Night"]:
            row_data.pop(f"{day:02d}_{key}", None)

    row_data.update({
        "Total P": c_P, "Total A": c_A, "Total L": c_L,
        "Total WO": c_WO, "Total HL": c_HL, "Total PH": c_PH,
        "OT Hours": round(total_ot, 1)
    })

    sorted_row = dict(sorted(row_data.items(), key=lambda x: (not x[0].startswith(('Employee', 'Total', 'OT')), x[0])))
    st.markdown("### Preview Entry")
    st.dataframe(pd.DataFrame([sorted_row]), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏹️ Previous", key=f"btn_prev_{current_index}"):
            if current_index > 0:
                st.session_state["current_index"] = current_index - 1
                st.rerun()
    with col2:
        if st.button("✅ Save & Next", key=f"btn_next_{current_index}"):
            safe_save(current_index, row_data.copy())
            st.session_state["current_index"] = current_index + 1
            st.rerun()

stored_data = fetch_firestore_records()
if stored_data:
    st.markdown("---")
    st.subheader("🗓️ Download Attendance Till Now")
    sorted_records = []
    for i in range(st.session_state.get("total_employees", 0)):
        if str(i) in stored_data:
            v = stored_data[str(i)]
            sorted_v = dict(sorted(v.items(), key=lambda x: (not x[0].startswith(('Employee', 'Total', 'OT')), x[0])))
            sorted_records.append(sorted_v)

    if sorted_records:
        final_df = pd.DataFrame(sorted_records)
        st.dataframe(final_df, use_container_width=True)
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name="Attendance")
        st.download_button("📥 Download Excel Till Now", data=towrite.getvalue(), file_name="attendance_upto_now.xlsx")
