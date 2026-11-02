/**
 * ROBODİ - Ağız Animasyonları
 * ESP32-C3 + 1.47" LCD (172x320)
 *
 * WiFi üzerinden komut alır, ağız animasyonlarını oynatır
 */

#include <WiFi.h>
#include <TFT_eSPI.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "ROBODİ_NETWORK";
const char* WIFI_PASS = "your_password";
const int SERVER_PORT = 8080;

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite sprite = TFT_eSprite(&tft);
WiFiServer server(SERVER_PORT);

#define BG_COLOR   TFT_BLACK
#define MOUTH_COLOR 0xFFFF
#define TEETH_COLOR TFT_WHITE
#define TONGUE_COLOR 0xF807  // Kırmızımsı

#define SCREEN_W 172
#define SCREEN_H 320
#define MOUTH_CX (SCREEN_W / 2)
#define MOUTH_CY (SCREEN_H / 2)

enum MouthState {
  M_IDLE,
  M_SPEAKING,
  M_SMILE,
  M_SURPRISED,
  M_THINKING
};

MouthState currentState = M_IDLE;
unsigned long stateStart = 0;
float speakPhase = 0;

void setupWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    server.begin();
    Serial.println("WiFi: " + WiFi.localIP().toString());
  }
}

void checkCommands() {
  WiFiClient client = server.available();
  if (!client) return;

  String line = "";
  unsigned long timeout = millis() + 500;
  while (client.connected() && millis() < timeout) {
    if (client.available()) {
      char c = client.read();
      if (c == '\n') break;
      line += c;
    }
  }
  client.stop();
  if (line.length() == 0) return;

  DynamicJsonDocument doc(128);
  if (deserializeJson(doc, line)) return;

  String anim = doc["anim"].as<String>();
  currentState = M_IDLE;
  stateStart = millis();

  if (anim == "speaking")   currentState = M_SPEAKING;
  else if (anim == "smile") currentState = M_SMILE;
  else if (anim == "surprised") currentState = M_SURPRISED;
  else if (anim == "thinking")  currentState = M_THINKING;
}

// --- Ağız Çizim Yardımcıları ---

void drawMouthLine(int x1, int y1, int x2, int y2, uint16_t color, int thickness = 3) {
  for (int i = -thickness/2; i <= thickness/2; i++) {
    sprite.drawLine(x1, y1 + i, x2, y2 + i, color);
  }
}

// Kavisli çizgi (quadratic bezier)
void drawCurve(int x0, int y0, int cx, int cy, int x1, int y1, uint16_t color, int thickness = 3) {
  int steps = 30;
  float px = x0, py = y0;
  for (int i = 1; i <= steps; i++) {
    float t = (float)i / steps;
    float nx = (1-t)*(1-t)*x0 + 2*(1-t)*t*cx + t*t*x1;
    float ny = (1-t)*(1-t)*y0 + 2*(1-t)*t*cy + t*t*y1;
    for (int w = -thickness/2; w <= thickness/2; w++) {
      sprite.drawLine((int)px, (int)py + w, (int)nx, (int)ny + w, color);
    }
    px = nx; py = ny;
  }
}

void renderIdle() {
  // Düz çizgi (kapalı ağız)
  int y = MOUTH_CY;
  int x1 = MOUTH_CX - 50;
  int x2 = MOUTH_CX + 50;
  drawMouthLine(x1, y, x2, y, MOUTH_COLOR, 4);

  // Köşe vurguları
  sprite.fillCircle(x1, y, 4, MOUTH_COLOR);
  sprite.fillCircle(x2, y, 4, MOUTH_COLOR);
}

