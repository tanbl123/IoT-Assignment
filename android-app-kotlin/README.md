# Caregiver App (Kotlin)

Real-time dashboard for a caregiver: live heart-rate & SpO₂ charts, current
status, and a fall-history log. Data comes from the same Firebase Realtime
Database the Python backend writes to.

## Data model (matches the backend)

```
telemetry/latest : { hr, spo2, status, ts }     # drives the live charts
alert            : { hr, spo2, lat, lng, ts, status }  # set on a confirmed fall
falls/<pushId>   : { hr, spo2, lat, lng, ts, status }  # history log
```

## Setup

1. Open `android-app-kotlin/` in Android Studio.
2. Firebase console → add an Android app with your package
   `com.example.falldetection` → download **google-services.json** into
   `app/` (it's gitignored — never commit it).
3. Let Gradle sync. Dependencies you'll need in `app/build.gradle`:
   ```gradle
   implementation platform('com.google.firebase:firebase-bom:33.1.0')
   implementation 'com.google.firebase:firebase-database-ktx'
   implementation 'com.github.PhilJay:MPAndroidChart:v3.1.0'   // charts
   ```
   and in the root `build.gradle` / settings, the Google services plugin
   and the JitPack maven repo (for MPAndroidChart).

## Files in this scaffold

- `app/src/main/java/com/example/falldetection/MainActivity.kt`
  — connects to Firebase, listens to `telemetry/latest`, updates the HR chart,
  and shows an alert when `alert` fires. TODOs mark where to extend.
- `app/src/main/res/layout/activity_main.xml`
  — status text, an MPAndroidChart `LineChart`, and a fall-history list area.

This is a starting skeleton — flesh out the SpO₂ chart, history RecyclerView,
and a map link for GPS as you go.
