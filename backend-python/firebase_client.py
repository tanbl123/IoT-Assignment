"""
Firebase Realtime Database client for the backend.

Paths used:
- telemetry/latest       : latest sensor reading
- all_records            : all history records, including normal, NOT FALL, and FALL CONFIRMED
- fall_events            : confirmed fall events only
- state/confirmed        : actuator ESP32 reads this to trigger buzzer
- state/alert            : actuator ESP32 alert flag
- state/latestFall       : latest confirmed fall detail
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


CRED_PATH = os.getenv("FIREBASE_CRED", "serviceAccountKey.json")

DB_URL = os.getenv(
    "FIREBASE_DB_URL",
    "https://fall-detection-ed1a9-default-rtdb.asia-southeast1.firebasedatabase.app/"
)

# How often (seconds) to append a vitals snapshot to history/vitals.
# telemetry/latest is overwritten on every packet, so it only ever holds the
# newest reading — no time-series. To let the Flutter app draw analytics
# graphs (HR/SpO2 over time) we ALSO append a snapshot to history/vitals, but
# throttled so a ~20 Hz sensor stream doesn't flood the database.
HISTORY_INTERVAL_SEC = int(os.getenv("FIREBASE_HISTORY_INTERVAL", "10"))

_initialized = False
_warned = False
_last_history_ts = 0.0

_last_normal_record_time = 0
NORMAL_RECORD_INTERVAL_SECONDS = 5


def _init():
    global _initialized, _warned

    if _initialized:
        return True

    if not _HAVE_FIREBASE:
        if not _warned:
            print("[firebase] firebase-admin not installed — running offline.")
            _warned = True
        return False

    if not os.path.exists(CRED_PATH):
        if not _warned:
            print(f"[firebase] credential file not found: {CRED_PATH}")
            print("[firebase] running in offline print mode.")
            _warned = True
        return False

    if not DB_URL:
        if not _warned:
            print("[firebase] database URL missing — running offline.")
            _warned = True
        return False

    try:
        cred = credentials.Certificate(CRED_PATH)

        firebase_admin.initialize_app(
            cred,
            {
                "databaseURL": DB_URL,
            },
        )

        _initialized = True
        print("[firebase] connected successfully")
        return True

    except Exception as e:
        if not _warned:
            print(f"[firebase] init failed: {e}")
            print("[firebase] running in offline print mode.")
            _warned = True
        return False


<<<<<<< Updated upstream
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
=======
def _now_ts():
    return int(time.time())


def push_telemetry(
    hr,
    spo2,
    status,
    accel_g=None,
    tilt=None,
    lat=0.0,
    lng=0.0,
):
    global _last_normal_record_time

    payload = {
        "record_type": "NORMAL_TELEMETRY",
        "hr": hr,
        "spo2": spo2,
        "status": status,
        "accel_g": accel_g,
        "tilt": tilt,
        "lat": lat,
        "lng": lng,
        "ts": _now_ts(),
    }

    if _init():
        try:
            db.reference("telemetry/latest").set(payload)

            current_time = time.time()

            if current_time - _last_normal_record_time >= NORMAL_RECORD_INTERVAL_SECONDS:
                db.reference("all_records").push(payload)
                db.reference("all_records_latest").set(payload)
                _last_normal_record_time = current_time

                print("[firebase] normal telemetry saved to all_records")

        except Exception as e:
            print(f"[firebase error] telemetry save failed: {e}")

>>>>>>> Stashed changes
    else:
        print(".", end="", flush=True)

    return payload


def push_all_record(
    hr,
    spo2,
    lat,
    lng,
    predicted_result,
    fall_probability,
    camera_posture,
    ml_says_fall,
    camera_says_lying,
    impact_says_fall,
    feature_report,
    event_folder="",
    processed_image="",
):
    event = {
        "record_type": "FALL_DETECTION_RESULT",
        "hr": hr,
        "spo2": spo2,
        "lat": lat,
        "lng": lng,
        "predicted_result": predicted_result,
        "is_confirmed_fall": predicted_result == "FALL CONFIRMED",
        "fall_probability": round(float(fall_probability), 3),
        "camera_posture": camera_posture,
        "ml_says_fall": bool(ml_says_fall),
        "camera_says_lying": bool(camera_says_lying),
        "impact_says_fall": bool(impact_says_fall),
        "features": feature_report,
        "event_folder": event_folder,
        "processed_image": processed_image,
        "ts": _now_ts(),
    }

    if _init():
        try:
            db.reference("all_records").push(event)
            db.reference("all_records_latest").set(event)

            print("[firebase] detection result saved to all_records")

        except Exception as e:
            print(f"[firebase error] all_records save failed: {e}")

    else:
        print("\n[firebase offline] ALL RECORD:", event)

    return event


def push_fall_event(hr, spo2, lat, lng):
    event = {
        "record_type": "FALL_CONFIRMED",
        "hr": hr,
        "spo2": spo2,
        "lat": lat,
        "lng": lng,
        "ts": _now_ts(),
        "status": "FALL_CONFIRMED",
    }

    if _init():
        try:
            db.reference("fall_events").push(event)

            db.reference("state/confirmed").set(True)
            db.reference("state/alert").set(True)
            db.reference("state/latestFall").set(event)

            print("[firebase] fall event saved to fall_events")
            print("[firebase] /state/confirmed set to true")

        except Exception as e:
            print(f"[firebase error] fall event save failed: {e}")

    else:
        print("\n[firebase offline] FALL EVENT:", event)

    return event