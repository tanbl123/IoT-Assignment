"""
REAL IoT live fall-confirmation loop.

Flow:
1. Read real JSON lines from ESP32 sensor node through serial.
2. Buffer real motion data.
3. When fall_suspected is received, capture real frames from ESP32-CAM.
4. Save raw frames and processed_detection.jpg.
5. Extract motion + image features.
6. Run Random Forest model.
7. If confirmed, update Firebase /state/confirmed = true.
8. Actuator ESP32 reads Firebase and triggers buzzer/OLED/vibration.
"""

from __future__ import annotations

import json
import time
import os
from collections import deque

import numpy as np
import joblib

from feature_extraction import build_feature_vector, FEATURE_NAMES
import firebase_client


# ===================== CONFIG =====================

# Change this if your sensor ESP32 is not COM7.
SERIAL_PORT = "COM7"
BAUD = 115200

# Must be plain URL only.
# No [ ], no markdown, no parentheses.
CAM_URL = "http://10.214.169.191/capture"

MODEL_PATH = "fall_rf.joblib"

WINDOW = 40

# Prototype threshold.
# Lower = easier to confirm fall.
# Higher = stricter.
FALL_THRESHOLD = 0.25

CAM_FRAME_COUNT = 8
EVIDENCE_DIR = "captures"

# Since you want real ESP32-CAM result, keep this True.
# If camera captures 0 frames, prediction will stop instead of motion-only.
CAMERA_REQUIRED = True

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
    """
    Print available COM ports to help you choose the correct sensor ESP32 port.
    """
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
    """
    Stop early if the important config is wrong.
    """
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
            "python train_model.py"
        )


def load_model():
    """
    Load trained Random Forest model.
    """
    bundle = joblib.load(MODEL_PATH)

    assert bundle["features"] == FEATURE_NAMES, (
        "feature order mismatch — retrain the model using python train_model.py"
    )

    print("[ml] model loaded successfully")
    print("[ml] feature order:", FEATURE_NAMES)

    return bundle["model"]


def open_serial():
    """
    Open real sensor ESP32 serial port.
    No demo fallback.
    """
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
    """
    Test ESP32-CAM before starting real inference.
    """
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
            "2. Make sure laptop and ESP32-CAM are on same WiFi.\n"
            "3. Open CAM_URL in browser.\n"
            "4. Update CAM_URL if IP changed."
        )


def grab_camera_frames(n=CAM_FRAME_COUNT):
    """
    Pull JPEG frames from ESP32-CAM.
    """
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
    """
    Save captured fall frames into:
    captures/fall_event_xxxxx/
    """
    if not frames:
        print("[camera] no image captured")
        return None

    event_dir = os.path.join(
        EVIDENCE_DIR,
        f"fall_event_{int(time.time())}"
    )

    os.makedirs(event_dir, exist_ok=True)

    for i, frame in enumerate(frames):
        image_path = os.path.join(event_dir, f"frame_{i + 1}.jpg")
        cv2.imwrite(image_path, frame)

    print(f"[camera] saved {len(frames)} raw frame(s) to: {event_dir}")

    return event_dir


def serial_packets(ser):
    """
    Yield JSON packets read from ESP32 sensor node.
    Non-JSON Arduino logs are ignored.
    """
    while True:
        raw = ser.readline().decode(errors="ignore").strip()

        if not raw:
            continue

        try:
            yield json.loads(raw)

        except json.JSONDecodeError:
            continue


def process_packet(pkt, model, accel_buf, tilt_buf, last_vitals):
    """
    Handle one real sensor packet.
    """
    g = float(pkt.get("accel_g", 1.0))
    tilt = float(pkt.get("tilt", 0.0))

    # Your sensor sends acceleration magnitude.
    # Random Forest expects x, y, z window, so distribute magnitude equally.
    accel_buf.append([g / np.sqrt(3)] * 3)
    tilt_buf.append(tilt)

    last_vitals.update({
        k: pkt.get(k, last_vitals[k])
        for k in last_vitals
    })

    firebase_client.push_telemetry(
        pkt.get("hr", -1),
        pkt.get("spo2", -1),
        "OK",
    )

    if pkt.get("type") != "fall_suspected":
        return

    if len(accel_buf) < 5:
        print("[stage-2] fall_suspected received, but not enough motion data yet")
        return

    print("\n================ FALL SUSPECTED ================")
    print("[stage-2] real fall_suspected received from ESP32 sensor")
    print(f"[stage-2] accel_g={g:.2f}, tilt={tilt:.1f}")

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
            "processed_detection.jpg"
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

    prob = model.predict_proba(fv.reshape(1, -1))[0][1]
    confirmed = prob >= FALL_THRESHOLD

    print(f"[ml] fall_probability = {prob:.2f}")
    print(f"[ml] threshold = {FALL_THRESHOLD:.2f}")

    if confirmed:
        print("[result] FALL CONFIRMED — updating Firebase")
        firebase_client.push_fall_event(
            last_vitals["hr"],
            last_vitals["spo2"],
            last_vitals["lat"],
            last_vitals["lng"],
        )
    else:
        print("[result] dismissed — not a fall")

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
    print("[system] safe test: person lies down in ESP32-CAM view, then shake/rotate sensor board.\n")

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