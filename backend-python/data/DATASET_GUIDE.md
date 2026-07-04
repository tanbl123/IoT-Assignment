# Choosing a training dataset (image + motion)

## Requirement
The lecturer requires the fall classifier to use **both image and motion** data
(vision + accelerometer). A motion-only dataset is **not acceptable**.

**Golden rule when judging any dataset:** it must contain **both camera frames
AND accelerometer data for the same recorded events**. If it only has one
modality, it cannot be used — no matter how convenient.

## What the model needs in the end
`train_model.py` reads `data/dataset.csv`, where each row is the **7 features**
(see `../FEATURES.md`) plus a `label` (1 = fall, 0 = not-fall). A dataset is
turned into that CSV by an *adapter* script that runs the raw
camera + accelerometer data through `feature_extraction.py`.

## Options evaluated (July 2026)

| Dataset | Camera? | Accelerometer? | Meets requirement? | Size / notes |
|---------|---------|----------------|--------------------|--------------|
| **UR Fall Detection (URFD)** | ✅ RGB (+depth) | ✅ yes | ✅ **YES — recommended** | Small: 70 sequences (30 falls + 40 ADLs). Manageable on a laptop. |
| **UP-Fall (HAR-UP)** | ✅ 2 cameras | ✅ yes | ✅ yes, but impractical | **812 GB** full / **171 GB** feature set. Only usable if you download a small subset (per subject/activity/trial). |
| Kaggle sensor-only sets (e.g. `uttejkumarkandagatla/fall-detection-dataset`) | ❌ none | ✅ yes | ❌ NO (no images) | Small CSV, but vision missing. |
| Kaggle `pragyachandak/upfalldataset` (UP-Fall CSV copy) | ❌ none | ✅ yes (5 IMUs) | ❌ NO (no images) | **Checked July 2026:** 47 columns, all numeric sensors (Ankle/Belt/Wrist accelerometers, angular velocity, luminosity, brain, 6× infrared) + Subject/Activity/Trial/Tag. Camera image ZIPs were stripped out — sensor-only. |
| Kaggle "Multiple Cameras Fall Dataset" | ✅ video | ❌ none | ❌ NO (no accelerometer) | Vision only. |
| Collect our own (ESP32 + ESP32-CAM / laptop webcam) | ✅ | ✅ | ✅ yes | Most authentic; needs hardware + time. A good stretch/supplement. |

### Note on `kagglehub`
`kagglehub` is a *download tool* (a Python library), **not a dataset**. It only
helps pull datasets that are hosted on Kaggle; it does not provide UP-Fall's
images.

## Decision
- **Primary: URFD** — the practical dataset that satisfies image + motion.
- **Fallback / more data: UP-Fall** — only a small downloaded subset, not the
  full 812 GB.
- **Stretch: self-collected** — once the ESP32 + ESP32-CAM hardware is available.

## Official sources
- URFD: <https://fenix.ur.edu.pl/~mkepski/ds/uf.html>
- UP-Fall (HAR-UP): <https://sites.google.com/up.edu.mx/har-up/>
- HAR-UP processing code: <https://github.com/jpnm561/HAR-UP>

## Honest limitations to state in the report
- The dataset's cameras differ from our ESP32-CAM (angle, resolution), so the
  image features come from a different camera domain. Acceptable for a
  proof-of-concept; for deployment we would fine-tune on ESP32-CAM footage.
- For the live demo without an ESP32-CAM, a **laptop webcam** can act as the
  camera source (`live_inference.py` already pulls frames).

## Next step
Once a dataset (or a subset) is downloaded, note its **folder/file structure**
(where the image frames are, and the accelerometer file + its columns). Then we
write an adapter — e.g. `build_dataset_urfd.py` — that produces `data/dataset.csv`.
