# GE Engine — AI Destekli Deterministik Oyunlaştırma Platformu

Gerçek zamanlı video platformu + oyunlaştırma motoru + **GPT-4o AI katmanı**.
Kullanıcılar kayıt olur, tarayıcıda gerçekten video izler; izlenen her saniye
ölçülür, görev eşiği aşıldığı **anda** puan, seviye, rozet, başarım ve canlı
bildirim düşer. Tüm iş kararları (puan / rozet / sıralama / sezon ödülü)
deterministik kural motorunda alınır — `random` yok, `eval()` yok, mock yok,
**LLM asla iş kararı vermez: sadece gerçek veriyi anlatır ve çevirir.**

## Hızlı Başlangıç

```bash
# 1) .env dosyası oluştur (kök dizine):
#    OPENAI_API_KEY=sk-...        ← AI katmanı için (yoksa deterministik mod)
#    LLM_ENABLED=true
#    LLM_MODEL=gpt-4o
#    SECRET_KEY=degistir-bunu

# 2) Başlat (Windows):
start.bat

# veya manuel:
pip install fastapi "uvicorn[standard]" pydantic PyJWT openai python-dotenv
python database/setup.py
uvicorn api.main:app --reload --port 8000
```

- Uygulama → **http://localhost:8000/** &nbsp;·&nbsp; Swagger → **/docs**
- Varsayılan admin: `admin / admin123`
- PWA: tarayıcıdan "uygulamayı yükle" ile telefona kurulabilir

## AI Engine — 12 Yetenek

