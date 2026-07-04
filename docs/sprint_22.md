# Sprint 22 — İçerik Kataloğu + Event Ingestion (Faz 2)

Girdinin gerçek kaynağı kuruldu: açık lisanslı video kataloğu ve player'ın
backend'e aktivite bildireceği event API'si.

## Katalog

- `data/input/catalog.json` — 2 dizi + 12 video (4 bağımsız film): Blender
  açık filmleri (Big Buck Bunny, Elephants Dream, Sintel, Tears of Steel) ve
  Google örnek video bucket'ındaki kısa klipler; Türkçe başlık/tür etiketleri
  (animasyon, bilim-kurgu, fantastik, macera, belgesel).
- `repositories/catalog.py` — JSON seed (idempotent, var olan satırlara
  dokunmaz) + deterministik sıralı sorgular (id / episode_number).
- `GET /catalog` (public) — diziler (bölümleri izleme sırasında) + filmler.
- `GET /catalog/videos/{id}` — tek video; yoksa 404.
- Startup lifespan'i challenges gibi kataloğu da seed'ler
  (`GAMIFICATION_BACKEND_CATALOG_JSON` ile özelleştirilebilir).

## Event ingestion (`/events/*`, hepsi auth zorunlu)

| Endpoint | Kural |
|---|---|
| `POST /events/heartbeat` | `watch_seconds` 1-300 (pydantic); video yoksa 404. |
| `POST /events/complete` | Kullanıcı+video+gün başına bir tamamlama; tekrarı `counted=false`. |
| `POST /events/rating` | 1-5 (pydantic); kullanıcı+video başına ömür boyu bir puanlama. |
| `POST /events/watch-party` | `party_seconds` 1-300; heartbeat ile aynı günlük kotayı paylaşır. |

### Güvenlik / anti-abuse tasarımı

- `user_id` asla request body'den gelmez — her event, token'daki kullanıcıya
  yazılır (başkası adına aktivite raporlanamaz).
- `event_date` her zaman sunucu tarafından atanır (UTC) — geçmiş/gelecek
  tarih göndermek imkânsız.
- Günlük izleme kotası: kullanıcı+video başına `süre × 3` saniye
  (heartbeat + watch-party toplamı). Aşan raporlar hata değil,
  `counted=false` ile sessizce yok sayılır — puan farming'i kapalı.
- `EventType` StrEnum: heartbeat / complete / rating / watch_party.

## Testler (16 yeni; toplam 253, coverage %94.85)

Katalog: seed sayıları + idempotency, `/catalog` yapısı ve sıralaması,
bölüm izleme sırası, video detay 200/404. Events: auth 401, heartbeat
saklama + sunucu tarihi, 0/-10/301 → 422, bilinmeyen video 404, günlük kota
(15s video → 45s tavan → 4. heartbeat reddedilir), complete dedupe (aynı
video false / farklı video true), rating sınırları + tek puanlama,
watch-party'nin kotayı paylaşması.

## Kalite kapıları

ruff + mypy strict temiz. Canlı smoke: catalog (2 dizi/4 film) → register →
heartbeat counted=true → complete true/duplicate false → rating true.
