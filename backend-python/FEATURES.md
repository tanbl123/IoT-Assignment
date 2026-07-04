# The 7 features — what the Random Forest looks at

The fall classifier does **not** read raw sensor values. Instead,
`feature_extraction.py` converts ~2 seconds of accelerometer readings and a
short burst of camera frames into **7 meaningful numbers (features)**. Those 7
numbers are the input to the Random Forest.

The features fall into **2 groups**:

- **Motion (4 features)** — from the ESP32's MPU6050 accelerometer/gyroscope.
- **Image (3 features)** — from the ESP32-CAM frames.

> ⚠️ "Motion" and "image" are the two **categories**, not the features
> themselves. There are 7 individual features in total. One number per category
> would not be enough to tell a real fall from a fall-like action (e.g. sitting
> down hard), because each feature captures a *different* characteristic.

The order below is fixed in `FEATURE_NAMES` and **must stay identical** between
training (`train_model.py`) and live inference (`live_inference.py`), or the
model would read the wrong value for each slot.

---

## Motion features (from the accelerometer)

| # | Feature | What it measures | Why it helps detect a fall |
|---|---------|------------------|-----------------------------|
| 1 | `sma` (Signal Magnitude Area) | Total movement energy over the window | A fall involves a lot of movement; sitting still involves very little |
| 2 | `peak_accel` | The single largest acceleration spike | This is **the impact** — the moment of hitting the ground |
| 3 | `tilt_change` | How much the body's orientation changed (max − min tilt) | Standing → lying flat is a huge change. **Separates a real fall from a hard sit-down**, which has impact but little tilt change |
| 4 | `stillness` | How motionless the person is *after* the impact | After a real fall a person often lies still; after a stumble they keep moving (recovering). High value = very still |

**How `stillness` is computed:** it looks at the variance of the *last third* of
the window (the moments after impact) and applies `1 / (1 + variance)`.
Motionless → variance ≈ 0 → stillness ≈ 1.0. Still moving → high variance →
stillness near 0.

---

## Image features (from the camera)

| # | Feature | What it measures | Why it helps detect a fall |
|---|---------|------------------|-----------------------------|
| 5 | `bbox_aspect_ratio` | Width ÷ height of the person's bounding box | Standing = tall & narrow (ratio **< 1**); fallen = wide & short (ratio **> 1**) |
| 6 | `centroid_height` | Vertical position of the person in the frame (0 = top, 1 = bottom) | A fallen person's body sits **low** in the frame (near 1.0) |
| 7 | `frame_motion` | Amount of movement the camera saw between frames | A fall = a sudden burst of motion (then stillness) |

**How the image features are found:** consecutive frames are converted to
grayscale and subtracted (frame differencing) to isolate what moved. The largest
moving blob is assumed to be the person; a bounding box around it gives its
shape (`bbox_aspect_ratio`) and position (`centroid_height`). The average of the
frame differences gives `frame_motion`.

> If the camera is unavailable, all 3 image features return **0.0** and the
> system runs **motion-only** — it still works, just with less information.

---

## Worked example — why more features matter

A **hard sit-down** (a common false alarm) crosses the ESP32's Stage-1 threshold
but is **not** a fall. Here is roughly how the two look:

| Feature | Real fall | Hard sit-down |
|---------|-----------|----------------|
| `peak_accel` | high (big impact) | high (also a bump) |
| `tilt_change` | **large** (upright → flat) | **small** (still upright) |
| `stillness` | high (lies still) | low (keeps moving) |
| image features | wide, low, motion | narrow, high, little |

With only "one motion number" the two would look almost identical (both have a
bump). It is the **combination** of features — especially the small
`tilt_change` and the camera showing the person still upright — that lets the
Random Forest correctly **dismiss** the sit-down. This is exactly what the
`live_inference.py --demo` run shows (false alarm dismissed at ~0.35).

---

## Where this fits in the pipeline

```
sensor + camera ──► feature_extraction.py ──► [7 numbers] ──► Random Forest ──► fall / not-fall
   (raw signals)     (build the features)                     (fall_rf.joblib)
```

- Built by: `feature_extraction.build_feature_vector()`
- Trained on: `data/dataset.csv` (columns = these 7 features + a `label`)
- Used live by: `live_inference.py`

## One-sentence summary (for the report / viva)

> We extract **7 features across 2 categories** — 4 motion features from the IMU
> (movement energy, impact peak, orientation change, post-impact stillness) and
> 3 image features from the camera (body shape, position in frame, and motion) —
> so the Random Forest can separate real falls from fall-like activities such as
> sitting down quickly.
