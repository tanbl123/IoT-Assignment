"""
Feature extraction for the fall-detection Random Forest.

Motion features:
- signal magnitude area
- peak acceleration
- tilt change
- post-impact stillness

Image features from ESP32-CAM:
- bounding-box aspect ratio
- centroid height
- frame motion

Keep FEATURE_NAMES order identical between training and live inference.
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


FEATURE_NAMES = [
    "sma",
    "peak_accel",
    "tilt_change",
    "stillness",
    "bbox_aspect_ratio",
    "centroid_height",
    "frame_motion",
]


def motion_features(accel_window: np.ndarray, tilt_window: np.ndarray) -> dict:
    """
    Extract motion features from ESP32 sensor readings.

    accel_window:
        Shape (N, 3), x/y/z acceleration values in g.

    tilt_window:
        Shape (N,), tilt angle values in degrees.
    """
    accel_window = np.asarray(accel_window, dtype=float).reshape(-1, 3)
    tilt_window = np.asarray(tilt_window, dtype=float).ravel()

    if len(accel_window) == 0 or len(tilt_window) == 0:
        return {
            "sma": 0.0,
            "peak_accel": 0.0,
            "tilt_change": 0.0,
            "stillness": 0.0,
        }

    mag = np.linalg.norm(accel_window, axis=1)

    sma = float(np.sum(np.abs(accel_window)) / len(accel_window))
    peak_accel = float(np.max(mag))
    tilt_change = float(np.max(tilt_window) - np.min(tilt_window))

    tail = mag[len(mag) * 2 // 3:]
    stillness = float(1.0 / (1.0 + np.var(tail)))

    return {
        "sma": sma,
        "peak_accel": peak_accel,
        "tilt_change": tilt_change,
        "stillness": stillness,
    }


def image_features(frames: list, save_debug_path: str | None = None) -> dict:
    """
    Extract image features from ESP32-CAM frames.

    Image preprocessing steps:
    1. Convert frames to grayscale.
    2. Apply Gaussian blur to reduce noise.
    3. Use frame differencing to detect movement.
    4. Apply thresholding.
    5. Use morphology to clean noise.
    6. Find the largest motion contour.
    7. Calculate bounding-box aspect ratio, centroid height, and frame motion.
    8. Save processed_detection.jpg if save_debug_path is provided.
    """
    default = {
        "bbox_aspect_ratio": 0.0,
        "centroid_height": 0.0,
        "frame_motion": 0.0,
    }

    if cv2 is None or not frames:
        return default

    grays = []

    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        grays.append(gray)

    diffs = [
        cv2.absdiff(grays[i], grays[i - 1])
        for i in range(1, len(grays))
    ]

    frame_motion = float(np.mean([d.mean() for d in diffs])) if diffs else 0.0

    if not diffs:
        return {
            **default,
            "frame_motion": frame_motion,
        }

    combined_diff = diffs[-1]

    for d in diffs:
        combined_diff = cv2.max(combined_diff, d)

    _, thresh = cv2.threshold(
        combined_diff,
        25,
        255,
        cv2.THRESH_BINARY,
    )

    kernel = np.ones((5, 5), np.uint8)

    thresh = cv2.morphologyEx(
        thresh,
        cv2.MORPH_OPEN,
        kernel,
    )

    thresh = cv2.morphologyEx(
        thresh,
        cv2.MORPH_DILATE,
        kernel,
    )

    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    annotated = frames[-1].copy()

    if not contours:
        if save_debug_path:
            cv2.putText(
                annotated,
                "No strong motion blob detected",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )

            cv2.imwrite(save_debug_path, annotated)

        return {
            **default,
            "frame_motion": frame_motion,
        }

    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)

    image_area = grays[-1].shape[0] * grays[-1].shape[1]
    min_area = max(100, image_area * 0.002)

    if area < min_area:
        if save_debug_path:
            cv2.putText(
                annotated,
                "Motion too small / noise",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
            )

            cv2.imwrite(save_debug_path, annotated)

        return {
            **default,
            "frame_motion": frame_motion,
        }

    x, y, w, h = cv2.boundingRect(c)

    H = grays[-1].shape[0]

    aspect = float(w / h) if h else 0.0
    centroid_y = float((y + h / 2) / H)

    if save_debug_path:
        cv2.rectangle(
            annotated,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2,
        )

        cv2.circle(
            annotated,
            (x + w // 2, y + h // 2),
            5,
            (0, 0, 255),
            -1,
        )

        cv2.putText(
            annotated,
            f"aspect={aspect:.2f}, centroid={centroid_y:.2f}, motion={frame_motion:.2f}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )

        cv2.imwrite(save_debug_path, annotated)

    return {
        "bbox_aspect_ratio": aspect,
        "centroid_height": centroid_y,
        "frame_motion": frame_motion,
    }


def extract_all_features(
    accel_window,
    tilt_window,
    frames=None,
    save_debug_path=None,
) -> dict:
    """
    Extract and combine motion + image features.
    """
    m = motion_features(accel_window, tilt_window)

    im = image_features(
        frames or [],
        save_debug_path=save_debug_path,
    )

    return {
        **m,
        **im,
    }


def build_feature_vector(
    accel_window,
    tilt_window,
    frames=None,
    save_debug_path=None,
) -> np.ndarray:
    """
    Build feature vector in the exact FEATURE_NAMES order.
    """
    combined = extract_all_features(
        accel_window,
        tilt_window,
        frames or [],
        save_debug_path=save_debug_path,
    )

    return np.array(
        [combined[name] for name in FEATURE_NAMES],
        dtype=float,
    )