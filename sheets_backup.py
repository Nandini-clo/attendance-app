import gspread
from google.oauth2.service_account import Credentials
import os

# Define scope
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Connect to service account
def append_to_sheet(data):
    SERVICE_ACCOUNT_FILE = 'google_sheets_key.json'  # 🟡 Replace with your actual file
    SPREADSHEET_ID = '10utjUxw0Zs8i-W623jaw_Fa6GWLuXT-0fuROK2zGQl4'  # 🟡 Replace with your Sheet ID

    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1

    # Convert dict to list of values (ensure consistent column order)
    ordered_keys = sorted(data.keys())
    row = [data.get(k, "") for k in ordered_keys]

    # Append to sheet
    sheet.append_row(row)
