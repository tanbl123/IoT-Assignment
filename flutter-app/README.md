# Caregiver App (Flutter) — Smart Elderly Fall Detection

The **User Interface + Reports module** of the fall-detection system. It reads
the same Firebase Realtime Database the Python backend writes to and shows:

| Tab | What it shows | Firebase source |
|-----|---------------|-----------------|
| **Live** | Current HR / SpO2, last-updated time, red "FALL DETECTED" banner with an *Acknowledge* button | `telemetry/latest`, `state/alert` |
| **Falls** | Log of every confirmed fall (time, vitals, GPS) | `fall_events/<pushId>` |
| **Reports** | Avg HR/SpO2, HR & SpO2 line charts over time, falls-per-day bar chart | `all_records/<pushId>`, `fall_events/<pushId>` |

> The Reports tab is the assignment's *"generate an analysis report from the
> collected data"* deliverable. It needs **historical** data. `telemetry/latest`
> is overwritten on every reading and can't be graphed over time, so the backend
> also appends each reading to `all_records` (every few seconds) — that
> append-only log is what the charts read.

---

## Firebase data model (shared contract)

The app and `backend-python/firebase_client.py` agree on this shape:

```
telemetry/latest        : { hr, spo2, status, accel_g, tilt, lat, lng, ts }  # live tile (overwritten)
all_records/<pushId>    : { record_type, hr, spo2, ts, ... }   # every reading — history/time-series for charts
all_records_latest      : { ...last record... }
fall_events/<pushId>    : { hr, spo2, lat, lng, ts, status }   # confirmed falls -> Falls tab + report counts
state/alert             : true|false                           # drives the red banner
state/confirmed         : true|false
state/latestFall        : { ...last fall... }
```

`record_type` is one of `NORMAL_TELEMETRY`, `FALL_DETECTION_RESULT`, or
`FALL_CONFIRMED`. The charts read every `all_records` row (they all carry
`hr`/`spo2`/`ts`); the Falls tab reads `fall_events`. `ts` is Unix **seconds**.

---

## One-time setup

You need the Flutter SDK installed (`flutter --version`). Then:

```bash
cd flutter-app

# 1. Install the FlutterFire CLI (once per machine)
dart pub global activate flutterfire_cli

# 2. Connect this app to YOUR Firebase project.
#    Pick the SAME project the Python backend uses.
#    This generates lib/firebase_options.dart and the platform config files.
flutterfire configure

# 3. Tell the app which Realtime Database to read:
#    open lib/config.dart and set kDatabaseUrl to your RTDB URL,
#    e.g. https://smart-fall-detection-default-rtdb.firebaseio.com
#    (must match FIREBASE_DB_URL in backend-python/firebase_client.py)

# 4. Get packages and run (phone/emulator plugged in)
flutter pub get
flutter run
```

`lib/firebase_options.dart` ships as a **placeholder** that throws a friendly
"run flutterfire configure" message — so the project compiles on a fresh clone
but reminds you to configure it before running.

---

## How the data gets there (end-to-end)

```
ESP32 sensor ──serial──► live_inference.py ──► Firebase RTDB ──► THIS APP
   (HR, SpO2,             (Random Forest             │
    fall_suspected)        confirms fall)            ├─ telemetry/latest    (every reading)
                                                     ├─ all_records/<id>    (every few s)  ← charts
                                                     ├─ fall_events/<id>    (on confirmed fall)
                                                     └─ state/alert = true  (on confirmed fall)
```

The history throttle is `NORMAL_RECORD_INTERVAL_SECONDS` (default 5 s) in
`backend-python/firebase_client.py`.

### No hardware yet? Seed some demo data

To demo the app before the ESP32 is wired up, add rows straight to the database
(Firebase console → Realtime Database → ⋮ → Import JSON), e.g.:

```json
{
  "telemetry": { "latest": { "hr": 78, "spo2": 97, "status": "OK", "ts": 1690000000 } },
  "all_records": {
    "s1": { "record_type": "NORMAL_TELEMETRY", "hr": 76, "spo2": 98, "status": "OK", "ts": 1690000000 },
    "s2": { "record_type": "NORMAL_TELEMETRY", "hr": 81, "spo2": 97, "status": "OK", "ts": 1690000600 },
    "s3": { "record_type": "NORMAL_TELEMETRY", "hr": 120, "spo2": 92, "status": "OK", "ts": 1690001200 }
  },
  "fall_events": {
    "f1": { "hr": 120, "spo2": 92, "lat": 3.2159, "lng": 101.7290, "ts": 1690001200, "status": "FALL_CONFIRMED" }
  }
}
```

⚠️ **Import replaces the whole database.** To keep your existing data, add these
nodes by hand instead, or export first. The charts and history list will
populate immediately once the rows exist.

---

## Project layout

```
flutter-app/
  pubspec.yaml                 firebase_core, firebase_database, fl_chart, intl
  lib/
    main.dart                  Firebase init + bottom-nav shell
    config.dart                kDatabaseUrl  (TODO: your RTDB URL)
    firebase_options.dart      placeholder — flutterfire configure overwrites it
    models/
      vitals.dart              telemetry/latest + history/vitals row
      fall_event.dart          falls/<pushId> row
    services/
      database_service.dart    all Firebase reads/writes live here
    screens/
      home_screen.dart         Live tab
      history_screen.dart      Falls tab
      analytics_screen.dart    Reports tab (fl_chart)
```

## Notes

- **Can't build here:** this folder was scaffolded on the web; Flutter is
  compiled on your own machine with the steps above.
- Keep the Firebase shape in sync with `backend-python/firebase_client.py`. If
  you rename a node in one place, rename it in the other.
