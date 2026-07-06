"""
Adapter: UP-Fall (HAR-UP) raw downloads  ->  data/dataset.csv

Turns the UP-Fall per-trial downloads into the 7-feature training file that
`train_model.py` expects, using your existing `feature_extraction.py`. This is
the "image + motion" pipeline your lecturer requires:

  * MOTION  <- the "DataSet" CSV (belt accelerometer, columns 16-18)
  * IMAGE   <- the "Camera1" zip (RGB frames, named by timestamp)

For each trial it slides a ~2 s window over the sensor rows, pulls the camera
frames whose timestamps fall inside that window, computes the 7 features, and
labels the window from the UP-Fall **Tag** column (the last column):
  Tag 1-5  = a fall activity      -> label 1
  Tag 6-11 / 20 / other           -> not a fall -> label 0

Using the Tag (per-sample) instead of the folder's Activity number means a
window is only labelled "fall" when it actually contains the fall, not the
standing period before it.

--------------------------------------------------------------------------
USAGE
  1. Put the downloaded files in  data/upfall_raw/ , keeping their names:
        data/upfall_raw/Subject1Activity1Trial1.csv
        data/upfall_raw/Subject1Activity1Trial1Camera1.zip
        data/upfall_raw/Subject1Activity3Trial1.csv
        data/upfall_raw/Subject1Activity3Trial1Camera1.zip
        ... (each CSV paired with its <same-prefix>Camera1.zip)
  2. pip install -r requirements.txt        # needs opencv-python for images
  3. python build_dataset_upfall.py
     -> writes data/dataset.csv
  4. python train_model.py                  # real image+motion accuracy
--------------------------------------------------------------------------
The Camera1 zips are read **directly** (no need to unzip them).
"""

from __future__ import annotations
import os
import re
import glob
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd

from feature_extraction import build_feature_vector, FEATURE_NAMES

try:
    import cv2
except ImportError:
    cv2 = None

# ===================== config =====================
RAW_DIR   = os.path.join("data", "upfall_raw")
OUT_PATH  = os.path.join("data", "dataset.csv")

# UP-Fall "DataSet" CSV layout (0-indexed columns), 2 header rows then data:
TS_COL        = 0                 # timestamp, e.g. 2018-07-04T12:04:17.738369
BELT_ACC_COLS = [15, 16, 17]      # belt accelerometer x, y, z (in g)
HEADER_ROWS   = 2                 # row 1 = names, row 2 = units

FALL_TAGS   = {1, 2, 3, 4, 5}     # UP-Fall tags that are falls
WINDOW      = 40                  # samples per window (~2 s at ~20 Hz)
STEP        = 20                  # hop between windows (~1 s, 50% overlap)
FRAMES_PER_WINDOW = 6             # camera frames sampled per window
FALL_FRACTION = 0.5              # >= this share of fall-tagged samples => fall
# ==================================================


def parse_ts(s: str) -> datetime:
    """Parse an UP-Fall timestamp string to datetime."""
    return datetime.strptime(s.strip(), "%Y-%m-%dT%H:%M:%S.%f")


def load_trial_csv(path):
    """Return (timestamps[list[datetime]], accel[N,3] g, tags[N] int)."""
    df = pd.read_csv(path, header=None, skiprows=HEADER_ROWS,
                     dtype=str, low_memory=False)
    df = df.dropna(how="all")
    ts = [parse_ts(v) for v in df.iloc[:, TS_COL]]
    accel = df.iloc[:, BELT_ACC_COLS].astype(float).to_numpy()
    # Tag is the last column in the synchronized DataSet file.
    try:
        tags = df.iloc[:, -1].astype(float).astype(int).to_numpy()
    except ValueError:
        tags = np.full(len(df), -1)   # no usable tag column
    return ts, accel, tags


def index_camera_zip(zip_path):
    """Map each frame's timestamp -> member name inside the Camera zip."""
    index = {}
    if not os.path.exists(zip_path):
        return None
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            base = os.path.basename(name)
            if not base.lower().endswith(".png"):
                continue
            stem = base[:-4]                     # drop ".png"
            # filename uses '_' where the timestamp has ':'
            try:
                ts = parse_ts(stem.replace("_", ":"))
            except ValueError:
                continue
            index[ts] = name
    return index


