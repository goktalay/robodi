# ESP32 ekran kartları

| Klasör | Kart | Ekran | Görev |
|---|---|---|---|
| `eyes/` | Waveshare ESP32-S3 1.28" çift göz | 2× GC9A01 yuvarlak, 240×240 | Gözler |
| `mouth/` | Waveshare ESP32-C3 1.47" LCD | ST7789, 172×320 (yatay) | Ağız |
| `chest/` | Waveshare ESP32-S3 1.69" dokunmatik LCD | ST7789, 240×280 | Göğüs ekranı |

Kartlar Raspberry Pi'ye USB-C kabloyla bağlanır; tek kablo hem besler hem haberleştirir.
Pi tarafı kartları kendisi bulur (`config/settings.yaml` → `esp32.boards: auto`): her porta
`{"cmd":"WHO"}` gönderir, kart `{"board":"eyes"}` gibi adıyla cevap verir.

## Yükleme

1. Arduino IDE'ye ESP32 kart paketini kurun (Espressif, `esp32` 3.x).
2. Kütüphaneler: **GFX Library for Arduino** (moononournation) ve **ArduinoJson** 7.x.
3. Her klasördeki `pins.h` dosyasını kartın Waveshare wiki sayfasındaki şemadan doldurun ve
   `#error` satırını silin. Pinler girilmeden taslak bilerek derlenmez.
4. Kart seçimi: göz ve göğüs için `ESP32S3 Dev Module`, ağız için `ESP32C3 Dev Module`.
   **USB CDC On Boot: Enabled** olmalı (komutlar USB'den gelir).
5. Yükleyin; Seri Monitör'de (115200) `{"cmd":"WHO"}` yazınca kart adını döndürmeli.

## Protokol

Satır sonlu JSON, 115200 baud. Pi her karta yalnızca kendi alanını gönderir.

```
{"cmd":"WHO"}                                             → {"board":"eyes"}
{"cmd":"INIT","version":"2.0"}                            → açılış animasyonu
{"cmd":"EXPRESSION","eyes":"happy","color":[0,255,100]}   → göz kartı
{"cmd":"EXPRESSION","mouth":"smile","color":[0,255,100]}  → ağız kartı
{"cmd":"EXPRESSION","state":"happy","color":[0,255,100]}  → göğüs kartı
{"cmd":"BLINK"}                                           → göz kırpar
{"cmd":"BRIGHTNESS","value":200}                          → 0–255
{"cmd":"SLEEP"}                                           → ekranları karartır
```

Göz şekilleri: `neutral, happy, sad, angry, wide, squint`.
Ağız şekilleri: `flat, smile, frown, open, hmm, talking` (`talking` kendi kendine oynar).
Yeni komut eklenirse hem `src/core/esp32_comm.py` hem ilgili `.ino` güncellenir.

## Durum

Taslaklar henüz derlenmedi ve donanımda denenmedi. Şekiller basit geometrik çizimler;
tasarımcının ifade görselleri gelince değiştirilecek.
