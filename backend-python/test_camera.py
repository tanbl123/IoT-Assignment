import requests

CAM_URL = "http://10.214.169.191/capture"

try:
    r = requests.get(CAM_URL, timeout=3)

    print("Status:", r.status_code)
    print("Content-Type:", r.headers.get("Content-Type"))
    print("Image size:", len(r.content), "bytes")

    if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
        with open("test_capture.jpg", "wb") as f:
            f.write(r.content)

        print("Saved image as test_capture.jpg")
    else:
        print("Camera responded, but not as image.")

except Exception as e:
    print("Camera test failed:", e)