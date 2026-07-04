/*
 * Smart Elderly Fall Detection — ESP32-CAM Node
 * ---------------------------------------------
 * Captures frames and serves them over HTTP. When the backend gets a
 * "fall_suspected" signal, it pulls a burst of frames from /capture for the
 * image-feature stage of the Random Forest.
 *
 * Board:   AI-Thinker ESP32-CAM (default pin map below). TODO: change if different.
 * PSRAM:   frame size / quality below assume PSRAM present. TODO: confirm your
 *          board has PSRAM; if not, drop to FRAMESIZE_QVGA and lower quality.
 *
 * Libraries: uses the built-in "esp32" board package camera driver (esp_camera.h).
 * Select board: "AI Thinker ESP32-CAM" in Arduino IDE.
 *
 * Not Wokwi-simulatable (no camera model). Flash to real hardware.
 */

#include "esp_camera.h"
#include <WiFi.h>

// ===================== TODO: credentials =====================
const char* WIFI_SSID = "YOUR_WIFI_SSID";       // TODO
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";   // TODO
// =============================================================

// ---- AI-Thinker ESP32-CAM pin map (TODO: change for other boards) ----
#define PWDN_GPIO_NUM  32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM   0
#define SIOD_GPIO_NUM  26
#define SIOC_GPIO_NUM  27
#define Y9_GPIO_NUM    35
#define Y8_GPIO_NUM    34
#define Y7_GPIO_NUM    39
#define Y6_GPIO_NUM    36
#define Y5_GPIO_NUM    21
#define Y4_GPIO_NUM    19
#define Y3_GPIO_NUM    18
#define Y2_GPIO_NUM     5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM  23
#define PCLK_GPIO_NUM  22

WiFiServer server(80);

void startCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM; config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {                       // TODO: confirm PSRAM
    config.frame_size = FRAMESIZE_VGA;       // 640x480
    config.jpeg_quality = 12;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QVGA;      // 320x240 fallback
    config.jpeg_quality = 15;
    config.fb_count = 1;
  }

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed"); return;
  }
}

void setup() {
  Serial.begin(115200);
  startCamera();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.print("\nCamera ready at http://"); Serial.println(WiFi.localIP());
  server.begin();
}

// Minimal HTTP: GET /capture returns one JPEG frame.
void loop() {
  WiFiClient client = server.available();
  if (!client) return;
  String req = client.readStringUntil('\r');
  client.readStringUntil('\n');

  if (req.indexOf("GET /capture") >= 0) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) { client.println("HTTP/1.1 500 Internal Server Error\r\n"); client.stop(); return; }
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: image/jpeg");
    client.print("Content-Length: "); client.println(fb->len);
    client.println("Connection: close");
    client.println();
    client.write(fb->buf, fb->len);
    esp_camera_fb_return(fb);
  } else {
    client.println("HTTP/1.1 404 Not Found\r\nConnection: close\r\n");
  }
  client.stop();
}
