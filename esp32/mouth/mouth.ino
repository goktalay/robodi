/*
 * ROBODİ - Ağız
 * Kart: Waveshare ESP32-C3 1.47" LCD (ST7789, 172×320), yatay kullanılır (320×172)
 * Bağlantı: Raspberry Pi'ye USB-C (USB CDC), 115200, satır sonlu JSON.
 * Kütüphaneler: "GFX Library for Arduino" (Arduino_GFX), ArduinoJson 7
 * Arduino ayarı: USB CDC On Boot = Enabled
 *
 * Komutlar:
 *   {"cmd":"WHO"}                                → {"board":"mouth"}
 *   {"cmd":"EXPRESSION","mouth":"smile","color":[r,g,b]}
 *   {"cmd":"BRIGHTNESS","value":0-255}  {"cmd":"INIT"}  {"cmd":"SLEEP"}
 * Ağız şekilleri: flat, smile, frown, open, hmm, talking (kendi kendine oynar)
 */
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include "pins.h"

#define BOARD_NAME "mouth"
#define W  320
#define H  172
#define CX (W / 2)
#define CY (H / 2)

Arduino_DataBus *bus = new Arduino_ESP32SPI(MOUTH_DC, MOUTH_CS, MOUTH_SCK, MOUTH_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *gfx = new Arduino_ST7789(bus, MOUTH_RST, 1 /* yatay */, true /* IPS */,
                                      172, 320, MOUTH_COL_OFS, MOUTH_ROW_OFS, MOUTH_COL_OFS, MOUTH_ROW_OFS);

String shape = "flat";
uint16_t color = WHITE;
unsigned long lastFrame = 0;
int frame = 0;
const int TALK_H[] = {10, 28, 46, 28};   // konuşma kareleri: ağız açıklığı (px)

void draw(const String &s) {
  gfx->fillScreen(BLACK);
  if (s == "smile") {
    gfx->fillArc(CX, CY - 60, 110, 94, 30, 150, color);
  } else if (s == "frown") {
    gfx->fillArc(CX, CY + 80, 110, 94, 210, 330, color);
  } else if (s == "open") {
    gfx->fillEllipse(CX, CY, 52, 42, color);
    gfx->fillEllipse(CX, CY, 40, 30, gfx->color565(120, 0, 20));
  } else if (s == "hmm") {
    gfx->fillRoundRect(CX - 50, CY, 90, 10, 5, color);
    gfx->fillCircle(CX + 62, CY + 5, 7, color);
  } else if (s == "talking") {
    int h = TALK_H[frame % 4];
    gfx->fillRoundRect(CX - 60, CY - h / 2, 120, h, min(h / 2, 20), color);
  } else {   // flat
    gfx->fillRoundRect(CX - 80, CY - 6, 160, 12, 6, color);
  }
}

void setBrightness(int v) {
#if MOUTH_BL >= 0
  analogWrite(MOUTH_BL, constrain(v, 0, 255));
#endif
}

void handle(const String &line) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) return;
  const char *cmd = doc["cmd"] | "";

  if (!strcmp(cmd, "WHO")) {
    Serial.println("{\"board\":\"" BOARD_NAME "\"}");
  } else if (!strcmp(cmd, "EXPRESSION")) {
    if (doc["color"].is<JsonArray>())
      color = gfx->color565(doc["color"][0], doc["color"][1], doc["color"][2]);
    shape = doc["mouth"] | "flat";
    frame = 0;
    draw(shape);
  } else if (!strcmp(cmd, "BRIGHTNESS")) {
    setBrightness(doc["value"] | 200);
  } else if (!strcmp(cmd, "INIT")) {
    Serial.println("{\"status\":\"ready\",\"board\":\"" BOARD_NAME "\"}");
    setBrightness(200);
    draw("smile"); delay(800); shape = "flat"; draw(shape);
  } else if (!strcmp(cmd, "SLEEP")) {
    gfx->fillScreen(BLACK);
    setBrightness(0);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);
#if MOUTH_BL >= 0
  pinMode(MOUTH_BL, OUTPUT);
#endif
  gfx->begin();
  setBrightness(200);
  draw(shape);
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length()) handle(line);
  }
  if (shape == "talking" && millis() - lastFrame > 120) {
    lastFrame = millis();
    frame++;
    draw(shape);
  }
}