def load_frames(zip_path, cam_index, window_ts):
    """Load up to FRAMES_PER_WINDOW frames whose timestamps fall in the window."""
    if cv2 is None or not cam_index:
        return []
    t0, t1 = window_ts[0], window_ts[-1]
    names = [cam_index[t] for t in cam_index if t0 <= t <= t1]
    if not names:
        return []
    # sample evenly across the window
    if len(names) > FRAMES_PER_WINDOW:
        idx = np.linspace(0, len(names) - 1, FRAMES_PER_WINDOW).astype(int)
        names = [sorted(names)[i] for i in idx]
    frames = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in names:
            arr = np.frombuffer(zf.read(name), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                frames.append(img)
    return frames


def tilt_from_accel(accel):
    """Per-sample tilt angle (deg) from accelerometer x,y,z, like the ESP32."""
    ax, ay, az = accel[:, 0], accel[:, 1], accel[:, 2]
    return np.degrees(np.arctan2(np.sqrt(ax * ax + ay * ay), az))


def process_trial(csv_path):
    """Yield (feature_vector, label) rows for one trial."""
    prefix = os.path.basename(csv_path)[:-4]              # strip ".csv"
    zip_path = os.path.join(os.path.dirname(csv_path), prefix + "Camera1.zip")
    ts, accel, tags = load_trial_csv(csv_path)
    cam_index = index_camera_zip(zip_path)

    if cam_index is None:
        print(f"  [warn] no Camera1 zip for {prefix} -> motion-only for this trial")
    elif cv2 is None:
        print("  [warn] opencv not installed -> image features = 0 "
              "(pip install opencv-python)")

    tilt = tilt_from_accel(accel)
    n = len(ts)
    n_fall = n_adl = 0
    for start in range(0, max(0, n - WINDOW + 1), STEP):
        sl = slice(start, start + WINDOW)
        w_tags = tags[sl]
        frac_fall = np.mean([t in FALL_TAGS for t in w_tags]) if len(w_tags) else 0
        label = 1 if frac_fall >= FALL_FRACTION else 0

        frames = load_frames(zip_path, cam_index, ts[sl]) if cam_index else []
        fv = build_feature_vector(accel[sl], tilt[sl], frames)
        if label:
            n_fall += 1
        else:
            n_adl += 1
        # `prefix` (SubjectXActivityYTrialZ) groups windows from the same
        # recording so evaluation can keep them out of train+test at once.
        yield fv, label, prefix
    print(f"  {prefix}: {n_fall} fall + {n_adl} not-fall windows")


def main():
    if cv2 is None:
        print("[warning] opencv-python not installed. Image features will be 0. "
              "Run: pip install opencv-python  (required for image + motion).")

    csvs = sorted(p for p in glob.glob(os.path.join(RAW_DIR, "*.csv"))
                  if "Camera" not in os.path.basename(p))
    if not csvs:
        print(f"No trial CSVs found in {RAW_DIR}/. "
              f"Download UP-Fall DataSet + Camera1 files there first.")
        return

    print(f"Building dataset from {len(csvs)} trial(s) in {RAW_DIR}/ ...")
    rows, labels, groups = [], [], []
    for csv_path in csvs:
        for fv, label, group in process_trial(csv_path):
            rows.append(fv)
            labels.append(label)
            groups.append(group)

    if not rows:
        print("No windows produced — check the files.")
        return

    df = pd.DataFrame(rows, columns=FEATURE_NAMES)
    df["label"] = labels
    df["group"] = groups          # recording id, for leakage-free evaluation
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    n_fall = int(sum(labels))
    print(f"\nWrote {len(df)} rows -> {OUT_PATH}")
    print(f"  falls: {n_fall}   not-falls: {len(df) - n_fall}")
    if n_fall == 0 or n_fall == len(df):
        print("  [warning] only one class present — add more trials of the "
              "other type before training.")
    print("Next: python train_model.py")


if __name__ == "__main__":
    main()
