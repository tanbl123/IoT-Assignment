import os
import firebase_admin
from firebase_admin import credentials, db

cred_path = os.getenv("FIREBASE_CRED", "serviceAccountKey.json")
db_url = os.getenv(
    "FIREBASE_DB_URL",
    "https://fall-detection-ed1a9-default-rtdb.asia-southeast1.firebasedatabase.app"
)

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {"databaseURL": db_url})

db.reference("state/confirmed").set(True)
db.reference("state/alert").set(True)

print("Firebase /state/confirmed set to true")