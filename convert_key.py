import json
import base64
from dotenv import set_key

# Read firebase_key.json
with open("firebase_key.json", "r") as f:
    key_content = f.read()

# Base64 encode
encoded_key = base64.b64encode(key_content.encode()).decode()

# Save to .env
set_key(".env", "FIREBASE_KEY", encoded_key)
print("✅ Firebase key encoded and saved to .env")
