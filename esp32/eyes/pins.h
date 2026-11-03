// ROBODİ gözler - Waveshare ESP32-S3 1.28" çift göz kartı pinleri
// DOĞRULA: Değerleri kartın Waveshare wiki sayfasındaki şemadan girin, sonra #error satırını silin.
// Bu taslak, iki ekranın SCK/MOSI/DC/RST'yi paylaştığını ve CS'lerinin ayrı olduğunu varsayar.
// Kartta ekranlar ayrı DC/RST kullanıyorsa eyes.ino'daki ekran seçimi buna göre değiştirilmeli.
#error "esp32/eyes/pins.h: pin numaralarını Waveshare wiki'den girip bu satırı silin"

#define EYE_SCK   -1
#define EYE_MOSI  -1
#define EYE_DC    -1
#define EYE_RST   -1
#define EYE_L_CS  -1   // sol göz
#define EYE_R_CS  -1   // sağ göz
#define EYE_BL    -1   // arka ışık (yoksa -1)
