"""
REAL IoT live fall-confirmation loop — FIREBASE MODE.

Flow:
1. Sensor ESP32 sends telemetry/latest and state/suspected to Firebase.
2. Python reads Firebase instead of COM7 Serial.
3. When state/suspected has a new fall_suspected event, Python captures ESP32-CAM frames.
4. Python extracts motion + image features.
5. Random Forest predicts fall probability.
6. Final decision requires:
   - ML says fall
   - camera says lying
   - impact is strong enough
7. Python writes all_records, fall_events, and state/confirmed.
8. Actuator ESP32 reads state/confirmed and triggers buzzer/OLED/vibration.
"""

from __future__ import annotations

import time
import os
import csv
from datetime import datetime
from collections import deque

import pandas as pd
import numpy as np
import joblib

from feature_extraction import build_feature_vector, FEATURE_NAMES
import firebase_client


# ===================== CONFIG =====================

# COM7 is no longer needed in Firebase mode.
USE_FIREBASE_MODE = True

# Plain URL only. No [ ], no markdown, no parentheses.
CAM_URL = "http://10.214.169.191/capture"

MODEL_PATH = "fall_rf.joblib"

WINDOW = 40

FALL_THRESHOLD = 0.45
MIN_PEAK_ACCEL_FOR_FALL = 1.40

CAM_FRAME_COUNT = 8
EVIDENCE_DIR = "captures"

LIVE_RESULT_CSV = "live_iot_results.csv"
LIVE_RESULT_XLSX = "live_iot_results.xlsx"

CAMERA_REQUIRED = True
REQUIRE_CAMERA_LYING_CONFIRMATION = True
REQUIRE_IMPACT_CONFIRMATION = True

FIREBASE_TELEMETRY_PATH = "telemetry/latest"
FIREBASE_SUSPECTED_PATH = "state/suspected"

POLL_INTERVAL_SECONDS = 0.5

NORMAL_RECORD_INTERVAL_SECONDS = 1

# ==================================================


try:
    import cv2
    import requests
except ImportError:
    cv2 = None
    requests = None


_last_normal_record_time = 0


# ===================== BASIC HELPERS =====================

def validate_config():
    if "[" in CAM_URL or "]" in CAM_URL or "(" in CAM_URL or ")" in CAM_URL:
        raise SystemExit(
            "[error] CAM_URL is wrong.\n"
            "Use plain URL only, for example:\n"
            'CAM_URL = "http://10.214.169.191/capture"'
        )

    if not os.path.exists(MODEL_PATH):
        raise SystemExit(
            f"[error] {MODEL_PATH} not found.\n"
            "Run this first:\n"
            "python export_rf_excel.py"
        )


def load_model():
    bundle = joblib.load(MODEL_PATH)

    assert bundle["features"] == FEATURE_NAMES, (
        "feature order mismatch — retrain the model using python export_rf_excel.py"
    )

    print("[ml] model loaded successfully")
    print("[ml] feature order:", FEATURE_NAMES)

    return bundle["model"]


def safe_int(value, default=-1):
    try:
        if value is None:
            return default

        return int(float(value))

    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (ValueError, TypeError):
        return default


def safe_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in ["true", "1", "yes", "y"]

    return False


def now_ts():
    return int(time.time())


# ===================== FIREBASE HELPERS =====================

def firebase_get(path):
    """
    Read a Firebase Realtime Database path.
    Uses firebase_client.py.
    """
    try:
        if hasattr(firebase_client, "read_path"):
            return firebase_client.read_path(path)

        if not firebase_client._init():
            return None

        return firebase_client.db.reference(path).get()

    except Exception as e:
        print(f"[firebase read error] {path}: {e}")
        return None


def firebase_set(path, value):
    try:
        if not firebase_client._init():
            return False

        firebase_client.db.reference(path).set(value)
        return True

    except Exception as e:
        print(f"[firebase write error] {path}: {e}")
        return False