Her yetenek **gerçek DB verisi** üzerinde çalışır; GPT-4o yalnızca dil
katmanıdır ve her birinin LLM'siz **deterministik fallback'i** vardır
(fallback'ler de ezber değil, gerçek sayılardan hesaplanır).

| Yetenek | Ne yapar | Nerede |
|---|---|---|
| 🤖 AI Koç (sohbet) | Konuşma hafızalı çok turlu sohbet; her turda güncel evidence yeniden üretilir | Panel |
| 🎯 Günün Planı | Panel açılışında otomatik 3 maddelik kişisel plan (streak riski + görev açıkları + sezon); günde 1 GPT çağrısı, cache'li | Panel |
| 🧭 Intent sınıflandırma | Türkçe soruları kalıp + GPT-4o ile kategorize eder; kategorisiz soruları serbest modda DOĞRUDAN yanıtlar | Panel · İzleme |
| 🔍 Doğal dil araması | "yarım saatten kısa yüksek puanlı animasyon" → GPT filtreye çevirir, sonuç **gerçek parametreli SQL**'den | Ctrl+K palet |
| 🎬 Kişisel öneriler | Gerçek izleme geçmişinden tür profili + GPT açıklaması | Katalog |
| 💡 Görev ipuçları | Her aktif görevin anlık açığı + GPT motivasyon satırı | Panel |
| 📋 Günlük özet · 📅 Haftalık rapor | Gerçek gün/hafta kırılımından GPT koç anlatısı | Panel |
| 🗣 Topluluk özeti | Gerçek yorum + puanlardan "topluluk ne diyor"; kaynak değişmedikçe cache | İçerik detayı |
| 😊 Duygu analizi | Her yorum GPT ile 1 kez etiketlenir (pozitif/negatif/nötr); LLM yoksa **uydurma etiket yok** | İçerik · Admin |
| ⚔️ Rakip analizi | İki kullanıcının gerçek istatistik kıyası; yakalama süresi gerçek 7 gün temposundan | Liderlik |
| 🧠 Platform analizi | 13 gerçek metrik kümesinden yönetici özeti + 3 aksiyon önerisi | Admin |
| 🛠 AI Görev Tasarımcısı | GPT metriklerden görev önerir → **safe parser doğrular** → admin onaylarsa oluşur | Admin |

## Oyunlaştırma Çekirdeği (deterministik)

- **Puan motoru** — görev koşulları `alan operatör sayı` sözdiziminde,
  whitelist'li parser (eval yok); günlük cap, idempotent değerlendirme
- **Seviye/XP** — `T(n)=50·n·(n+1)` eğrisi, unvanlar (Çaylak → Platform Yıldızı)
- **Rozetler** — Bronze/Silver/Gold/Platinum puan eşikleri
- **Başarımlar** — 14 tek seferlik kilometre taşı; koşullar gerçek DB
  sorguları, Kaşif hedefi katalogdaki tür sayısından **dinamik**
- **Sezonlar** — ISO hafta yarışları; pazartesi lazy-finalization (zamanlayıcı
  yok, idempotent), ilk 3'e gerçek ledger ödülü (500/300/150)
- **Watch Party** — oda kodu ile ortak izleme; parti dakikaları sunucuda ölçülür

## Sosyal Katman

Takip sistemi + arkadaş liderliği · yorum + 1-5 yıldız oylama · aktivite
akışı + trend içerikler · public profiller + paylaşım kartı · kalıcı bildirim
merkezi (SSE canlı + DB geçmişi) · içerik detay sayfası (benzer videolar,
puan dağılımı)

## Mimari

```text
Vanilla JS SPA (frontend/)                FastAPI (api/)
  8 sayfa · GSAP · SSE · PWA      HTTP     routers/ (17 router)
  Ctrl+K komut paleti            ─────►        │
                                               ▼
                                  Motorlar (engine/ — 24 modül)
                                    kural parser (eval'siz) · level · season
                                    achievement · sentiment · nl_search
                                    llm_adapter (TEK OpenAI çağrı noktası)
                                               │
                                               ▼
                                  SQLite (database/) — 21 tablo
                                    points_ledger (append-only mantığı)
                                    UNIQUE kısıtlarıyla çifte ödül imkânsız
```

**AI mimari kuralı:** `engine/llm_adapter.py` dışında hiçbir dosya OpenAI
çağrısı yapamaz. `llm_call()` hata/kapalı durumda `None` döner; çağıran her
motor deterministik yoluna düşer. `LLM_ENABLED=false` global kill switch.

## Mühendislik Garantileri

- **Mock/simülasyon yok** — her sayı gerçek DB sorgusundan; AI fallback'leri
  bile gerçek medyan/tempo hesaplarından
- **Çifte ödül imkânsız** — UNIQUE kısıtları + `INSERT OR IGNORE` + rowcount
  guard (görev/rozet/başarım/sezon)
- **Güvenli kurallar** — koşullar whitelist parser'dan geçer; AI önerileri
  dahi aynı parser'la doğrulanır, admin onayı olmadan hiçbir şey oluşmaz
- **Anti-abuse** — izleme süresi `timeupdate` delta'larıyla ölçülür (seek
  sayılmaz), günlük video cap'i, tarihler sunucudan
- **Şeffaflık** — her AI cevabında model rozeti + evidence; cache'ler
  "önbellekten" etiketiyle görünür

## API Özeti

| Grup | Öne çıkanlar |
|---|---|
| `/api/auth` | register · login · refresh |
| `/api/users` | me · profil · public profil · şifre |
| `/api/content` | katalog · detay · AI topluluk özeti · admin CRUD |
| `/api/watch` | session start/end/heartbeat (canlı değerlendirme) |
| `/api/challenges` | aktif görevler + ilerleme · admin CRUD · **ai-suggest** |
| `/api/ai` | chat · daily-plan · weekly-report · digest · recommendations · explain |
| `/api/social` | follow · feed · trending · rivalry · yorum/oylama |
| `/api/seasons` | current · history (lazy finalization) |
| `/api/achievements` | mine · stats |
| `/api/search` | birleşik arama · **ai (doğal dil)** |
| `/api/notifications` | SSE stream · kalıcı liste · okundu yönetimi |
| `/api/pipeline` | run · metrics · **insights (AI)** |

## Teknoloji

FastAPI · SQLite · OpenAI GPT-4o · Vanilla JS (framework'süz) · GSAP + Lenis
· SSE · JWT (HS256) · PWA (service worker, API'ye asla dokunmaz)
