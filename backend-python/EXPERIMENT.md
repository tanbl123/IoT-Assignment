# Experiment branch: camera-temporal fall detection

**Branch:** `camera-temporal-fall` — isolated from `main` so the working system
is untouched. Merge only if this proves better.

## The problem this tackles
The camera currently grabs frames **after** a fall is suspected, so it only sees
the person **already on the floor** — and *"fell"* vs *"lay down"* look identical
at that point. Result: lying down can be mistaken for a fall.

Key idea (correct, real-world): **a fall is a *process* — a fast descent — while
lying down is slow.** So we add a temporal feature that measures *how fast the
person went down*.

## What changed on this branch
- `feature_extraction.py` — new **`descent_speed`** feature (8th feature) via a
  new `temporal_features()`. It tracks the moving blob's centroid height across
  the frame burst and reports the largest downward jump per frame:
  fast drop → high (fall), slow → low (lie-down), none → 0.
- `evaluate_and_plot.py` — `descent_speed` tagged as an image feature for charts.

Unit test (synthetic frames) confirms it separates the cases:
```
FAST descent (fall)   descent_speed = 0.188
SLOW descent (liedown) descent_speed = 0.033
STILL (no motion)      descent_speed = 0.000   ->  fast > slow > still  ✅
```

## ⚠️ You must rebuild + retrain to test this (raw images needed)
Adding a feature changes the model input from 7 → 8 features, so the committed
`dataset.csv` and `fall_rf.joblib` are out of date on this branch. On your laptop
(where the raw UP-Fall images live):

```bash
# 1. Rebuild dataset.csv WITH the new descent_speed feature (recomputes from frames)
python build_dataset_upfall.py "C:\Users\User\Documents\HAR-UP\DataBaseDownload"

# 2. Retrain + evaluate
python train_model.py
python evaluate_and_plot.py     # or: python app.py
```

### Make it a FAIR test of the lie-down problem
The current download is falls-only, so the model never sees deliberate lying
down. To actually judge whether `descent_speed` fixes the false alarm, **also
download Activity 11 (laying) — and ideally 6/8 (walking/sitting) — as
not-fall examples** into the same folder, then rebuild + retrain. Compare against
`main`:
- Did **precision** go up (fewer false alarms)?
- Did **recall** stay high?

If yes → merge this branch into `main`. If not → discard it; `main` is untouched.

## To use it LIVE on the real ESP32-CAM (after the ML proves out)
Right now `live_inference.py` captures 8 frames *after* the trigger — too late to
see the descent. To feed `descent_speed` live, the laptop must **continuously
buffer frames** (a rolling window of the last ~2 s) so that when a fall is
suspected, the *"standing → going down → landed"* sequence is already captured.
Sketch:

```python
from collections import deque
frame_buffer = deque(maxlen=20)          # ~2 s at 10 fps

# in a background thread, always running:
#   frame_buffer.append(grab_one_frame())

# on fall_suspected: use list(frame_buffer) as the frames for build_feature_vector
```

That's the only live change needed — the feature code already handles the rest.
