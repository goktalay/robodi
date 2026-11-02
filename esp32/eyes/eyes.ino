/*
 * ROBODİ - ESP32-S3 Göz LED Matrix Kontrolü
 * Donanım: 2× 8x8 MAX7219 LED Matrix (Gözler)
 * Haberleşme: UART (115200 baud) → JSON komutları
 *
 * Bağlantı:
 *   ESP32 GPIO17 (TX) → RPi GPIO15 (RX)
 *   ESP32 GPIO16 (RX) → RPi GPIO14 (TX)
 *   ESP32 GPIO5  → MAX7219 DIN
 *   ESP32 GPIO18 → MAX7219 CLK
 *   ESP32 GPIO19 → MAX7219 CS
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <MD_MAX72xx.h>
#include <MD_Parola.h>

// ── Donanım tanımları ─────────────────────────────────────────
#define MAX_DEVICES  2    // 2 adet 8x8 matrix (sol + sağ göz)
#define CS_PIN       19
#define CLK_PIN      18
#define DIN_PIN       5
#define HW_TYPE      MD_MAX72xx::FC16_HW

MD_Parola eyes(HW_TYPE, DIN_PIN, CLK_PIN, CS_PIN, MAX_DEVICES);

// ── Göz desenleri (8x8 bitmap) ───────────────────────────────
const uint8_t EYE_NEUTRAL[] = {
  0b00111100,
  0b01111110,
  0b11111111,
  0b11111111,
  0b11111111,
  0b01111110,
  0b00111100,
  0b00000000
};

const uint8_t EYE_HAPPY[] = {
  0b00000000,
  0b00111100,
  0b01111110,
  0b11111111,
  0b11111111,
  0b01111110,
  0b00111100,
  0b00000000
};

const uint8_t EYE_SAD[] = {
  0b00111100,
  0b01111110,
  0b11111111,
  0b11000011,
  0b11000011,
  0b00000000,
  0b00000000,
  0b00000000
};

const uint8_t EYE_ANGRY[] = {
  0b11000000,
  0b01100000,
  0b00111100,
  0b01111110,
  0b11111111,
  0b11111111,
  0b01111110,
  0b00000000
};

const uint8_t EYE_WIDE[] = {
  0b01111110,
  0b11111111,
  0b11111111,
  0b11111111,
  0b11111111,
  0b11111111,
  0b01111110,
  0b00111100
};

const uint8_t EYE_SQUINT[] = {
  0b00000000,
  0b00000000,
  0b00111100,
  0b01111110,
  0b01111110,
  0b00111100,
  0b00000000,
  0b00000000
};

const uint8_t EYE_BLINK[] = {
  0b00000000,
  0b00000000,
  0b00000000,
  0b11111111,
  0b11111111,
  0b00000000,
  0b00000000,
  0b00000000
};

// ── State ─────────────────────────────────────────────────────
String currentExpression = "neutral";
unsigned long lastBlinkTime = 0;
unsigned long blinkInterval = 4000;  // 4 saniyede bir göz kırp
bool isBlinking = false;

// ── Setup ─────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);   // USB debug
  Serial2.begin(115200, SERIAL_8N1, 16, 17);  // RPi UART

  eyes.begin();
  eyes.setIntensity(0, 4);  // Parlaklık (0-15)
  eyes.setIntensity(1, 4);

  setEyes("neutral");
  Serial.println("ROBODİ Eyes v1.0 hazır");
}

// ── Ana Döngü ─────────────────────────────────────────────────
void loop() {
  // UART'tan JSON komut al
  if (Serial2.available()) {
    String line = Serial2.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      handleCommand(line);
    }
  }

  // Otomatik göz kırpma
  if (millis() - lastBlinkTime > blinkInterval && !isBlinking) {
    startBlink();
  }
  if (isBlinking && millis() - lastBlinkTime > 150) {
    endBlink();
  }

  delay(10);
}

// ── Komut İşle ────────────────────────────────────────────────
void handleCommand(String json) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, json);
  if (err) {
    Serial.println("JSON parse hatası: " + String(err.c_str()));
    return;
  }

  const char* cmd = doc["cmd"];

  if (strcmp(cmd, "EXPRESSION") == 0) {
    const char* eyes_expr = doc["eyes"] | "neutral";
    setEyes(eyes_expr);
    currentExpression = String(eyes_expr);

  } else if (strcmp(cmd, "BLINK") == 0) {
    startBlink();

  } else if (strcmp(cmd, "BRIGHTNESS") == 0) {
    int bri = doc["value"] | 4;
    eyes.setIntensity(0, bri);
    eyes.setIntensity(1, bri);

  } else if (strcmp(cmd, "INIT") == 0) {
    Serial2.println("{\"status\":\"ready\",\"device\":\"eyes\"}");
    setEyes("happy");
    delay(1000);
    setEyes("neutral");

  } else if (strcmp(cmd, "SLEEP") == 0) {
    showPattern(EYE_BLINK);
    delay(500);
    eyes.setIntensity(0, 0);
    eyes.setIntensity(1, 0);
  }
}

// ── Göz Deseni Göster ────────────────────────────────────────
void setEyes(const char* expression) {
  if (strcmp(expression, "neutral")  == 0) showPattern(EYE_NEUTRAL);
  else if (strcmp(expression, "happy")   == 0) showPattern(EYE_HAPPY);
  else if (strcmp(expression, "sad")     == 0) showPattern(EYE_SAD);
  else if (strcmp(expression, "angry")   == 0) showPattern(EYE_ANGRY);
  else if (strcmp(expression, "wide")    == 0) showPattern(EYE_WIDE);
  else if (strcmp(expression, "squint")  == 0) showPattern(EYE_SQUINT);
  else showPattern(EYE_NEUTRAL);
}

void showPattern(const uint8_t pattern[]) {
  for (int dev = 0; dev < MAX_DEVICES; dev++) {
    for (int row = 0; row < 8; row++) {
      eyes.getGraphicObject()->setRow(dev, row, pattern[row]);
    }
  }
}

void startBlink() {
  showPattern(EYE_BLINK);
  isBlinking    = true;
  lastBlinkTime = millis();
  // Sonraki blink için rastgele aralık (3-6 saniye)
  blinkInterval = random(3000, 6000);
}

void endBlink() {
  setEyes(currentExpression.c_str());
  isBlinking = false;
}
