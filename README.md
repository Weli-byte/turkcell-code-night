# Deterministic Gamification Engine

Dijital video platformları için modüler, **deterministik** bir Python
oyunlaştırma motoru. Günlük kullanıcı aktivite CSV'lerini işler; kullanıcı
durumunu hesaplar, challenge kurallarını değerlendirir, puanları append-only
ledger'da tutar, rozet atar, deterministik leaderboard üretir ve kullanıcı
sorularına veri temelli açıklamalar verir.

**Temel garanti:** Aynı girdi + aynı çalışma tarihi ⇒ her zaman bayt düzeyinde
aynı çıktı. `random` yok, sistem saati yok, `eval()` yok. LLM yalnızca
opsiyonel bir "cevabı daha doğal ifade etme" katmanıdır — hiçbir iş kararı
LLM'e bırakılmaz.

## Kurulum

Gereksinim: Python 3.11+

```bash
python -m pip install -e ".[dev]"
```

## Hızlı Başlangıç

Örnek veri `data/input/` altında hazırdır. Günlük batch çalıştırma:

```bash
gamification-engine run \
  --activities data/input/user_activities.csv \
  --challenges data/input/challenges.csv \
  --output-dir data/output \
  --run-date 2026-07-01
```

Çıktı (`data/output/` altına 7 JSON dosyası yazılır):

```text
Pipeline completed successfully.
Run Date:                  2026-07-01
Total Users Processed:     6
Total Rewards Generated:   5
Total Ledger Entries:      9
Total Badges Assigned:     2
Total Notifications:       11
Leaderboard Size:          5
```

Aynı output dizinine ardışık günler çalıştırıldığında ledger ve rozetler
birikir (örnek çıktılar 2026-06-29 → 07-01 arası üç günlük çalıştırmanın
sonucudur). Aynı günü tekrar çalıştırmak güvenlidir: ledger append-only'dir
ve duplicate guard idempotentlik sağlar.

### Canlı Platform (Faz 2 — API + React SPA)

Proje artık gerçek zamanlı çalışan bir video platformu içerir: kayıt ol,
video izle, puanı **izlerken** kazan.

```bash
uvicorn gamification_backend.main:app     # API → http://127.0.0.1:8000 (Swagger: /docs)
cd frontend && npm install && npm run dev # SPA → http://localhost:5173
```

Player gerçek izleme süresini ölçer (seek/pause sayılmaz), 15 sn'de bir
motora raporlar; challenge eşiği aşıldığı anda ödül ve rozet bildirimi
düşer. Ayrıntılar: `docs/v2_plan.md` ve `docs/sprint_2X.md` kayıtları.

### Eski Landing (v1 batch demo)

Proje, motoru canlı sorgulayan tek dosyalık bir landing page ile gelir:

```bash
python server.py
# → http://localhost:8000
```

`server.py` (yalnızca stdlib) statik sayfayı sunar ve motor çıktılarını
küçük bir JSON API ile köprüler: `/api/summary`, `/api/leaderboard`,
`/api/badges` ve `/api/explain?user_id=u001&question=...`. Sayfadaki
leaderboard tablosu `data/output/leaderboard.json`'dan canlı beslenir;
"AI Açıklama" bölümündeki interaktif demo her soruda deterministik motoru
çağırır. `index.html` çift tıkla da açılır — API yoksa statik örnek
verilerle çalışır.

### Açıklama Sorgulama (explain)

```bash
gamification-engine explain \
  --user-id u001 \
  --question "Gold rozetine ulaşmak için ne yapmalıyım?" \
  --output-dir data/output \
  --challenges data/input/challenges.csv
```

```text
GOLD rozetine ulaşmak için 3000 puana ihtiyacınız var. Şu anda 1560 puanınız var. 1440 puan daha kazanmalısınız.
```

`--format json` ile cevap, kanıt (evidence) alanlarıyla birlikte döner:

