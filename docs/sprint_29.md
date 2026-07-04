# Sprint 29 — AI Açıklama Entegrasyonu (Faz 2)

v1'in deterministik açıklama motoru artık canlı veritabanından besleniyor
ve dashboard'da bir sohbet kutusuyla kullanılıyor.

## Backend

- `services/explain.py` — DB kayıtlarını motorun domain modellerine çevirir
  (ledger → `PointsLedgerEntry`, rozetler → `BadgeAssignment`, canlı
  leaderboard → `LeaderboardEntry`, ödüller → `RewardEvent`, challenge'lar →
  `ChallengeDefinition`, bugünkü state → `DailyUserState`) ve
  `explain_user_query`'ye verir.
- **Kimlik eşlemesi**: tüm domain nesneleri internal uuid yerine
  `username` ile kurulur — cevap ve evidence, kullanıcının leaderboard'da
  gördüğü isimleri referanslar ("bir üst sıradaki kullanıcı (ayse)...").
- LLM adapter zinciri korunur: cevap her zaman deterministik üretilir,
  yapılandırılmışsa LLM yalnızca dilsel cilalar; hata → deterministik
  fallback. `GAMIFICATION_LLM_ENABLED=0` kill switch geçerli.
- `POST /explain` (auth): `{question}` → `{user_id, question, answer,
  evidence}`. Soru 3-300 karakter; kullanıcı yalnızca **kendi** verisini
  sorgulayabilir (user token'dan gelir).

## Frontend (`ExplainBox`, dashboard'da)

- "🤖 AI Asistan" kartı: hazır soru chip'leri (Kaç puanım var? / Neden bu
  sıradayım? / Gold'a ne kadar kaldı? / Neden bu ödülü kazandım?) + serbest
  soru girişi.
- Cevaplar sohbet geçmişi olarak birikir; her cevabın altında açılabilir
  **Kanıt (evidence)** bölümü ham JSON'u gösterir — "cevap uydurma değil,
  veriden" mesajı.

## Testler (7 yeni; toplam 322, coverage %94.28)

Auth 401; puan sorusu (cevapta 80 + evidence.total_points); sıra sorusu
(rank 1, username'li); rozet sorusu (GOLD + current_points); bilinmeyen
soru kontrollü fallback; sıfır veri kullanıcısı; kısa soru 422. Autouse
fixture LLM'i kapatır — testler ortam değişkenlerinden bağımsız.

## Kalite kapıları

ruff + mypy strict + `npm run build` temiz. Canlı smoke: 60 dk izleme →
"Kaç puanım var?" → "Şu ana kadar toplam 80 puan kazandınız." (evidence 80);
"Gold rozetine ulaşmak için ne yapmalıyım?" → "3000 puana ihtiyacınız var…
2920 puan daha kazanmalısınız."
