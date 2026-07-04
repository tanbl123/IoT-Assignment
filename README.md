# Smart Elderly Fall Detection System (IoT + ML)

A wearable + edge system that detects falls in elderly users, confirms them with
machine learning, reads vital signs and location, and alerts a caregiver in real time.

> University IoT assignment. This repository is a **scaffold**: every part has
> starter code with clear `TODO` markers for credentials, pin numbers, and keys.

---

## 1. Architecture

Three parts communicate over Bluetooth/Wi-Fi and the cloud:

```
 ┌────────────────────┐     motion + vitals      ┌──────────────────────┐
 │  ESP32 Sensor Node │ ───────(BT/WiFi)───────►  │  Laptop/PC Backend   │
 │  MPU6050 (accel/   │                           │  (Python)            │
 │   gyro)            │                           │                      │
 │  MAX30102 (HR/SpO2)│     "fall suspected"      │  feature extraction  │
 │  NEO-6M (GPS)      │ ─────────trigger────────► │  + Random Forest     │
 │  threshold filter  │                           │  confirm fall        │
 └─────────┬──────────┘                           └──────────┬───────────┘
           │ drives                                          │ on confirmed fall
           ▼                                                 ▼
 ┌────────────────────┐     image stream          ┌──────────────────────┐
 │  Actuators         │ ◄──────────────────────── │  Firebase Realtime DB │
 │  buzzer, vib motor │                           │  + caregiver alert    │
 │  OLED, SOS LED     │     ┌─────────────────┐   └──────────┬───────────┘
 └────────────────────┘     │ ESP32-CAM node  │──►(image)     │
                            │ captures frames  │              ▼
                            └─────────────────┘   ┌──────────────────────┐
                                                  │ Kotlin Android App   │
                                                  │ live charts + history│
                                                  └──────────────────────┘
```

| Folder | Part | Language | Role |
|---|---|---|---|
| `esp32-sensor-node/` | ESP32 sensor node | C++/Arduino | Read sensors, run threshold pre-filter, send data, drive actuators |
| `esp32-cam-node/` | ESP32-CAM node | C++/Arduino | Capture + stream images when a fall is suspected |
| `backend-python/` | Laptop backend | Python | Feature extraction, Random Forest confirm, Firebase upload, alerts |
| `android-app-kotlin/` | Caregiver app | Kotlin | Real-time HR/SpO₂/status charts + fall-history log |

---

## 2. The three-stage detection funnel

A single sensor threshold produces far too many false alarms (sitting down
hard, dropping the device). We reduce false positives with a funnel:

```
   Stage 1: THRESHOLD (on ESP32, fast, cheap)
   ─────────────────────────────────────────
   Impact:  |acceleration magnitude| spikes past THRESHOLD_G
   AND
   Tilt:    orientation change past THRESHOLD_TILT
        │
        │  "fall suspected"  → wake the camera, start ML pipeline
        ▼
   Stage 2: ML CONFIRM (on laptop, accurate)
   ─────────────────────────────────────────
   Random Forest over motion features (signal magnitude area, peak accel,
   post-impact stillness, tilt) + image features (bounding-box aspect ratio,
   centroid height, frame motion). Outputs fall / not-fall.
        │
        │  confirmed fall
        ▼
   Stage 3: 10-SECOND CANCEL WINDOW (human in the loop)
   ─────────────────────────────────────────
   Buzzer + OLED countdown. If the user presses "I'm OK" within 10 s,
   the alert is cancelled (they got up fine). Otherwise:
        → upload vitals + GPS to Firebase
        → trigger caregiver alert
        → SOS LED on
```

Stage 1 keeps the ESP32 responsive and only wakes the expensive stages when
something actually looks like a fall. Stage 2 removes most false positives.
Stage 3 respects user autonomy and avoids alarming caregivers over a stumble.

---

## 3. Quick start

> **No hardware yet? Simulate first.** The sensor node runs in
> [Wokwi](https://wokwi.com) — see `esp32-sensor-node/WOKWI.md` for the wiring
> (`diagram.json`) and how to trigger a fall in the browser. Move to physical
> hardware later without changing the sketch logic.

```bash
# ESP32 nodes: open the .ino files in Arduino IDE / PlatformIO, install the
# libraries listed in each file's header, fill in the TODO credentials, flash.

# Python backend:
cd backend-python
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python train_model.py         # trains Random Forest from data/dataset.csv
python live_inference.py      # runs the live confirm loop

# Android app: open android-app-kotlin/ in Android Studio, add your
# google-services.json, sync Gradle, run.
```

---

## 4. What you still need to fill in

Search the repo for `TODO`. The main ones:

- Wi-Fi SSID / password (ESP32 nodes)
- Firebase project URL + database secret / service-account key
- Sensor pin assignments for your exact wiring
- Your ESP32-CAM model + whether it has PSRAM
- The ML dataset (see `backend-python/data/README.md`)

**Never commit secrets.** `.gitignore` already excludes key files, `.env`, and
`google-services.json`.

---

## 5. Hardware plan & two-embedded-systems note

**Decided: ESP32 + laptop.** The backend runs on a laptop (already owned) rather
than a Raspberry Pi, to avoid extra cost. The two embedded systems are the
**ESP32 sensor node** and the **ESP32-CAM node**; the laptop is only the ML
backend, since the Random Forest can't run on the ESP32. Firebase uses
`firebase-admin` (no Raspberry Pi / Pyrebase needed).

The one thing to confirm with your group/lecturer is that a laptop-as-backend is
acceptable for the two-embedded-systems requirement in the marking rubric — that's
a rubric question, not a code change.