def append_normal_record_only(pkt):
    """
    Save normal telemetry into all_records without overwriting telemetry/latest.

    Important:
    Sensor ESP32 owns telemetry/latest.
    Python should not overwrite it, because it contains GPS fix/sats/lat/lng.
    """
    global _last_normal_record_time

    current_time = time.time()

    if current_time - _last_normal_record_time < NORMAL_RECORD_INTERVAL_SECONDS:
        return

    payload = {
        "record_type": "NORMAL_TELEMETRY",
        "node": "python_backend_history",
        "hr": safe_int(pkt.get("hr", -1), -1),
        "spo2": safe_int(pkt.get("spo2", -1), -1),
        "status": "NORMAL",
        "accel_g": safe_float(pkt.get("accel_g", 0.0), 0.0),
        "tilt": safe_float(pkt.get("tilt", 0.0), 0.0),
        "lat": safe_float(pkt.get("lat", 0.0), 0.0),
        "lng": safe_float(pkt.get("lng", 0.0), 0.0),
        "fix": safe_bool(pkt.get("fix", False)),
        "has_last_fix": safe_bool(pkt.get("has_last_fix", pkt.get("fix", False))),
        "sats": safe_int(pkt.get("sats", 0), 0),
        "gps_chars": safe_int(pkt.get("gps_chars", -1), -1),
        "gps_age_ms": safe_int(pkt.get("gps_age_ms", -1), -1),
        "ts": now_ts(),
    }

    try:
        if not firebase_client._init():
            return

        firebase_client.db.reference("all_records").push(payload)
        firebase_client.db.reference("all_records_latest").set(payload)

        _last_normal_record_time = current_time

        print("[firebase] normal telemetry saved to all_records")

    except Exception as e:
        print(f"[firebase error] normal telemetry save failed: {e}")


def push_fall_event_safe(hr, spo2, lat, lng, image_path="", accel_g=None):
    """
    Supports all versions of firebase_client.py:
    - push_fall_event(hr, spo2, lat, lng)
    - push_fall_event(hr, spo2, lat, lng, image_path="")
    - push_fall_event(hr, spo2, lat, lng, image_path="", accel_g=None)
    """
    try:
        return firebase_client.push_fall_event(
            hr,
            spo2,
            lat,
            lng,
            image_path=image_path if image_path else "",
            accel_g=accel_g,
        )

    except TypeError:
        try:
            return firebase_client.push_fall_event(
                hr,
                spo2,
                lat,
                lng,
                image_path=image_path if image_path else "",
            )

        except TypeError:
            return firebase_client.push_fall_event(
                hr,
                spo2,
                lat,
                lng,
            )


def test_firebase_connection():
    print("[firebase] testing read access...")

    test_data = firebase_get(FIREBASE_TELEMETRY_PATH)

    if test_data is None:
        print("[firebase warning] telemetry/latest is empty or Firebase read failed.")
        print("[firebase warning] Make sure:")
        print("  1. serviceAccountKey.json is inside backend-python folder")
        print("  2. FIREBASE_DB_URL is correct")
        print("  3. Sensor ESP32 already uploaded telemetry/latest")
    else:
        print("[firebase] read OK")
        print("[firebase] latest telemetry:", test_data)


# ===================== CAMERA HELPERS =====================

