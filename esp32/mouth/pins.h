// ROBODİ ağız - Waveshare ESP32-C3 1.47" LCD kartı pinleri
// DOĞRULA: Değerleri kartın Waveshare wiki sayfasındaki şemadan girin, sonra #error satırını silin.
#error "esp32/mouth/pins.h: pin numaralarını Waveshare wiki'den girip bu satırı silin"

#define MOUTH_SCK   -1
#define MOUTH_MOSI  -1
#define MOUTH_CS    -1
#define MOUTH_DC    -1
#define MOUTH_RST   -1
#define MOUTH_BL    -1   // arka ışık (yoksa -1)

// 172 piksel genişlikli ST7789 panelin bellek kaydırması. Görüntü kayıksa wiki örneğindeki değeri kullanın.
#define MOUTH_COL_OFS 34
#define MOUTH_ROW_OFS 0
