"""
Firebase Realtime Database client for the backend.

Setup:
  1. Firebase console -> Project settings -> Service accounts -> Generate new
     private key. Save as serviceAccountKey.json in this folder (gitignored).
  2. Copy your Realtime Database URL (…-default-rtdb.firebaseio.com).
  3. Fill the TODOs below or set env vars FIREBASE_CRED and FIREBASE_DB_URL.

If firebase-admin or credentials are missing, calls become no-ops that print,
so the rest of the pipeline still runs during development.
"""

from __future__ import annotations
import os
import time

try:
    import firebase_admin
    from firebase_admin import credentials, db
    _HAVE_FIREBASE = True
except ImportError:
    _HAVE_FIREBASE = False

CRED_PATH = os.getenv("FIREBASE_CRED", "serviceAccountKey.json")   # TODO
DB_URL    = os.getenv("FIREBASE_DB_URL", "")                       # TODO: your RTDB URL

_initialized = False


def _init():
    global _initialized
    if _initialized:
        return True
    if not (_HAVE_FIREBASE and os.path.exists(CRED_PATH) and DB_URL):
        print("[firebase] not configured — running in offline print mode.")
        return False
    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
    _initialized = True
    return True


def push_telemetry(hr, spo2, status):
    """Routine vitals for the app's live charts."""
    payload = {"hr": hr, "spo2": spo2, "status": status, "ts": int(time.time())}
    if _init():
        db.reference("telemetry/latest").set(payload)
    else:
        print("[firebase offline] telemetry:", payload)


def push_fall_event(hr, spo2, lat, lng):
    """Confirmed fall -> append to history and set an alert flag for the app."""
    event = {"hr": hr, "spo2": spo2, "lat": lat, "lng": lng,
             "ts": int(time.time()), "status": "FALL_CONFIRMED"}
    if _init():
        db.reference("falls").push(event)          # history log
        db.reference("alert").set(event)           # caregiver alert flag
    else:
        print("[firebase offline] FALL EVENT:", event)
    return event
