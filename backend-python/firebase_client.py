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

# How often (seconds) to append a vitals snapshot to history/vitals.
# telemetry/latest is overwritten on every packet, so it only ever holds the
# newest reading — no time-series. To let the Flutter app draw analytics
# graphs (HR/SpO2 over time) we ALSO append a snapshot to history/vitals, but
# throttled so a ~20 Hz sensor stream doesn't flood the database.
HISTORY_INTERVAL_SEC = int(os.getenv("FIREBASE_HISTORY_INTERVAL", "10"))

_initialized = False
_warned = False
_last_history_ts = 0.0


def _init():
    global _initialized, _warned
    if _initialized:
        return True
    if not (_HAVE_FIREBASE and os.path.exists(CRED_PATH) and DB_URL):
        if not _warned:                    # warn once, not on every packet
            print("[firebase] not configured — running in offline print mode "
                  "(telemetry shown as '.', fall events shown in full).")
            _warned = True
        return False
    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
    _initialized = True
    return True


def push_telemetry(hr, spo2, status):
    """Routine vitals for the app's live charts + throttled history for analytics.

    * telemetry/latest  -> overwritten each call (the app's live tile).
    * history/vitals/<pushId> -> an append-only time-series the Flutter app
      reads to draw HR/SpO2 charts and daily reports. Appended at most once
      every HISTORY_INTERVAL_SEC so the database doesn't fill with ~20 rows/sec.
    """
    global _last_history_ts
    now = time.time()
    payload = {"hr": hr, "spo2": spo2, "status": status, "ts": int(now)}
    if _init():
        db.reference("telemetry/latest").set(payload)
        if now - _last_history_ts >= HISTORY_INTERVAL_SEC:
            db.reference("history/vitals").push(payload)   # time-series log
            _last_history_ts = now
    else:
        # offline: a compact heartbeat so the demo isn't flooded with lines
        print(".", end="", flush=True)


# def push_fall_event(hr, spo2, lat, lng):
#     """Confirmed fall -> append to history and set an alert flag for the app."""
#     event = {"hr": hr, "spo2": spo2, "lat": lat, "lng": lng,
#              "ts": int(time.time()), "status": "FALL_CONFIRMED"}
#     if _init():
#         db.reference("falls").push(event)          # history log
#         db.reference("alert").set(event)           # caregiver alert flag
#     else:
#         print("\n[firebase offline] FALL EVENT:", event)
#     return event
def push_fall_event(hr, spo2, lat, lng):
    event = {
        "hr": hr,
        "spo2": spo2,
        "lat": lat,
        "lng": lng,
        "ts": int(time.time()),
        "status": "FALL_CONFIRMED"
    }

    if _init():
        db.reference("falls").push(event)
        db.reference("state/confirmed").set(True)
        db.reference("state/alert").set(True)
        db.reference("state/latestFall").set(event)
        print("[firebase] /state/confirmed set to true")
    else:
        print("\n[firebase offline] FALL EVENT:", event)

    return event
