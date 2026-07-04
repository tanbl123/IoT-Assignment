"""
Feature extraction for the fall-detection Random Forest.

Two feature groups, matching the project spec:
  MOTION (from the ESP32 sensor node window around the impact):
      - signal magnitude area (SMA)
      - peak acceleration
      - tilt change
      - post-impact stillness
  IMAGE (from the ESP32-CAM frames):
      - bounding-box aspect ratio (a fallen person is wide, not tall)
      - centroid height (fallen person's centroid sits low in the frame)
      - frame motion (sudden motion then stillness)

Both groups are concatenated into a single feature vector. Keep the ORDER in
FEATURE_NAMES identical between training and live inference.
"""

from __future__ import annotations
import numpy as np

try:
    import cv2
except ImportError:      # image features optional if you start motion-only
    cv2 = None

FEATURE_NAMES = [
    "sma", "peak_accel", "tilt_change", "stillness",       # motion
    "bbox_aspect_ratio", "centroid_height", "frame_motion" # image
]


# ------------------------- MOTION FEATURES -------------------------
def motion_features(accel_window: np.ndarray, tilt_window: np.ndarray) -> dict:
    """
    accel_window: shape (N, 3) of x,y,z acceleration in g over a short window.
    tilt_window:  shape (N,)   of tilt angle (deg) over the same window.
    """
    accel_window = np.asarray(accel_window, dtype=float).reshape(-1, 3)
    tilt_window = np.asarray(tilt_window, dtype=float).ravel()

    mag = np.linalg.norm(accel_window, axis=1)                 # per-sample magnitude
    sma = float(np.sum(np.abs(accel_window)) / len(accel_window))
    peak_accel = float(np.max(mag))
    tilt_change = float(np.max(tilt_window) - np.min(tilt_window))

    # post-impact stillness: variance of the last third of the window
    tail = mag[len(mag) * 2 // 3:]
    stillness = float(1.0 / (1.0 + np.var(tail)))              # high = very still

    return {"sma": sma, "peak_accel": peak_accel,
            "tilt_change": tilt_change, "stillness": stillness}


# ------------------------- IMAGE FEATURES --------------------------
def image_features(frames: list) -> dict:
    """
    frames: list of BGR images (np.ndarray) captured around the suspected fall.
    Returns zeros if OpenCV is unavailable or no person is segmented, so the
    pipeline still runs motion-only.
    """
    default = {"bbox_aspect_ratio": 0.0, "centroid_height": 0.0, "frame_motion": 0.0}
    if cv2 is None or not frames:
        return default

    # --- crude foreground person estimate via frame differencing ---
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    diffs = [cv2.absdiff(grays[i], grays[i - 1]) for i in range(1, len(grays))]
    frame_motion = float(np.mean([d.mean() for d in diffs])) if diffs else 0.0

    # bounding box of the largest motion blob in the last diff
    if diffs:
        _, thresh = cv2.threshold(diffs[-1], 25, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(c)
            H = grays[-1].shape[0]
            aspect = float(w / h) if h else 0.0            # >1 = wider than tall = fallen
            centroid_y = float((y + h / 2) / H)            # 1.0 = bottom of frame
            return {"bbox_aspect_ratio": aspect,
                    "centroid_height": centroid_y,
                    "frame_motion": frame_motion}
    return {**default, "frame_motion": frame_motion}


def build_feature_vector(accel_window, tilt_window, frames=None) -> np.ndarray:
    """Concatenate motion + image features in FEATURE_NAMES order."""
    m = motion_features(accel_window, tilt_window)
    im = image_features(frames or [])
    combined = {**m, **im}
    return np.array([combined[name] for name in FEATURE_NAMES], dtype=float)
