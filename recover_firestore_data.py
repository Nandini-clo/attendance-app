from google.cloud import firestore

cred_path = "firebase_key.json"
db = firestore.Client.from_service_account_json(cred_path)

collection = db.collection("attendance_records")
docs = collection.stream()

found = False
for doc in docs:
    print(f"{doc.id} => {doc.to_dict()}")
    found = True

if not found:
    print("⚠️ No data found in attendance_records collection.")