void renderSpeaking() {
  speakPhase += 0.15;
  float openAmount = abs(sin(speakPhase)) * 35 + 5;

  int x1 = MOUTH_CX - 55;
  int x2 = MOUTH_CX + 55;
  int topY = MOUTH_CY - (int)(openAmount * 0.4);
  int botY = MOUTH_CY + (int)(openAmount * 0.6);

  // Ağız içi
  sprite.fillEllipse(MOUTH_CX, MOUTH_CY, 55, (int)openAmount, TFT_BLACK);
  sprite.fillEllipse(MOUTH_CX, MOUTH_CY + 5, 45, (int)(openAmount * 0.6), 0x6000); // Koyu kırmızı (boğaz)

  // Dişler (üst)
  if (openAmount > 10) {
    sprite.fillRect(x1 + 10, topY, (x2 - x1) - 20, (int)(openAmount * 0.35), TEETH_COLOR);
    // Diş çizgisi
    for (int tx = x1 + 15; tx < x2 - 15; tx += 14) {
      sprite.drawLine(tx, topY, tx, topY + (int)(openAmount * 0.25), 0xAAAAAA);
    }
  }

  // Ağız konturları
  drawCurve(x1, MOUTH_CY, MOUTH_CX, topY, x2, MOUTH_CY, MOUTH_COLOR, 4);  // üst
  drawCurve(x1, MOUTH_CY, MOUTH_CX, botY, x2, MOUTH_CY, MOUTH_COLOR, 4);  // alt
}

void renderSmile() {
  int x1 = MOUTH_CX - 55;
  int x2 = MOUTH_CX + 55;
  int cpY = MOUTH_CY + 40;  // Kontrol noktası aşağıda = gülen ağız

  // Gülücük çizgisi
  drawCurve(x1, MOUTH_CY, MOUTH_CX, cpY, x2, MOUTH_CY, MOUTH_COLOR, 5);

  // Köşe noktaları
  sprite.fillCircle(x1, MOUTH_CY, 5, MOUTH_COLOR);
  sprite.fillCircle(x2, MOUTH_CY, 5, MOUTH_COLOR);

  // Yanaklar hafif kırmızı (opsiyonel)
  sprite.fillEllipse(x1 - 15, MOUTH_CY + 20, 12, 8, 0xF80F); // Sol yanak
  sprite.fillEllipse(x2 + 15, MOUTH_CY + 20, 12, 8, 0xF80F); // Sağ yanak
}

void renderSurprised() {
  // Yuvarlak açık ağız
  sprite.fillCircle(MOUTH_CX, MOUTH_CY + 10, 40, TFT_BLACK);
  sprite.drawCircle(MOUTH_CX, MOUTH_CY + 10, 40, MOUTH_COLOR);
  sprite.drawCircle(MOUTH_CX, MOUTH_CY + 10, 39, MOUTH_COLOR);
  sprite.drawCircle(MOUTH_CX, MOUTH_CY + 10, 41, MOUTH_COLOR);

  // Üst diş
  sprite.fillRect(MOUTH_CX - 20, MOUTH_CY - 15, 40, 12, TEETH_COLOR);
}

void renderThinking() {
  // Yana doğru büzülmüş ağız
  int x1 = MOUTH_CX - 10;
  int x2 = MOUTH_CX + 40;
  int y = MOUTH_CY + 5;

  drawCurve(x1, y, MOUTH_CX + 15, y - 10, x2, y, MOUTH_COLOR, 4);
  sprite.fillCircle(x1, y, 4, MOUTH_COLOR);
  sprite.fillCircle(x2, y, 4, MOUTH_COLOR);

  // Düşünce noktaları
  float t = millis() / 400.0;
  for (int i = 0; i < 3; i++) {
    int dotY = MOUTH_CY - 60 + (int)(sin(t + i * 1.0) * 5);
    sprite.fillCircle(MOUTH_CX - 20 + i * 20, dotY, 5, MOUTH_COLOR);
  }
}

void setup() {
  Serial.begin(115200);

  tft.init();
  tft.setRotation(0);
  tft.fillScreen(BG_COLOR);

  sprite.createSprite(SCREEN_W, SCREEN_H);

  setupWiFi();

  Serial.println("Ağız sistemi hazır!");
}

void loop() {
  checkCommands();

  sprite.fillSprite(BG_COLOR);

  switch (currentState) {
    case M_IDLE:      renderIdle(); break;
    case M_SPEAKING:  renderSpeaking(); break;
    case M_SMILE:     renderSmile(); break;
    case M_SURPRISED: renderSurprised(); break;
    case M_THINKING:  renderThinking(); break;
  }

  sprite.pushSprite(0, 0);

  if (currentState != M_IDLE && currentState != M_SPEAKING) {
    if (millis() - stateStart > 3000) {
      currentState = M_IDLE;
    }
  }

  delay(16);
}
