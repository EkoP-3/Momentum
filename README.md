# Momentum

Konuyu yaz, gerisini Momentum halletsin: konu sahnelere ayrılır, her sahne için görsel üretilir
ve görseller zoom/kaydırma animasyonları ve geçişlerle birleştirilerek **20 saniyelik dikey (9:16)**
bir motivasyon videosuna dönüştürülür. Reels, TikTok ve Shorts için hazırdır.

## Nasıl çalışır?

1. **Sahne planı (Claude):** Konu, hikâye yayı izleyen 5 sahneye bölünür. Her sahne için Türkçe
   başlık ve açıklama, İngilizce görsel prompt'u ve bir kamera hareketi (zoom in/out, sağa/sola/yukarı/aşağı kaydırma) seçilir.
2. **Görseller (Gemini):** İlk sahne üretilir, sonraki sahnelere referans olarak verilir; böylece
   karakter, stil ve renkler tüm videoda tutarlı kalır.
3. **Video (ffmpeg):** Her görsele yumuşak Ken Burns hareketi uygulanır, sahneler farklı geçişlerle
   (fade, slideup, circleopen…) bağlanır, seçilen müzik eklenip sonunda yavaşça kısılır.
   Çıktı tam 20 sn, 1080x1920, 30 fps H.264 MP4.

## Kurulum

Gerekenler: Python 3.10+ ve [ffmpeg](https://ffmpeg.org/download.html) (`ffmpeg -version` ile kontrol edin).

```bash
pip install -r requirements.txt
cp .env.example .env   # ANTHROPIC_API_KEY ve GEMINI_API_KEY değerlerini girin
uvicorn momentum.app:app
```

Tarayıcıda <http://localhost:8000> adresini açın.

## Kullanım

- **Konu:** Ne anlatmak istediğinizi bir iki cümleyle yazın (ör. *"Sabah 5'te kalkıp maratona hazırlanan genç bir kadının azmi"*).
- **Görsel stil:** Sinematik, Anime, 3D Animasyon, Dijital illüstrasyon veya Suluboya.
- **Müzik:** `music/` klasörüne mp3 koyun ya da arayüzdeki **Yükle** butonunu kullanın; "Rastgele" seçeneği her videoda farklı parça seçer.
- **Video Oluştur**'a basın; sahneler ve görseller hazırlandıkça ekranda görünür, sonunda videoyu izleyip indirebilirsiniz.

Her videonun dosyaları `output/<iş-no>/` klasöründe saklanır: `scenes.json` (sahne planı), sahne görselleri ve `video.mp4`.

## Deneme modu

API anahtarı olmadan arayüzü ve video birleştirmeyi denemek için:

```bash
MOMENTUM_MOCK=1 uvicorn momentum.app:app
```

Bu modda API çağrılmaz, renkli yer tutucu görsellerle gerçek bir 20 saniyelik video üretilir.

## Ayarlar (`.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `MOMENTUM_CLAUDE_MODEL` | `claude-opus-5-5` | Sahne planlayan Claude modeli |
| `MOMENTUM_IMAGE_MODEL` | `gemini-3.1-flash-image` | Görsel üreten Gemini modeli |
| `MOMENTUM_SCENES` | `5` | Videodaki sahne sayısı |
| `MOMENTUM_MOCK` | kapalı | `1` ise API çağırmadan deneme modu |

## Proje yapısı

```
momentum/
  app.py        web sunucusu ve API uçları
  pipeline.py   konu -> plan -> görseller -> video akışı
  planner.py    Claude ile sahne planı
  imagegen.py   Gemini ile görsel üretimi
  video.py      ffmpeg ile animasyon ve birleştirme
  static/index.html  arayüz
music/          arka plan müzikleri
output/         üretilen videolar
```
