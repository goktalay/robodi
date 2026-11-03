// ROBODİ göğüs ekranı - Waveshare ESP32-S3 1.69" dokunmatik LCD kartı pinleri
// DOĞRULA: Değerleri kartın Waveshare wiki sayfasındaki şemadan girin, sonra #error satırını silin.
#error "esp32/chest/pins.h: pin numaralarını Waveshare wiki'den girip bu satırı silin"

#define CHEST_SCK   -1
#define CHEST_MOSI  -1
#define CHEST_CS    -1
#define CHEST_DC    -1
#define CHEST_RST   -1
#define CHEST_BL    -1   // arka ışık (yoksa -1)

// 280 piksel yükseklikli ST7789 panelin bellek kaydırması. Görüntü kayıksa wiki örneğindeki değeri kullanın.
#define CHEST_ROW_OFS 20
