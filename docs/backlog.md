# Teknik Borç ve Gelecek Backlog

Mevcut MVP'nin bilinçli sınırları ve önceliklendirilmiş gelecek işleri.

## Teknik Borç

| Konu | Detay | Etki |
|---|---|---|
| Satır sonu normalizasyonu | Repo'da `.gitattributes` yok; Windows'ta LF→CRLF uyarıları görülüyor. Golden testler normalize ederek telafi ediyor. | Düşük |
| `# type: ignore[no-untyped-def]` kullanımı | Bazı test decorator'larında (mock patch) untyped-def ignore'ları var. | Düşük |
| `chat.py` prototip kalıntısı | Eski prototip (`turkcell-code-night-main/` alt klasörü) gitignore'da; yeni kod tabanına taşınacak bir şey kalmadıysa yerelden silinebilir. | Düşük |
| Logging yapılandırması | Pipeline logger'ları handler'sız; CLI'da `--verbose` bayrağı yok. | Düşük |
| `run_summary` alan genişletme | Özet; hangi kullanıcıların ödül aldığı gibi detayları içermiyor. | Düşük |

## Gelecek Özellikler (öncelik sırasıyla)

### 1. Bileşik koşullar (AND/OR)

`watch_minutes_today >= 60 AND unique_genres_today >= 2` gibi ifadeler.
Parser bilinçli olarak tek karşılaştırmayla sınırlı tutuldu; genişletme
`condition_parser.py` içinde recursive-descent ile yapılmalı, `eval()`
yasağı korunmalı.

### 2. Badge konfigürasyonunun dosyaya taşınması

Eşikler şu an kod içinde typed config (`config/badge_config.py`). JSON/YAML
dosyasından yükleme + şema doğrulaması eklenebilir; determinizm için config
dosyası da run input'u sayılmalı.

### 3. Top-N leaderboard ve sayfalama

MVP tüm kullanıcıları listeler. `--top-n` CLI parametresi ve export desteği.

### 4. Streak tabanlı challenge türü

`ChallengeType.STREAK` enum'da mevcut ama özel davranışı yok;
`watch_streak_days` alanı üzerinden dolaylı destekleniyor. Streak kırılma
bildirimleri eklenebilir.

### 5. Notification kanalları

`NotificationChannel` enum'ında `IN_APP`, `BIP`, `EMAIL` tanımlı; MVP yalnızca
JSON kayıt üretir. Kanal bazlı şablon ve gönderim adaptörleri eklenebilir.

### 6. Çoklu dil desteği

Açıklama şablonları Türkçe. `templates.py` locale parametresiyle
genişletilebilir; LLM prompt'u da locale'e göre seçilmeli.

### 7. Artımlı state hesaplama

Her çalıştırma tüm aktivite dosyasını okur. Büyük veri için tarih aralığı
filtresi veya önceki state'ten artımlı hesaplama gerekebilir.

### 8. LLM geliştirmeleri

- Cevap loglama (deterministik + LLM cevabı yan yana, denetlenebilirlik).
- Anthropic Claude adapter'ı (`docs/ai_layer.md` "Yeni Provider Ekleme").
- LLM çıktısında sayısal değerlerin deterministik cevapla tutarlılık
  doğrulaması (post-validation guardrail).

## Faz 2 ile Teslim Edilenler (eski "kapsam dışı" maddeler)

- ✅ Web arayüzü / REST API (React SPA + FastAPI)
- ✅ Veritabanı entegrasyonu (SQLite + SQLAlchemy, append-only trigger'lar)
- ✅ Kullanıcı authentication (JWT + bcrypt)
- ✅ Gerçek zamanlıya yakın event akışı (canlı değerlendirme + SSE)

## Faz 2 Sonrası Teknik Borç

| Konu | Detay | Etki |
|---|---|---|
| SSE broker tek süreç | `NotificationBroker` in-process; çoklu uvicorn worker'da Redis pub/sub gerekir. | Orta |
| SQLite eşzamanlılık | Yüksek trafik için PostgreSQL'e geçiş (SQLAlchemy sayesinde URL değişimi + trigger portu). | Orta |
| Frontend test altyapısı | vitest + React Testing Library kurulmadı; kritik mantık backend'de testli. | Düşük |
| Docker imajları CI'da build edilmiyor | Compose dosyaları elle doğrulandı; CI'a build adımı eklenebilir. | Düşük |
| Canlı "günde tek ödül" zamanlaması | Gün içi ilk tetiklenen kazanır; batch daha yüksek öncelikliyi geriye dönük seçemez (bilinçli tasarım, docs/sprint_23.md). | Bilgi |

## Kapsam Dışı (bilinçli)

- Production observability (metrics/tracing)
- E-posta/BIP kanal gönderimi (kayıtlar üretiliyor, gönderim yok)
