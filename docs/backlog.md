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

## Kapsam Dışı (bilinçli)

- Gerçek zamanlı event streaming
- Web arayüzü / REST API
- Veritabanı entegrasyonu (dosya tabanlı depolama yeterli)
- Kullanıcı authentication
- Production observability (metrics/tracing)
