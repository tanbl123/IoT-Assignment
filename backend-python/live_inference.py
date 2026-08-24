"""
REAL IoT live fall-confirmation loop.

Flow:
1. Read real JSON lines from ESP32 sensor node through serial.
2. Buffer real motion data.
3. Read HR and SpO2 from sensor JSON.
4. Save normal telemetry into Firebase all_records.
5. When fall_suspected is received, capture frames from ESP32-CAM.
6. Save raw frames and processed_detection.jpg.
7. Extract motion + image features.
8. Check camera posture: lying down / not lying / unclear.
9. Run Random Forest model.
10. Final decision:
    - ML says fall
    - camera says lying
    - impact is strong enough
    = FALL CONFIRMED
11. Save live IoT prediction result to CSV and Excel.
12. Save every detection result into Firebase all_records.
13. If confirmed, save into Firebase fall_events and update state/confirmed = true.
14. Actuator ESP32 reads Firebase and triggers buzzer/OLED/vibration.
"""

from __future__ import annotations

import json
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

SERIAL_PORT = "COM7"
BAUD = 115200

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

# ==================================================


try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

try:
    import cv2
    import requests
except ImportError:
    cv2 = None
    requests = None


def show_available_ports():
    if serial is None:
        return

    ports = list(serial.tools.list_ports.comports())

    print("\nAvailable COM ports:")

    if not ports:
        print("  No COM ports found.")
        return

    for port in ports:
        print(f"  {port.device} - {port.description}")


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


def open_serial():
    if serial is None:
        raise SystemExit(
            "[error] pyserial not installed.\n"
            "Run:\n"
            "pip install pyserial"
        )

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
        time.sleep(2)
        print(f"[serial] connected to {SERIAL_PORT} at {BAUD}")
        return ser

    except Exception as e:
        show_available_ports()
        raise SystemExit(
            f"\n[error] could not open {SERIAL_PORT}: {e}\n\n"
            "Fix:\n"
            "1. Plug in the SENSOR ESP32.\n"
            "2. Close Arduino Serial Monitor.\n"
            "3. Check Arduino IDE > Tools > Port.\n"
            "4. Update SERIAL_PORT in live_inference.py.\n"
            "5. Or run: python -m serial.tools.list_ports"
        )


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


def serial_packets(ser):
    while True:
        raw = ser.readline().decode(errors="ignore").strip()

        if not raw:
            continue

        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def safe_int(value, default=-1):
    try:
        if value is None:
            return default

        return int(float(value))

    except (ValueError, TypeError):
        return default


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
):
    file_exists = os.path.exists(LIVE_RESULT_CSV)

    row = {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "hr": hr,
        "hr_status": hr_status,
        "spo2": spo2,
        "spo2_status": spo2_status,

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


def process_packet(pkt, model, accel_buf, tilt_buf, last_vitals):
    g = float(pkt.get("accel_g", 1.0))
    tilt = float(pkt.get("tilt", 0.0))

    hr = safe_int(pkt.get("hr", -1), default=-1)
    spo2 = safe_int(pkt.get("spo2", -1), default=-1)

    hr_status, spo2_status, hr_display, spo2_display = classify_vitals(hr, spo2)

    print(f"[vitals] HR={hr_display} | SpO2={spo2_display}")

    accel_buf.append([g / np.sqrt(3)] * 3)
    tilt_buf.append(tilt)

    last_vitals.update({
        "hr": hr,
        "spo2": spo2,
        "lat": pkt.get("lat", last_vitals["lat"]),
        "lng": pkt.get("lng", last_vitals["lng"]),
    })

    firebase_client.push_telemetry(
        hr=hr,
        spo2=spo2,
        status="NORMAL",
        accel_g=g,
        tilt=tilt,
        lat=last_vitals["lat"],
        lng=last_vitals["lng"],
    )

    if pkt.get("type") != "fall_suspected":
        return

    if len(accel_buf) < 5:
        print("[stage-2] fall_suspected received, but not enough motion data yet")
        return

    print("\n================ FALL SUSPECTED ================")
    print("[stage-2] real fall_suspected received from ESP32 sensor")
    print(f"[stage-2] accel_g={g:.2f}, tilt={tilt:.1f}")
    print(f"[vitals] HR={hr_display} ({hr_status}) | SpO2={spo2_display} ({spo2_status})")

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

    prob = model.predict_proba(fv.reshape(1, -1))[0][1]
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

        firebase_client.push_fall_event(
            hr,
            spo2,
            last_vitals["lat"],
            last_vitals["lng"],
            image_path=debug_image_path,
            accel_g=peak_accel,  # strongest impact G-force seen in the window
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
    )

    firebase_client.push_all_record(
        hr=hr,
        spo2=spo2,
        lat=last_vitals["lat"],
        lng=last_vitals["lng"],
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


def main():
    validate_config()

    print("========== REAL IOT ML FALL DETECTION ==========")
    print("Mode: REAL IOT ONLY")
    print(f"Serial Port: {SERIAL_PORT}")
    print(f"Camera URL: {CAM_URL}")
    print("No demo fallback will be used.")
    print("================================================\n")

    model = load_model()

    test_camera_once()

    ser = open_serial()

    accel_buf = deque(maxlen=WINDOW)
    tilt_buf = deque(maxlen=WINDOW)

    last_vitals = {
        "hr": -1,
        "spo2": -1,
        "lat": 0.0,
        "lng": 0.0,
    }

    print("\n[system] waiting for real ESP32 sensor packets...")
    print("[system] Test 1: person lies down safely, then shake/rotate sensor board.")
    print("[system] Test 2: person stands/sits normally, then shake/rotate sensor board.")
    print("[system] Fall confirmed only when ML, camera posture, and impact all support fall.")
    print("[system] HR or SpO2 = -1 means Unknown.\n")

    for pkt in serial_packets(ser):
        print("RX:", pkt)

        process_packet(
            pkt,
            model,
            accel_buf,
            tilt_buf,
            last_vitals,
        )


if __name__ == "__main__":
    main()