/*
 * ROBODİ - Gözler
 * Kart: Waveshare ESP32-S3 1.28" çift yuvarlak göz (2× GC9A01, 240×240)
 * Bağlantı: Raspberry Pi'ye USB-C (USB CDC), 115200, satır sonlu JSON.
 * Kütüphaneler: "GFX Library for Arduino" (Arduino_GFX), ArduinoJson 7
 * Arduino ayarı: USB CDC On Boot = Enabled
 *
 * Komutlar:
 *   {"cmd":"WHO"}                                → {"board":"eyes"}
 *   {"cmd":"INIT"}                               → açılış animasyonu
 *   {"cmd":"EXPRESSION","eyes":"happy","color":[r,g,b]}
 *   {"cmd":"BLINK"}  {"cmd":"BRIGHTNESS","value":0-255}  {"cmd":"SLEEP"}
 * Göz şekilleri: neutral, happy, sad, angry, wide, squint
 */
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include "pins.h"

#define BOARD_NAME "eyes"
#define W  240
#define H  240
#define CX 120
#define CY 120

// İki ekran SCK/MOSI/DC/RST'yi paylaşır, CS'leri ayrıdır: CS elle seçilir.
Arduino_DataBus *bus = new Arduino_ESP32SPI(EYE_DC, GFX_NOT_DEFINED, EYE_SCK, EYE_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *gfx = new Arduino_GC9A01(bus, EYE_RST, 0 /* döndürme */, true /* IPS */);

String shape = "neutral";
uint16_t color = 0x041F;       // varsayılan mavi
unsigned long lastBlink = 0, blinkEvery = 4000;
bool blinking = false;

// ── Ekran seçimi ────────────────────────────────────────────────
enum { LEFT = 0, RIGHT = 1, BOTH = 2 };

void selectEye(int which) {
  digitalWrite(EYE_L_CS, (which == LEFT  || which == BOTH) ? LOW : HIGH);
  digitalWrite(EYE_R_CS, (which == RIGHT || which == BOTH) ? LOW : HIGH);
}

// Ayna: sağ gözde "dış" taraf sağdadır
int mx(int x, bool mirror) { return mirror ? W - x : x; }

// Göz kapağı: dış köşede yOuter, iç köşede yInner hizasına kadar üstü kapatır
void lid(int yOuter, int yInner, bool mirror) {
  gfx->fillTriangle(mx(0, mirror), 0, mx(W, mirror), 0, mx(W, mirror), yInner, BLACK);
  gfx->fillTriangle(mx(0, mirror), 0, mx(W, mirror), yInner, mx(0, mirror), yOuter, BLACK);
}

void drawEye(const String &s, bool mirror) {
  gfx->fillScreen(BLACK);
  if (s == "blink") {
    gfx->fillRoundRect(CX - 80, CY - 8, 160, 16, 8, color);
    return;
  }
  if (s == "happy") {
    gfx->fillArc(CX, CY + 40, 90, 62, 200, 340, color);   // ^ şekli
    return;
  }
  int r = (s == "wide") ? 100 : 80;
  gfx->fillCircle(CX, CY, r, color);
  gfx->fillCircle(CX, CY, r / 2, BLACK);                      // göz bebeği
  gfx->fillCircle(mx(CX + 22, mirror), CY - 24, 10, WHITE);   // parıltı

  if (s == "sad")    lid(CY - 10, CY - 80, mirror);           // dış köşe düşük
  if (s == "angry")  lid(CY - 80, CY - 10, mirror);           // iç köşe düşük
  if (s == "squint") {
    gfx->fillRect(0, 0, W, CY - 30, BLACK);
    gfx->fillRect(0, CY + 30, W, H - (CY + 30), BLACK);
  }
}

void show(const String &s) {
  selectEye(LEFT);  drawEye(s, false);
  selectEye(RIGHT); drawEye(s, true);
  selectEye(-1);
}

void setBrightness(int v) {
#if EYE_BL >= 0
  analogWrite(EYE_BL, constrain(v, 0, 255));
#endif
}

// ── Komutlar ────────────────────────────────────────────────────
void handle(const String &line) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) return;
  const char *cmd = doc["cmd"] | "";

  if (!strcmp(cmd, "WHO")) {
    Serial.println("{\"board\":\"" BOARD_NAME "\"}");
  } else if (!strcmp(cmd, "EXPRESSION")) {
    if (doc["color"].is<JsonArray>())
      color = gfx->color565(doc["color"][0], doc["color"][1], doc["color"][2]);
    shape = doc["eyes"] | "neutral";
    show(shape);
  } else if (!strcmp(cmd, "BLINK")) {
    lastBlink = 0;
  } else if (!strcmp(cmd, "BRIGHTNESS")) {
    setBrightness(doc["value"] | 200);
  } else if (!strcmp(cmd, "INIT")) {
    Serial.println("{\"status\":\"ready\",\"board\":\"" BOARD_NAME "\"}");
    setBrightness(200);
    show("happy"); delay(800); shape = "neutral"; show(shape);
  } else if (!strcmp(cmd, "SLEEP")) {
    show("blink"); delay(300);
    selectEye(BOTH); gfx->fillScreen(BLACK); selectEye(-1);
    setBrightness(0);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);
  pinMode(EYE_L_CS, OUTPUT);
  pinMode(EYE_R_CS, OUTPUT);
#if EYE_BL >= 0
  pinMode(EYE_BL, OUTPUT);
#endif
  selectEye(BOTH);          // iki ekranı birlikte başlat
  gfx->begin();
  selectEye(-1);
  setBrightness(200);
  show(shape);
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length()) handle(line);
  }
  // Otomatik göz kırpma (3–6 sn)
  unsigned long now = millis();
  if (!blinking && now - lastBlink > blinkEvery && shape != "happy") {
    show("blink");
    blinking = true;
    lastBlink = now;
    blinkEvery = random(3000, 6000);
  }
  if (blinking && now - lastBlink > 150) {
    show(shape);
    blinking = false;
  }
}