def test_camera_once():
    if cv2 is None or requests is None:
        raise SystemExit(
            "[error] opencv-python or requests not installed.\n"
            "Run:\n"
            "pip install opencv-python requests"
        )

    print(f"[camera] testing {CAM_URL}")

    try:
        r = requests.get(CAM_URL, timeout=5)

        if r.status_code != 200:
            raise SystemExit(
                f"[error] ESP32-CAM returned HTTP {r.status_code}.\n"
                "Open the camera URL in browser and check /capture."
            )

        arr = np.frombuffer(r.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is None:
            raise SystemExit(
                "[error] ESP32-CAM response is not a valid image.\n"
                "Check your ESP32-CAM /capture endpoint."
            )

        os.makedirs(EVIDENCE_DIR, exist_ok=True)

        test_path = os.path.join(EVIDENCE_DIR, "startup_camera_test.jpg")
        cv2.imwrite(test_path, img)

        print(f"[camera] OK, startup test image saved to: {test_path}")

    except Exception as e:
        raise SystemExit(
            f"[error] camera test failed: {e}\n\n"
            "Fix:\n"
            "1. Make sure ESP32-CAM is powered on.\n"
            "2. Make sure laptop and ESP32-CAM are on the same WiFi.\n"
            "3. Open CAM_URL in browser.\n"
            "4. Update CAM_URL if IP changed."
        )


def grab_camera_frames(n=CAM_FRAME_COUNT):
    frames = []

    for i in range(n):
        try:
            r = requests.get(CAM_URL, timeout=2)

            if r.status_code != 200:
                print(f"[camera] frame {i + 1}: HTTP {r.status_code}")
                break

            arr = np.frombuffer(r.content, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

            if img is not None:
                frames.append(img)
            else:
                print(f"[camera] frame {i + 1}: decode failed")

        except Exception as e:
            print(f"[camera] frame {i + 1}: capture failed - {e}")
            break

        time.sleep(0.1)

    return frames


def save_fall_frames(frames):
    if not frames:
        print("[camera] no image captured")
        return None

    event_dir = os.path.join(
        EVIDENCE_DIR,
        f"fall_event_{int(time.time())}",
    )

    os.makedirs(event_dir, exist_ok=True)

    for i, frame in enumerate(frames):
        image_path = os.path.join(event_dir, f"frame_{i + 1}.jpg")
        cv2.imwrite(image_path, frame)

    print(f"[camera] saved {len(frames)} raw frame(s) to: {event_dir}")

    return event_dir


# ===================== CLASSIFICATION HELPERS =====================

def classify_vitals(hr, spo2):
    hr_status = "UNKNOWN" if hr == -1 else "DETECTED"
    spo2_status = "UNKNOWN" if spo2 == -1 else "DETECTED"

    hr_display = "Unknown" if hr == -1 else str(hr)
    spo2_display = "Unknown" if spo2 == -1 else str(spo2)

    return hr_status, spo2_status, hr_display, spo2_display


def classify_camera_posture(feature_report):
    aspect = feature_report.get("bbox_aspect_ratio", 0)
    centroid = feature_report.get("centroid_height", 0)
    motion = feature_report.get("frame_motion", 0)

    if aspect == 0 and centroid == 0:
        return "NO CLEAR PERSON / MOTION DETECTED", False

    if aspect >= 1.25 and centroid >= 0.45:
        return "LYING DOWN DETECTED", True

    if aspect >= 1.50:
        return "POSSIBLE LYING DOWN", True

    if motion > 0 and centroid >= 0.45:
        return "LOW POSTURE / UNCLEAR", False

    return "NOT LYING / UNCLEAR POSTURE", False


def print_gps_status(pkt):
    lat = safe_float(pkt.get("lat", 0.0), 0.0)
    lng = safe_float(pkt.get("lng", 0.0), 0.0)

    gps_chars = safe_int(pkt.get("gps_chars", -1), -1)
    gps_fix = safe_bool(pkt.get("fix", False))
    has_last_fix = safe_bool(pkt.get("has_last_fix", pkt.get("fix", False)))
    sats = safe_int(pkt.get("sats", 0), 0)
    gps_age_ms = safe_int(pkt.get("gps_age_ms", -1), -1)

    if lat != 0.0 and lng != 0.0:
        location_text = "LOCATION OK"
    else:
        location_text = "NO LOCATION YET"

    print(
        f"[gps] {location_text} | "
        f"chars={gps_chars} | "
        f"fix={'YES' if gps_fix else 'NO'} | "
        f"last_fix={'YES' if has_last_fix else 'NO'} | "
        f"sats={sats} | "
        f"age={gps_age_ms}ms | "
        f"lat={lat:.6f} | "
        f"lng={lng:.6f}"
    )


# ===================== LOGGING =====================

def save_live_iot_result(
    event_dir,
    processed_image_path,
    feature_report,
    camera_posture,
    ml_says_fall,
    camera_says_lying,
    impact_says_fall,
    fall_probability,
    predicted_result,
    firebase_updated,
    hr,
    hr_status,
    spo2,
    spo2_status,
    lat,
    lng,
):
    file_exists = os.path.exists(LIVE_RESULT_CSV)

    row = {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "hr": hr,
        "hr_status": hr_status,
        "spo2": spo2,
        "spo2_status": spo2_status,

        "lat": lat,
        "lng": lng,

        "event_folder": event_dir if event_dir else "",
        "processed_image": processed_image_path if processed_image_path else "",

        "sma": feature_report.get("sma", 0),
        "peak_accel": feature_report.get("peak_accel", 0),
        "tilt_change": feature_report.get("tilt_change", 0),
        "stillness": feature_report.get("stillness", 0),
        "bbox_aspect_ratio": feature_report.get("bbox_aspect_ratio", 0),
        "centroid_height": feature_report.get("centroid_height", 0),
        "frame_motion": feature_report.get("frame_motion", 0),

        "camera_posture": camera_posture,
        "ml_says_fall": ml_says_fall,
        "camera_says_lying": camera_says_lying,
        "impact_says_fall": impact_says_fall,

        "fall_probability": round(float(fall_probability), 3),
        "predicted_result": predicted_result,
        "firebase_updated": firebase_updated,
    }

    with open(LIVE_RESULT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)

    print(f"[log] live IoT result saved to CSV: {LIVE_RESULT_CSV}")

    try:
        df = pd.read_csv(LIVE_RESULT_CSV)

        with pd.ExcelWriter(LIVE_RESULT_XLSX, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Live IoT Results", index=False)

        print(f"[log] live IoT result also saved to Excel: {LIVE_RESULT_XLSX}")

    except Exception as e:
        print(f"[log warning] CSV saved, but Excel export failed: {e}")


# ===================== FIREBASE PACKET NORMALIZATION =====================

def normalize_firebase_packet(data, packet_type):
    """
    Convert Firebase JSON into packet format.
    Also includes GPS fields for checking GPS status.
    """
    if not isinstance(data, dict):
        return None

    pkt = {
        "type": packet_type,
        "accel_g": safe_float(data.get("accel_g", 1.0), 1.0),
        "tilt": safe_float(data.get("tilt", 0.0), 0.0),

        "hr": safe_int(data.get("hr", -1), -1),
        "spo2": safe_int(data.get("spo2", -1), -1),

        "lat": safe_float(data.get("lat", 0.0), 0.0),
        "lng": safe_float(data.get("lng", 0.0), 0.0),

        "gps_chars": safe_int(data.get("gps_chars", -1), -1),
        "fix": safe_bool(data.get("fix", False)),
        "has_last_fix": safe_bool(data.get("has_last_fix", data.get("fix", False))),
        "sats": safe_int(data.get("sats", 0), 0),
        "gps_age_ms": safe_int(data.get("gps_age_ms", -1), -1),

        "ts": data.get("ts"),
        "event": data.get("event"),
    }

    return pkt


# ===================== MAIN PROCESSING =====================

def process_packet(pkt, model, accel_buf, tilt_buf, last_vitals):
    g = safe_float(pkt.get("accel_g", 1.0), 1.0)
    tilt = safe_float(pkt.get("tilt", 0.0), 0.0)

    hr = safe_int(pkt.get("hr", -1), default=-1)
    spo2 = safe_int(pkt.get("spo2", -1), default=-1)

    lat = safe_float(pkt.get("lat", last_vitals["lat"]), last_vitals["lat"])
    lng = safe_float(pkt.get("lng", last_vitals["lng"]), last_vitals["lng"])

    hr_status, spo2_status, hr_display, spo2_display = classify_vitals(hr, spo2)

    print(f"[vitals] HR={hr_display} | SpO2={spo2_display}")
    print_gps_status(pkt)

    accel_buf.append([g / np.sqrt(3)] * 3)
    tilt_buf.append(tilt)

    last_vitals.update({
        "hr": hr,
        "spo2": spo2,
        "lat": lat,
        "lng": lng,
        "gps_chars": safe_int(pkt.get("gps_chars", -1), -1),
        "gps_fix": safe_bool(pkt.get("fix", False)),
        "has_last_fix": safe_bool(pkt.get("has_last_fix", pkt.get("fix", False))),
        "sats": safe_int(pkt.get("sats", 0), 0),
        "gps_age_ms": safe_int(pkt.get("gps_age_ms", -1), -1),
    })

    # In Firebase mode, do NOT call firebase_client.push_telemetry()
    # because that would overwrite telemetry/latest and remove GPS fields.
    if pkt.get("type") == "telemetry":
        append_normal_record_only(pkt)
        return

    if pkt.get("type") != "fall_suspected":
        return

    if len(accel_buf) < 5:
        print("[stage-2] fall_suspected received, but not enough motion data yet")
        return

    print("\n================ FALL SUSPECTED ================")
    print("[stage-2] real fall_suspected received from Firebase")
    print(f"[stage-2] accel_g={g:.2f}, tilt={tilt:.1f}")
    print(f"[vitals] HR={hr_display} ({hr_status}) | SpO2={spo2_display} ({spo2_status})")
    print(f"[gps] fall event location lat={lat:.6f}, lng={lng:.6f}")

    frames = grab_camera_frames(n=CAM_FRAME_COUNT)

    print(f"[camera] captured {len(frames)} frame(s)")

    if CAMERA_REQUIRED and len(frames) == 0:
        print("[camera] required, but 0 frames captured")
        print("[result] prediction skipped because ESP32-CAM image was not captured")
        print("================================================\n")
        return

    event_dir = save_fall_frames(frames)

    debug_image_path = None

    if event_dir:
        debug_image_path = os.path.join(
            event_dir,
            "processed_detection.jpg",
        )

    fv = build_feature_vector(
        np.array(accel_buf),
        np.array(tilt_buf),
        frames,
        save_debug_path=debug_image_path,
    )

    if debug_image_path:
        print(f"[image processing] saved processed image: {debug_image_path}")

    feature_report = {
        name: round(float(value), 3)
        for name, value in zip(FEATURE_NAMES, fv)
    }

    print("[features]", feature_report)

    camera_posture, camera_says_lying = classify_camera_posture(feature_report)
    print(f"[camera posture] {camera_posture}")

    fv_2d = np.asarray(fv).reshape(1, -1)
    feature_df = pd.DataFrame(fv_2d, columns=FEATURE_NAMES)

    prob = model.predict_proba(feature_df)[0][1]
    ml_says_fall = prob >= FALL_THRESHOLD

    peak_accel = feature_report.get("peak_accel", 0)
    impact_says_fall = peak_accel >= MIN_PEAK_ACCEL_FOR_FALL

    confirmed = ml_says_fall

    if REQUIRE_CAMERA_LYING_CONFIRMATION:
        confirmed = confirmed and camera_says_lying

    if REQUIRE_IMPACT_CONFIRMATION:
        confirmed = confirmed and impact_says_fall

    print(f"[ml] fall_probability = {prob:.2f}")
    print(f"[ml] threshold = {FALL_THRESHOLD:.2f}")
    print(f"[ml decision] ML says fall: {ml_says_fall}")

    print(f"[camera decision] Camera says lying: {camera_says_lying}")
    print(f"[impact] peak_accel = {peak_accel:.2f}, required >= {MIN_PEAK_ACCEL_FOR_FALL:.2f}")
    print(f"[impact decision] Impact says fall: {impact_says_fall}")

    print(f"[final rule] require camera lying: {REQUIRE_CAMERA_LYING_CONFIRMATION}")
    print(f"[final rule] require impact: {REQUIRE_IMPACT_CONFIRMATION}")

    if confirmed:
        print("[result] FALL CONFIRMED — updating Firebase")

        push_fall_event_safe(
            hr=hr,
            spo2=spo2,
            lat=lat,
            lng=lng,
            image_path=debug_image_path if debug_image_path else "",
            accel_g=peak_accel,  # strongest impact G-force -> shown in fall history
        )

        predicted_result = "FALL CONFIRMED"
        firebase_updated = "Yes"

    else:
        if not impact_says_fall and camera_says_lying:
            print("[result] NOT FALL — lying posture detected, but impact is not strong enough")
        elif ml_says_fall and not camera_says_lying:
            print("[result] NOT FALL — sensor/ML triggered, but camera did not detect lying posture")
        elif not ml_says_fall and camera_says_lying:
            print("[result] NOT FALL — camera detected lying posture, but ML probability is too low")
        else:
            print("[result] NOT FALL — dismissed")

        predicted_result = "NOT FALL"
        firebase_updated = "No"

    save_live_iot_result(
        event_dir=event_dir,
        processed_image_path=debug_image_path,
        feature_report=feature_report,
        camera_posture=camera_posture,
        ml_says_fall=ml_says_fall,
        camera_says_lying=camera_says_lying,
        impact_says_fall=impact_says_fall,
        fall_probability=prob,
        predicted_result=predicted_result,
        firebase_updated=firebase_updated,
        hr=hr,
        hr_status=hr_status,
        spo2=spo2,
        spo2_status=spo2_status,
        lat=lat,
        lng=lng,
    )

    firebase_client.push_all_record(
        hr=hr,
        spo2=spo2,
        lat=lat,
        lng=lng,
        predicted_result=predicted_result,
        fall_probability=prob,
        camera_posture=camera_posture,
        ml_says_fall=ml_says_fall,
        camera_says_lying=camera_says_lying,
        impact_says_fall=impact_says_fall,
        feature_report=feature_report,
        event_folder=event_dir if event_dir else "",
        processed_image=debug_image_path if debug_image_path else "",
    )

    print("================================================\n")


# ===================== FIREBASE LIVE LOOP =====================

def make_suspected_key(data):
    if not isinstance(data, dict):
        return None

    return (
        data.get("ts"),
        data.get("accel_g"),
        data.get("tilt"),
        data.get("event"),
    )


def firebase_live_loop(model):
    accel_buf = deque(maxlen=WINDOW)
    tilt_buf = deque(maxlen=WINDOW)

    last_vitals = {
        "hr": -1,
        "spo2": -1,
        "lat": 0.0,
        "lng": 0.0,
        "gps_chars": -1,
        "gps_fix": False,
        "has_last_fix": False,
        "sats": 0,
        "gps_age_ms": -1,
    }

    last_telemetry_ts = None

    existing_suspected = firebase_get(FIREBASE_SUSPECTED_PATH)
    last_suspected_key = make_suspected_key(existing_suspected)

    if last_suspected_key is not None:
        print("[system] Existing old suspected event found and ignored.")
        print("[system] Trigger a new suspected fall for a new detection.")

    print("\n[system] Firebase mode started.")
    print("[system] Sensor ESP32 can now be powered by power bank.")
    print("[system] Python reads:")
    print(f"  - {FIREBASE_TELEMETRY_PATH}")
    print(f"  - {FIREBASE_SUSPECTED_PATH}")
    print("[system] Waiting for Firebase sensor data...\n")

    while True:
        telemetry_data = firebase_get(FIREBASE_TELEMETRY_PATH)

        if isinstance(telemetry_data, dict):
            telemetry_ts = telemetry_data.get("ts")

            if telemetry_ts != last_telemetry_ts:
                last_telemetry_ts = telemetry_ts

                pkt = normalize_firebase_packet(
                    telemetry_data,
                    packet_type="telemetry",
                )

                if pkt is not None:
                    print("FB TELEMETRY:", pkt)
                    process_packet(
                        pkt,
                        model,
                        accel_buf,
                        tilt_buf,
                        last_vitals,
                    )

        suspected_data = firebase_get(FIREBASE_SUSPECTED_PATH)

        if isinstance(suspected_data, dict):
            suspected_key = make_suspected_key(suspected_data)
            event_name = suspected_data.get("event")

            if event_name == "fall_suspected" and suspected_key != last_suspected_key:
                last_suspected_key = suspected_key

                pkt = normalize_firebase_packet(
                    suspected_data,
                    packet_type="fall_suspected",
                )

                if pkt is not None:
                    print("FB SUSPECTED:", pkt)
                    process_packet(
                        pkt,
                        model,
                        accel_buf,
                        tilt_buf,
                        last_vitals,
                    )

        time.sleep(POLL_INTERVAL_SECONDS)


# ===================== ENTRY POINT =====================

def main():
    validate_config()

    print("========== REAL IOT ML FALL DETECTION ==========")
    print("Mode: FIREBASE MODE")
    print("Serial Port: NOT USED")
    print(f"Camera URL: {CAM_URL}")
    print("Sensor ESP32 can run on power bank.")
    print("No demo fallback will be used.")
    print("================================================\n")

    model = load_model()

    test_firebase_connection()
    test_camera_once()

    print("[system] Safe test method only:")
    print("[system] Person stays safely lying down for camera confirmation.")
    print("[system] Shake/rotate the sensor board by hand to trigger suspected fall.")
    print("[system] Do not perform an actual fall.")
    print("[system] Fall confirmed only when ML, camera posture, and impact all support fall.")
    print("[system] HR or SpO2 = -1 means Unknown.")
    print("[system] For GPS, wait until Python shows LOCATION OK before triggering fall.\n")

    firebase_live_loop(model)


if __name__ == "__main__":
    main()