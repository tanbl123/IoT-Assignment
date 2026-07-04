# CLAUDE.md — Project context for Claude Code

Read this first. It captures the course requirements and hardware reality that
should shape every change to this repo. When a choice exists, prefer what the
course actually teaches and what the student can demo in the lab.

## What this project is

Smart Elderly Fall Detection System (IoT + ML) — a university assignment for
**BMIT2123 Internet of Things**. The assignment is worth 50% of coursework and
is assessed by a **demonstration/presentation** (long semester: prepare weeks
8–12, present weeks 13–14). So everything must be *demonstrable on the course's
lab hardware*, not just theoretically correct.

## Course hardware & stack (align to this)

The course teaches and provides these — prefer them over exotic alternatives:

- **Embedded controllers:**
  - **NodeMCU ESP32** programmed in the **Arduino IDE** (C++). Used for sensors
    and MQTT clients (PubSubClient library).
  - **Raspberry Pi (3/4/5)** programmed in **Python** via the **Thonny IDE**.
- **Sensor/actuator interface:** **GrovePi+** board or **Grove Base HAT**, with
  **Grove** sensors/modules (DHT, light, ultrasonic, PIR, buzzer, relay, LCD,
  OLED, RFID, servo, button, etc.). Grove talks I2C/Digital/Analog/PWM/UART.
- **Cloud:** **Firebase Realtime Database**, accessed from the Raspberry Pi in
  Python via **Pyrebase / Pyrebase4** (NOT firebase-admin — the labs use Pyrebase).
- **Messaging:** **MQTT** (Mosquitto broker, `paho-mqtt` on the Pi,
  `PubSubClient` on the ESP32) and **Node-RED** for flow dashboards.
- **Vision:** a **webcam** practical exists (Practical 9), so a USB webcam on the
  Pi is a course-supported alternative to the ESP32-CAM.

## Design decision — DECIDED: ESP32 + laptop

**The demo runs on ESP32 + a laptop Python backend + a Kotlin app.** The student
already owns a laptop; a Raspberry Pi would cost extra money, so the Pi option
was declined. Treat this as settled — do not re-open it or migrate the backend
to a Pi unless the user explicitly changes their mind.

Consequences of this decision (keep the scaffold aligned to it):

1. **Two-embedded-systems requirement:** this is satisfied by **ESP32 sensor
   node + ESP32-CAM** as the two embedded systems, with the laptop acting purely
   as the ML/backend host (the Random Forest can't run on the ESP32). Confirm
   with the group/lecturer that a laptop-as-backend is acceptable for the marking
   rubric — that's the only open point, and it's a rubric question, not a code one.
2. **Firebase library:** keep **`firebase-admin`** (already in the scaffold and
   `requirements.txt`). Pyrebase4 was only relevant for a Pi backend, so it is
   not needed here.

_For future reference only:_ the course also teaches a Raspberry Pi + Pyrebase
path. It is intentionally NOT used here. Ignore Pi/Pyrebase alternatives unless
the hardware plan changes.

## Alternatives already supported by the course (offer these)

- **Caregiver UI:** a **Node-RED dashboard** is a course-taught, faster-to-demo
  alternative to the Kotlin Android app. Keep the Kotlin app as the "stretch"
  deliverable; a Node-RED dashboard may be the safer demo.
- **Image capture:** a **USB webcam on the Pi** (Practical 9) can replace the
  ESP32-CAM if the camera module is troublesome.
- **Node-to-node messaging:** use **MQTT** (Mosquitto) between the ESP32 and the
  Pi rather than raw sockets — it's what the course teaches and grades.

## Repo structure

```
esp32-sensor-node/     ESP32 (Arduino/C++): sensors + threshold pre-filter + actuators
esp32-cam-node/        ESP32-CAM (or swap for Pi + USB webcam)
backend-python/        Feature extraction, Random Forest, live inference, Firebase
android-app-kotlin/    Caregiver app (or Node-RED dashboard alternative)
```

## Detection design (keep intact)

Three-stage funnel — do not collapse it:
1. **Threshold** on the ESP32 (impact + tilt) → "fall suspected".
2. **ML confirm** (Random Forest over motion + image features) on the Pi/laptop.
3. **10-second cancel window** (buzzer + OLED countdown, "I'm OK" button) before
   any alert fires — respects user autonomy, cuts false alarms.

## Coding rules

- **Never hardcode secrets.** Wi-Fi SSID/password, Firebase keys, and pin numbers
  stay as clearly-marked `TODO` placeholders. `.gitignore` already excludes
  `.env`, `serviceAccountKey.json`, `google-services.json`, `secrets.h`.
- Keep ESP32 sketches **Wokwi-compatible where possible** (MPU6050 / OLED /
  buzzer / LED) so they can be simulated before hardware is available.
- Keep the ML **honest**: the training script ships with synthetic placeholder
  data. Do not report accuracy from synthetic data — swap in a real dataset
  (UP-Fall, SisFall, or self-collected) via `backend-python/data/dataset.csv`.
- Commit in small, logical steps with clear messages. Build incrementally: repo
  + README first, then ESP32 sensor node, then the Python backend, then the UI.

## Firebase data model (shared contract)

```
telemetry/latest : { hr, spo2, status, ts }              # live charts
alert            : { hr, spo2, lat, lng, ts, status }     # caregiver alert flag
falls/<pushId>   : { hr, spo2, lat, lng, ts, status }     # history log
```
Keep the ESP32, backend, and UI consistent with this shape.
