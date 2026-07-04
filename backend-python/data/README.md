# Dataset

`train_model.py` expects **`data/dataset.csv`** with these columns:

```
sma, peak_accel, tilt_change, stillness, bbox_aspect_ratio, centroid_height, frame_motion, label
```

`label`: `1` = fall, `0` = not-fall. The 7 feature columns must match
`feature_extraction.FEATURE_NAMES` in order.

## Where to get data (ML approach undecided)

**Option A — Public dataset (fastest).**
The UP-Fall Detection Dataset is a common academic choice (wearable IMU + vision,
multiple subjects and activities). Write a small adapter that reads its raw
accelerometer windows (and, if you use vision, its camera frames), runs them
through `feature_extraction.build_feature_vector()`, and writes `dataset.csv`.
Other options: SisFall, MobiFall.

**Option B — Collect your own.**
Log windowed samples from your ESP32 while performing scripted falls and
non-falls (sit, walk, lie down, drop device), label each window, and export to
`dataset.csv`. More work, but matches your exact hardware best.

Until you add real data, `train_model.py` generates a small **synthetic** sample
(`data/sample.csv`) so the pipeline runs end-to-end. Do **not** report accuracy
from synthetic data — swap in real data first.

> Raw dataset files are gitignored (they're large). Keep `dataset.csv` local.