```json
{
  "user_id": "u002",
  "question": "Liderlik tablosunda neden bu sıradayım?",
  "answer": "Liderlik tablosunda 3. sıradasınız. Toplam 280 puanınız var. Bir üst sıradaki kullanıcı (u003) ile aranızda 20 puan fark var.",
  "evidence": {
    "rank": 3,
    "total_points": 280,
    "next_user_id": "u003",
    "points_to_next": 20
  }
}
```

Desteklenen soru tipleri: puan durumu, liderlik sırası, rozet gereksinimi,
"neden bu ödülü kazandım / kazanamadım". Bilinmeyen sorular kontrollü bir
fallback cevabı alır.

### Opsiyonel LLM Katmanı

Deterministik cevap her zaman üretilir; API anahtarı tanımlıysa LLM cevabı
yalnızca **dilsel olarak** yeniden ifade eder:

```bash
export GEMINI_API_KEY=...        # veya OPENAI_API_KEY (Gemini öncelikli)
export GAMIFICATION_LLM_ENABLED=0  # kill switch: LLM'i tamamen kapat
```

LLM hatasında veya kapalıyken sistem deterministik cevapla devam eder.
Detay: [docs/ai_layer.md](docs/ai_layer.md)

## Girdi Formatı

`user_activities.csv`:

```csv
event_id,user_id,date,shows_watched,unique_genres,watch_minutes,episodes_completed,watch_party_minutes,ratings
EV-001,u001,2026-07-01,S1|S2,2,320,4,0,0
```

`challenges.csv`:

```csv
challenge_id,challenge_name,challenge_type,condition,reward_points,priority,is_active
CH-004,Maraton Gunu,DAILY,watch_minutes_today >= 300,800,1,true
```

Koşul sözdizimi `alan operatör tamsayı` biçimindedir (örn.
`watch_minutes_7d >= 600`); desteklenen alanlar ve kurallar için
[docs/rule_engine.md](docs/rule_engine.md). Düşük `priority` değeri yüksek
önceliktir; bir kullanıcı günde tek ödül alır, diğer tetiklenen challenge'lar
suppress edilir.

## Geliştirme

```bash
pytest              # 193 test + coverage kapısı (fail-under=85)
ruff check src tests
ruff format src tests
mypy                # strict mod
```

CI (GitHub Actions) her push/PR'da Python 3.11 ve 3.12 üzerinde lint, format,
type-check ve testleri çalıştırır.

## Mimari

```text
CSV ingestion → state engine → rule engine → points ledger (append-only)
             → badge engine → leaderboard → notifications → JSON export
                                          → explanation layer (+ opsiyonel LLM)
```

Her modül tek sorumluluğa sahiptir; pipeline yalnızca orkestrasyon yapar.
Rozet eşikleri: Bronze 500, Silver 1500, Gold 3000
(`src/gamification_engine/config/badge_config.py`).

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Mimari ve modül sorumlulukları |
| [docs/data_contracts.md](docs/data_contracts.md) | Domain modelleri ve veri kontratları |
| [docs/rule_engine.md](docs/rule_engine.md) | Koşul sözdizimi, tie-break, yeni challenge ekleme |
| [docs/ai_layer.md](docs/ai_layer.md) | Açıklama katmanı, LLM adapter, prompt contract |
| [docs/operations.md](docs/operations.md) | Günlük batch akışı, hata kodları, geçmiş dosyaları |
| [docs/testing_and_determinism.md](docs/testing_and_determinism.md) | Determinizm garantileri, golden file süreci, edge case matrisi |
| [docs/agent_guide.md](docs/agent_guide.md) | AI coding agent'lar için katkı rehberi |
| [docs/backlog.md](docs/backlog.md) | Teknik borç ve gelecek özellikler |

## Mühendislik İlkeleri

- Deterministik çıktı; tüm sıralamalarda açık tie-break.
- Append-only points ledger; update/delete yok.
- Kurallar güvenli parser ile değerlendirilir; `eval()` kullanılmaz.
- LLM iş kararı veremez; yalnızca açıklamayı yeniden ifade eder.
- Her modülde type hint, docstring, unit test; mypy strict + ruff temiz.
