"""
Live fall-confirmation loop (Stage 2 of the funnel).

Flow:
  1. Read JSON lines from the ESP32 sensor node (serial). Buffer a rolling window.
  2. On a "fall_suspected" packet, pull a burst of frames from the ESP32-CAM.
  3. Build the feature vector, run the Random Forest.
  4. If confirmed -> push vitals + GPS to Firebase (caregiver alert).

TODOs: serial port, ESP32-CAM IP. The camera pull is optional — if the CAM
isn't reachable the model runs motion-only (image features = 0).
"""

from __future__ import annotations
import json
import time
from collections import deque

import numpy as np
import joblib

from feature_extraction import build_feature_vector, FEATURE_NAMES
import firebase_client

# ===================== TODO: config =====================
SERIAL_PORT = "COM3"          # TODO: e.g. "COM3" (Windows) or "/dev/ttyUSB0" (Linux)
BAUD        = 115200
CAM_URL     = "http://192.168.1.50/capture"   # TODO: your ESP32-CAM IP
MODEL_PATH  = "fall_rf.joblib"
WINDOW      = 40               # samples kept for motion features (~= 2 s at 20 Hz)
# ========================================================

try:
    import serial          # pyserial
except ImportError:
    serial = None
try:
    import cv2
    import requests
except ImportError:
    cv2 = None
    requests = None


def load_model():
    bundle = joblib.load(MODEL_PATH)
    assert bundle["features"] == FEATURE_NAMES, "feature order mismatch — retrain"
    return bundle["model"]


def grab_camera_frames(n=5):
    """Pull n JPEG frames from the ESP32-CAM. Returns [] if unavailable."""
    if cv2 is None or requests is None:
        return []
    frames = []
    for _ in range(n):
        try:
            r = requests.get(CAM_URL, timeout=1.5)
            arr = np.frombuffer(r.content, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                frames.append(img)
        except Exception:
            break
        time.sleep(0.1)
    return frames


def open_serial():
    if serial is None:
        print("[warn] pyserial not installed — running in DEMO mode (no hardware).")
        return None
    try:
        return serial.Serial(SERIAL_PORT, BAUD, timeout=1)
    except Exception as e:
        print(f"[warn] could not open {SERIAL_PORT} ({e}) — DEMO mode.")
        return None


def main():
    model = load_model()
    ser = open_serial()

    accel_buf = deque(maxlen=WINDOW)   # rows of [ax, ay, az]  (approx from magnitude here)
    tilt_buf  = deque(maxlen=WINDOW)
    last_vitals = {"hr": -1, "spo2": -1, "lat": 0.0, "lng": 0.0}

    print("Live inference running. Waiting for packets...")
    while True:
        line = None
        if ser is not None:
            raw = ser.readline().decode(errors="ignore").strip()
            line = raw or None
        else:
            time.sleep(1)      # DEMO mode: no data; wire a hardware node to see it work

        if not line:
            continue
        try:
            pkt = json.loads(line)
        except json.JSONDecodeError:
            continue

        # buffer motion. The node sends magnitude+tilt; store as pseudo-xyz for SMA.
        g = float(pkt.get("accel_g", 1.0))
        accel_buf.append([g / np.sqrt(3)] * 3)
        tilt_buf.append(float(pkt.get("tilt", 0.0)))
        last_vitals.update({k: pkt.get(k, last_vitals[k]) for k in last_vitals})

        # routine telemetry -> live charts
        firebase_client.push_telemetry(pkt.get("hr", -1), pkt.get("spo2", -1), "OK")

        if pkt.get("type") == "fall_suspected" and len(accel_buf) >= 5:
            frames = grab_camera_frames()
            fv = build_feature_vector(np.array(accel_buf), np.array(tilt_buf), frames)
            prob = model.predict_proba(fv.reshape(1, -1))[0][1]
            confirmed = prob >= 0.5
            print(f"[suspected] fall_prob={prob:.2f} -> "
                  f"{'CONFIRMED' if confirmed else 'dismissed'}")
            if confirmed:
                firebase_client.push_fall_event(
                    last_vitals["hr"], last_vitals["spo2"],
                    last_vitals["lat"], last_vitals["lng"])
                # The ESP32 already ran its 10 s on-device cancel window before this,
                # so a confirmed event here means the user did not cancel.


if __name__ == "__main__":
    main()
