# Simulating the sensor node in Wokwi

Run the ESP32 sensor node in your browser — no hardware needed. This lets you
test Stage-1 (impact + tilt threshold) and Stage-3 (10-second cancel window with
the OLED countdown and "I'm OK" button) before the physical parts arrive.

## What's wired in `diagram.json`

| Component            | ESP32 pin | Notes                                  |
|----------------------|-----------|----------------------------------------|
| MPU6050 (accel/gyro) | SDA=21, SCL=22 | I2C — drives Stage-1 fall detection |
| SSD1306 OLED (0x3C)  | SDA=21, SCL=22 | I2C — shows status + cancel countdown |
| Buzzer               | 25        | Sounds during the cancel window        |
| Vibration motor (LED)| 26        | Blue LED stands in for the motor       |
| SOS LED              | 27        | Red LED — turns on for an uncancelled fall |
| "I'm OK" button      | 14        | Active-LOW (INPUT_PULLUP)              |

**Not simulated** (Wokwi has no model for them) — the sketch guards these so it
still runs: **MAX30102** (HR/SpO₂ read as -1) and **NEO-6M GPS** (lat/lng = 0).
You'll test those on real hardware later.

## How to run it

1. Go to <https://wokwi.com>, click **New Project → ESP32**.
2. Open the **`diagram.json`** tab, delete its contents, and paste this folder's
   `diagram.json`.
3. Open the **`sketch.ino`** tab and paste `esp32-sensor-node.ino`.
4. (If the libraries don't auto-load) open the **Library Manager** panel and add
   the entries from `libraries.txt`.
5. Press the green **▶ Play** button to start the simulation.

## How to trigger a fall in the simulation

1. Let it boot — the OLED shows **"Fall Detector Ready"**, then **"Monitoring…"**.
2. Click the **MPU6050** part. A panel lets you set acceleration (X/Y/Z) and
   rotation.
3. To cross Stage-1, push the accelerometer past the impact threshold and tip the
   orientation over: set a large acceleration spike (magnitude > **2.5 g**) **and**
   change the tilt by more than **60°** from the upright boot value.
4. The OLED switches to **"FALL DETECTED — Press OK: 10s"** and the buzzer sounds.
5. **Click the green "I'm OK" button** within 10 s → the alert cancels (buzzer off,
   back to monitoring). **Do nothing** → the countdown ends, the **red SOS LED**
   turns on, and the node reports the fall over Serial (open the Serial Monitor at
   the bottom to see the JSON packets).

> Thresholds live at the top of the sketch (`THRESHOLD_G`, `THRESHOLD_TILT`,
> `CANCEL_MS`). Tune them here in simulation, then keep the same values when you
> move to physical hardware.
