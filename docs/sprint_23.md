# Sprint 23 — Canlı Değerlendirme Motoru (Faz 2)

Projenin kalbi: her kabul edilen event'te deterministik motor çalışır;
puan, rozet ve bildirim **anında** verilir.

## Akış

```text
POST /events/*  (counted=true)
  → state_builder: watch_events → DailyUserState  (saniye → dakika, 7g pencere, streak)
  → engine.evaluate_challenges_for_state          (güvenli parser, eval yok)
  → engine.select_reward                          (öncelik + challenge_id tie-break)
  → reward_events INSERT                          (UNIQUE(user_id, reward_date) = günde tek ödül)
  → points_ledger APPEND                          (append-only, source_ref=reward:<date>)
  → rozet eşik kontrolü (Bronze 500/Silver 1500/Gold 3000, motor config'i)
  → notifications INSERT (deterministik id ile dedupe) → SSE broker'a publish
```

Tüm iş kararları motorun saf fonksiyonlarında; backend yalnızca veri
taşır ve kalıcılaştırır.

## Yeni modüller

| Modül | Sorumluluk |
|---|---|
| `services/state_builder.py` | DB event'lerinden motorun `DailyUserState`'i: bugün+7g toplamları, distinct tür sayısı (video join), ardışık izleme günü serisi. Tam sayı bölmesi (motor kuralı). |
| `services/live_evaluator.py` | Yukarıdaki akış; `LiveEvaluationResult(reward, new_badges, notifications)`. |
| `services/notifier.py` | Thread-safe in-process `NotificationBroker` (kullanıcı başına SSE kuyrukları) + `format_sse`. Tek süreç; çoklu worker için Redis pub/sub backlog'da. |
| `repositories/rewards.py` | `reward_events` tablosu; `UNIQUE(user_id, reward_date)` "günde tek ödül" kuralını DB seviyesinde garanti eder. |
| `repositories/badges.py`, `repositories/notifications.py` | Check-first + IntegrityError fallback dedupe. |
| `api/sse.py` | `GET /sse/notifications?token=...` — EventSource header koyamadığı için token query'de; keepalive yorumları; kopuşta unsubscribe. |

## Yeni/geliştirilen endpoint'ler

- `POST /events/*` yanıtı artık `reward {challenge_id, challenge_name,
  points}` ve `new_badges` içerir — player anında kutlama gösterebilir.
- `GET /me/points` — toplam + append-only işlem geçmişi.
- `GET /me/badges`, `GET /me/notifications`.
- `GET /me/challenges` — aktif challenge'lar canlı ilerlemeyle:
  `progress_current/target/percent`, `satisfied`, `won_today`. Koşullar
  motorun güvenli parser'ıyla çözülür.

## Kritik tasarım kararı: canlı modda "günde tek ödül"

Gün içinde ilk tetiklenen değerlendirmede motor, o an tetiklenen
challenge'lar arasından öncelikle seçer ve ödül verilir; gün boyu ikinci
ödül `UNIQUE(user_id, reward_date)` ile imkânsızdır. Gün sonu batch'i
(S24) eksik kalan ödülleri tamamlayacak, asla çelişmeyecek.

## Testler (22 yeni; toplam 275, coverage %93.84)

- state_builder: boş state, tam sayı bölmesi, 7g penceresi sınırı, bölüm/
  puanlama sayımları, distinct tür, watch-party dakikası, streak (ardışık +
  bugün izlenmediyse 0).
- live evaluation e2e: 60 dk → CH-001 +80p anında; eşik altı → ödül yok;
  günde tek ödül; 300 dk → CH-004 800p + BRONZE rozet aynı yanıtta;
  bildirimler saklanıyor; /me/challenges ilerleme (30 dk → %50) ve
  won_today bayrağı; tüm /me uçları auth zorunlu.
- notifier: kullanıcı izolasyonu, çoklu abone, unsubscribe idempotent,
  SSE format; SSE endpoint geçersiz token 401 / token'sız 422.

## Kalite kapıları

ruff + mypy strict temiz. Canlı smoke: 12 heartbeat ile 60 dk izleme →
"Gunun Izleyicisi +80p" anında, /me/points 80, won_today=true, bildirim
kayıtlı.
