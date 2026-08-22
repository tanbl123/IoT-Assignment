import os
import glob
import cv2

from feature_extraction import image_features


CAPTURES_DIR = "captures"


def find_latest_fall_event_folder():
    folders = glob.glob(os.path.join(CAPTURES_DIR, "fall_event_*"))

    if not folders:
        raise FileNotFoundError(
            "No fall_event folder found inside captures/. "
            "Run live_inference.py first to capture images."
        )

    latest_folder = max(folders, key=os.path.getmtime)
    return latest_folder


def load_frames(folder):
    image_paths = sorted(glob.glob(os.path.join(folder, "frame_*.jpg")))

    if not image_paths:
        raise FileNotFoundError(
            f"No frame_*.jpg images found in {folder}"
        )

    frames = []

    for path in image_paths:
        img = cv2.imread(path)

        if img is not None:
            frames.append(img)

    if not frames:
        raise ValueError("Images found, but OpenCV could not read them.")

    return frames


def main():
    latest_folder = find_latest_fall_event_folder()

    print(f"[info] using latest folder: {latest_folder}")

    frames = load_frames(latest_folder)

    output_path = os.path.join(
        latest_folder,
        "processed_detection_test.jpg"
    )

    features = image_features(
        frames,
        save_debug_path=output_path,
    )

    print("[image preprocessing result]")
    print(f"bbox_aspect_ratio: {features['bbox_aspect_ratio']:.3f}")
    print(f"centroid_height:   {features['centroid_height']:.3f}")
    print(f"frame_motion:      {features['frame_motion']:.3f}")

    print(f"[saved] {output_path}")


if __name__ == "__main__":
    main()