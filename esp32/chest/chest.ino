/*
 * ROBODİ - Göğüs ekranı
 * Kart: Waveshare ESP32-S3 1.69" dokunmatik LCD (ST7789, 240×280)
 * Bağlantı: Raspberry Pi'ye USB-C (USB CDC), 115200, satır sonlu JSON.
 * Kütüphaneler: "GFX Library for Arduino" (Arduino_GFX), ArduinoJson 7
 * Arduino ayarı: USB CDC On Boot = Enabled
 *
 * Komutlar:
 *   {"cmd":"WHO"}                                    → {"board":"chest"}
 *   {"cmd":"EXPRESSION","state":"listening","color":[r,g,b]}
 *   {"cmd":"BRIGHTNESS","value":0-255}  {"cmd":"INIT"}  {"cmd":"SLEEP"}
 * Robotun durumunu renkli halka ve kısa yazıyla gösterir. Dokunmatik henüz kullanılmıyor.
 */
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include "pins.h"

#define BOARD_NAME "chest"
#define W 240
#define H 280

Arduino_DataBus *bus = new Arduino_ESP32SPI(CHEST_DC, CHEST_CS, CHEST_SCK, CHEST_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *gfx = new Arduino_ST7789(bus, CHEST_RST, 0, true /* IPS */,
                                      240, 280, 0, CHEST_ROW_OFS, 0, CHEST_ROW_OFS);

// Varsayılan yazı tipinde Türkçe harf yok; etiketler bu yüzden ASCII
const char *label(const String &state) {
  if (state == "listening") return "Seni dinliyorum";
  if (state == "thinking")  return "Bir saniye...";
  if (state == "speaking")  return "Cevap veriyorum";
  if (state == "happy")     return "Mutlu";
  if (state == "sad")       return "Hmm...";
  if (state == "angry")     return "Grr!";
  if (state == "surprised") return "Vay!";
  return "Merhaba";
}

void draw(const String &state, uint16_t color) {
  gfx->fillScreen(BLACK);
  gfx->fillCircle(W / 2, 115, 72, color);
  gfx->fillCircle(W / 2, 115, 56, BLACK);
  const char *text = label(state);
  gfx->setTextSize(2);
  gfx->setTextColor(WHITE);
  gfx->setCursor((W - strlen(text) * 12) / 2, 220);   // 2× yazı: karakter 12 px
  gfx->print(text);
}

void setBrightness(int v) {
#if CHEST_BL >= 0
  analogWrite(CHEST_BL, constrain(v, 0, 255));
#endif
}

void handle(const String &line) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) return;
  const char *cmd = doc["cmd"] | "";

  if (!strcmp(cmd, "WHO")) {
    Serial.println("{\"board\":\"" BOARD_NAME "\"}");
  } else if (!strcmp(cmd, "EXPRESSION")) {
    uint16_t color = doc["color"].is<JsonArray>()
      ? gfx->color565(doc["color"][0], doc["color"][1], doc["color"][2]) : BLUE;
    draw(doc["state"] | "idle", color);
  } else if (!strcmp(cmd, "BRIGHTNESS")) {
    setBrightness(doc["value"] | 200);
  } else if (!strcmp(cmd, "INIT")) {
    Serial.println("{\"status\":\"ready\",\"board\":\"" BOARD_NAME "\"}");
    setBrightness(200);
    draw("idle", gfx->color565(0, 100, 255));
  } else if (!strcmp(cmd, "SLEEP")) {
    gfx->fillScreen(BLACK);
    setBrightness(0);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);
#if CHEST_BL >= 0
  pinMode(CHEST_BL, OUTPUT);
#endif
  gfx->begin();
  setBrightness(200);
  draw("idle", gfx->color565(0, 100, 255));
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length()) handle(line);
  }
}
