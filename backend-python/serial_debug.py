import serial

SERIAL_PORT = "COM7"
BAUD = 115200

ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)

print(f"Reading from {SERIAL_PORT}...")
print("Press Ctrl+C to stop.\n")

while True:
    raw = ser.readline().decode(errors="replace").strip()

    if raw:
        print("RAW:", raw)