# Operasyon Rehberi

Günlük batch çalıştırma akışını, geçmiş dosyalarının devrini, hata
davranışını ve CLI sözleşmesini tanımlar.

## Günlük Batch Akışı

Sistem günde bir kez, o günün `run_date`'i ile çalıştırılır:

```bash
gamification-engine run \
  --activities data/input/user_activities.csv \
  --challenges data/input/challenges.csv \
  --output-dir data/output \
  --run-date 2026-07-01
```

Pipeline adımları sırasıyla: CSV yükleme → geçmiş yükleme (ledger, badges,
notifications) → state hesaplama → challenge değerlendirme → ödül seçimi →
ledger append → rozet atama → leaderboard → bildirim üretimi → JSON export.

### Çıktı Dosyaları

| Dosya | İçerik | Yazma davranışı |
|---|---|---|
| `states.json` | Çalışma günündeki kullanıcı state'leri | Her çalıştırmada üzerine yazılır |
| `rewards.json` | Bu çalıştırmada seçilen ödüller | Üzerine yazılır |
| `ledger.json` | **Tüm** puan geçmişi | Append-only birikir |
| `badges.json` | Tüm rozet atamaları | Birikir (duplicate guard) |
| `leaderboard.json` | Güncel sıralama | Üzerine yazılır |
| `notifications.json` | Tüm bildirimler | Birikir (duplicate guard) |
| `run_summary.json` | Çalıştırma özeti | Üzerine yazılır |

### Geçmiş Dosyalarının Devri

Varsayılan olarak pipeline geçmişi (`ledger.json`, `badges.json`,
`notifications.json`) **aynı `--output-dir` içinden** okur. Ardışık günleri
aynı dizine çalıştırmak yeterlidir; puanlar ve rozetler otomatik birikir.

Geçmişi farklı bir yerden beslemek için:

```bash
gamification-engine run ... \
  --existing-ledger path/to/ledger.json \
  --existing-badges path/to/badges.json \
  --existing-notifications path/to/notifications.json
```

Geçmiş dosyası hiç yoksa sistem boş geçmişle başlar (ilk gün senaryosu).

### İdempotentlik

Aynı günü aynı dizine tekrar çalıştırmak güvenlidir:

- Ledger duplicate guard aynı ödülü ikinci kez yazmaz.
- Badge duplicate guard aynı rozeti ikinci kez vermez.
- Notification duplicate guard bildirimleri çoğaltmaz.

Geçmiş bir günü sonraki günlerden sonra yeniden çalıştırmak da geçmişi bozmaz
(otomatik test: `tests/integration/test_determinism.py`).

## Hata Davranışı ve Exit Kodları

| Exit kodu | Anlamı |
|---|---|
| `0` | Başarılı |
| `1` | Hata: geçersiz `--run-date`, eksik/bozuk input dosyası, pipeline hatası, explain yükleme hatası |
| `2` | argparse kullanım hatası (eksik zorunlu argüman) |

- Pipeline **partial failure'da durur**: herhangi bir adım başarısız olursa
  hiçbir çıktı "yarım" bırakılmaz, hata `stderr`'e `Pipeline Error: ...`
  olarak yazılır.
- Ingestion strict'tir: eksik header, hatalı tip, negatif değer veya
  duplicate challenge ID tüm çalıştırmayı durdurur.

## explain Komutu

`explain` bir `run` çıktısı üzerinde çalışır (önce `run` çalıştırılmalıdır):

```bash
gamification-engine explain \
  --user-id u001 \
  --question "Kaç puanım var?" \
  --output-dir data/output \
  --challenges data/input/challenges.csv \
  --format json   # veya text (varsayılan)
```

## LLM Ortam Değişkenleri

| Değişken | Etki |
|---|---|
| `GEMINI_API_KEY` | Gemini ile cevap yeniden ifade etme (öncelikli) |
| `OPENAI_API_KEY` | OpenAI ile yeniden ifade etme |
| `GAMIFICATION_LLM_ENABLED=0` | Kill switch — anahtarlar olsa bile LLM kapalı |

LLM hiçbir `run` çıktısını etkilemez; yalnızca `explain` cevabının metnini
değiştirebilir. Hata durumunda deterministik cevap döner.

## Loglama

Pipeline `logging` modülüyle `INFO` seviyesinde adım logları üretir
(handler yapılandırması çağırana bırakılmıştır). CLI çıktısı stdout'a özet,
stderr'e hata yazar.
