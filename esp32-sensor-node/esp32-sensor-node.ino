/*
 * Smart Elderly Fall Detection — ESP32 Sensor Node
 * ------------------------------------------------
 * Reads:   MPU6050 (accel + gyro), MAX30102 (HR + SpO2), NEO-6M (GPS)
 * Does:    Stage-1 threshold pre-filter (impact + tilt), then streams data to
 *          the Python backend and drives actuators (buzzer, vib motor, OLED, SOS LED).
 *
 * Libraries to install (Arduino Library Manager):
 *   - Adafruit MPU6050 + Adafruit Unified Sensor
 *   - SparkFun MAX3010x Sensor Library      (heart rate / SpO2)
 *   - TinyGPSPlus                            (NEO-6M parsing)
 *   - Adafruit SSD1306 + Adafruit GFX        (OLED)
 *   - ArduinoJson                            (packet formatting)
 *
 * Communication: this template sends JSON lines over Serial. Swap sendPacket()
 * for WiFi (HTTP/WebSocket) or BluetoothSerial once your transport is decided.
 *
 * Wokwi-friendly: MPU6050 + OLED + buzzer/LED simulate well. MAX30102/GPS do not,
 * so those reads are guarded so the sketch still compiles & runs in simulation.
 */

#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_SSD1306.h>
#include <TinyGPSPlus.h>
// #include "MAX30105.h"          // TODO: uncomment when MAX30102 wired
// #include "spo2_algorithm.h"

// ===================== TODO: pins & config =====================
#define PIN_BUZZER      25   // TODO: your buzzer pin
#define PIN_VIB_MOTOR   26   // TODO: vibration motor
#define PIN_SOS_LED     27   // TODO: SOS LED
#define PIN_OK_BUTTON   14   // "I'm OK" cancel button (active LOW)
#define PIN_GPS_RX      16   // ESP32 RX  <- GPS TX
#define PIN_GPS_TX      17   // ESP32 TX  -> GPS RX
#define OLED_WIDTH      128
#define OLED_HEIGHT     64
#define OLED_ADDR       0x3C

// ---- Stage-1 threshold tuning (calibrate on your device) ----
const float THRESHOLD_G      = 2.5;   // impact: accel magnitude in g
const float THRESHOLD_TILT   = 60.0;  // tilt change in degrees
const uint32_t CANCEL_MS     = 10000; // Stage-3 cancel window (10 s)
// ===============================================================

Adafruit_MPU6050 mpu;
Adafruit_SSD1306 oled(OLED_WIDTH, OLED_HEIGHT, &Wire, -1);
TinyGPSPlus gps;
HardwareSerial GPSserial(2);   // UART2 for NEO-6M

float baselineTilt = 0.0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_VIB_MOTOR, OUTPUT);
  pinMode(PIN_SOS_LED, OUTPUT);
  pinMode(PIN_OK_BUTTON, INPUT_PULLUP);

  Wire.begin();
  if (!mpu.begin()) { Serial.println("MPU6050 not found"); }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);

  if (oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    oled.clearDisplay(); oled.setTextSize(1); oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(0, 0); oled.println("Fall Detector Ready"); oled.display();
  }

  GPSserial.begin(9600, SERIAL_8N1, PIN_GPS_RX, PIN_GPS_TX);
  // TODO: MAX30102 particleSensor.begin(); configure sample rate here.

  baselineTilt = readTilt();   // assume upright/still at boot
}

// Accel magnitude in g (1 g = 9.81 m/s^2)
float readAccelMagnitudeG() {
  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);
  float ax = a.acceleration.x, ay = a.acceleration.y, az = a.acceleration.z;
  return sqrt(ax*ax + ay*ay + az*az) / 9.81;
}

// Tilt angle of the device from vertical, degrees
float readTilt() {
  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);
  float ax = a.acceleration.x, ay = a.acceleration.y, az = a.acceleration.z;
  return atan2(sqrt(ax*ax + ay*ay), az) * 180.0 / PI;
}

// TODO: implement real HR/SpO2 read; placeholders keep the packet shape stable.
int   readHeartRate() { return -1; }   // -1 = not available
float readSpO2()      { return -1; }

void feedGPS() { while (GPSserial.available()) gps.encode(GPSserial.read()); }

// Stage 1: impact + tilt gate
bool fallSuspected() {
  float g    = readAccelMagnitudeG();
  float tilt = readTilt();
  bool impact = g > THRESHOLD_G;
  bool tilted = fabs(tilt - baselineTilt) > THRESHOLD_TILT;
  return impact && tilted;
}

// Stage 3: buzz + OLED countdown; returns true if user cancelled
bool cancelWindow() {
  uint32_t start = millis();
  while (millis() - start < CANCEL_MS) {
    digitalWrite(PIN_BUZZER, HIGH);
    digitalWrite(PIN_VIB_MOTOR, HIGH);
    int remaining = (CANCEL_MS - (millis() - start)) / 1000;
    oled.clearDisplay(); oled.setCursor(0, 0);
    oled.println("FALL DETECTED"); oled.print("Press OK: "); oled.print(remaining); oled.println("s");
    oled.display();
    if (digitalRead(PIN_OK_BUTTON) == LOW) {   // user is fine
      digitalWrite(PIN_BUZZER, LOW); digitalWrite(PIN_VIB_MOTOR, LOW);
      return true;
    }
    delay(100);
  }
  digitalWrite(PIN_BUZZER, LOW); digitalWrite(PIN_VIB_MOTOR, LOW);
  return false;
}

// Send one JSON line to the backend. TODO: replace Serial with WiFi/BT transport.
void sendPacket(bool suspected) {
  feedGPS();
  StaticJsonDocument<256> doc;
  doc["type"]     = suspected ? "fall_suspected" : "telemetry";
  doc["accel_g"]  = readAccelMagnitudeG();
  doc["tilt"]     = readTilt();
  doc["hr"]       = readHeartRate();
  doc["spo2"]     = readSpO2();
  doc["lat"]      = gps.location.isValid() ? gps.location.lat() : 0.0;
  doc["lng"]      = gps.location.isValid() ? gps.location.lng() : 0.0;
  doc["ts"]       = millis();
  serializeJson(doc, Serial);
  Serial.println();
}

void loop() {
  feedGPS();

  if (fallSuspected()) {
    sendPacket(true);            // wake camera + ML pipeline on the laptop
    bool cancelled = cancelWindow();
    if (!cancelled) {
      digitalWrite(PIN_SOS_LED, HIGH);
      // Backend handles Firebase upload + caregiver alert on the confirmed fall.
      // TODO: optionally wait for backend ACK before clearing SOS.
    }
    delay(2000);                 // debounce so one fall isn't reported repeatedly
    digitalWrite(PIN_SOS_LED, LOW);
    oled.clearDisplay(); oled.setCursor(0,0); oled.println("Monitoring..."); oled.display();
  } else {
    sendPacket(false);           // routine telemetry for live charts
    delay(200);                  // ~5 Hz; raise sample rate for better ML features
  }
}
