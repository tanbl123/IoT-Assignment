"""
Live fall-confirmation loop (Stage 2 of the funnel).

Flow:
  1. Read JSON lines from the ESP32 sensor node (serial). Buffer a rolling window.
  2. On a "fall_suspected" packet, pull a burst of frames from the ESP32-CAM.
  3. Build the feature vector, run the Random Forest.
  4. If confirmed -> push vitals + GPS to Firebase (caregiver alert).

TODOs: serial port, ESP32-CAM IP. The camera pull is optional — if the CAM
isn't reachable the model runs motion-only (image features = 0).

DEMO / REPLAY MODE
  No hardware yet? Run:  python live_inference.py --demo
  This feeds the pipeline a scripted stream of packets that emulate the ESP32:
  a calm baseline, then a REAL fall (big impact + tilt) that gets CONFIRMED,
  then a FALSE alarm (a hard sit-down) that gets DISMISSED. It exercises the
  exact same code path as real hardware, so you can demo Stage 2 with no ESP32.
  Demo mode also turns on automatically if the serial port can't be opened.
"""

from __future__ import annotations
import sys
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
        print("[warn] pyserial not installed — falling back to DEMO mode.")
        return None
    try:
        return serial.Serial(SERIAL_PORT, BAUD, timeout=1)
    except Exception as e:
        print(f"[warn] could not open {SERIAL_PORT} ({e}) — falling back to DEMO mode.")
        return None


# ------------------------- packet sources -------------------------
def serial_packets(ser):
    """Yield JSON packets read from the ESP32 over serial (real hardware)."""
    while True:
        raw = ser.readline().decode(errors="ignore").strip()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def demo_packets():
    """
    Yield a scripted stream that emulates the ESP32 for a hardware-free demo.
    A packet mirrors what esp32-sensor-node.ino sends over serial.
    """
    def pkt(accel_g, tilt, hr=76, spo2=98, typ="telemetry"):
        return {"type": typ, "accel_g": round(accel_g, 2), "tilt": round(tilt, 1),
                "hr": hr, "spo2": spo2, "lat": 3.2117, "lng": 101.7215, "ts": 0}

    print("\n--- [1/3] calm baseline: person upright, moving normally ---")
    for i in range(15):
        yield pkt(1.0 + 0.03 * ((i % 3) - 1), 5.0)     # ~1 g, near-upright

    print("\n--- [2/3] REAL FALL: impact spike + big tilt change ---")
    for i in range(8):
        yield pkt(4.2 - 0.2 * i, 78.0, hr=112)          # slam + now on the ground
    yield pkt(4.3, 82.0, hr=115, typ="fall_suspected")  # ESP32 Stage-1 trigger

    print("\n--- recovering to baseline (window clears) ---")
    for i in range(45):
        yield pkt(1.0, 6.0)

    print("\n--- [3/3] FALSE ALARM: hard sit-down (bump, but little tilt) ---")
    for i in range(4):
        yield pkt(2.6, 14.0)
    yield pkt(2.6, 15.0, typ="fall_suspected")          # crosses ESP32 threshold...
    for i in range(6):
        yield pkt(1.0, 5.0)                              # ...but ML should dismiss it


# ------------------------- core processing ------------------------
def process_packet(pkt, model, accel_buf, tilt_buf, last_vitals, use_camera):
    """Handle one packet: buffer it, push telemetry, and confirm on 'fall_suspected'."""
    # buffer motion. The node sends magnitude+tilt; store as pseudo-xyz for SMA.
    g = float(pkt.get("accel_g", 1.0))
    accel_buf.append([g / np.sqrt(3)] * 3)
    tilt_buf.append(float(pkt.get("tilt", 0.0)))
    last_vitals.update({k: pkt.get(k, last_vitals[k]) for k in last_vitals})

    # routine telemetry -> live charts
    firebase_client.push_telemetry(pkt.get("hr", -1), pkt.get("spo2", -1), "OK")

    if pkt.get("type") == "fall_suspected" and len(accel_buf) >= 5:
        frames = grab_camera_frames() if use_camera else []
        fv = build_feature_vector(np.array(accel_buf), np.array(tilt_buf), frames)
        prob = model.predict_proba(fv.reshape(1, -1))[0][1]
        confirmed = prob >= 0.5
        print(f">>> [suspected] fall_prob={prob:.2f} -> "
              f"{'CONFIRMED — alerting caregiver' if confirmed else 'dismissed (not a fall)'}")
        if confirmed:
            firebase_client.push_fall_event(
                last_vitals["hr"], last_vitals["spo2"],
                last_vitals["lat"], last_vitals["lng"])
            # The ESP32 already ran its 10 s on-device cancel window before this,
            # so a confirmed event here means the user did not cancel.


def main():
    demo = "--demo" in sys.argv
    model = load_model()
    ser = None if demo else open_serial()
    if ser is None:
        demo = True                       # no serial -> demo replay instead of idling

    accel_buf = deque(maxlen=WINDOW)      # rows of [ax, ay, az] (approx from magnitude)
    tilt_buf  = deque(maxlen=WINDOW)
    last_vitals = {"hr": -1, "spo2": -1, "lat": 0.0, "lng": 0.0}

    if demo:
        print("=== DEMO / REPLAY MODE (no hardware) ===")
        source = demo_packets()
        delay  = 0.05                     # readable pacing for the demo
    else:
        print("Live inference running. Reading from ESP32 over serial...")
        source = serial_packets(ser)
        delay  = 0.0

    for pkt in source:
        process_packet(pkt, model, accel_buf, tilt_buf, last_vitals, use_camera=not demo)
        if delay:
            time.sleep(delay)

    if demo:
        print("\n=== demo finished — plug in an ESP32 and run without --demo for live data ===")


if __name__ == "__main__":
    main()
