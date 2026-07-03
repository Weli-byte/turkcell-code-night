# Rule Engine

Challenge koşullarının nasıl tanımlandığını, değerlendirildiğini ve ödül
seçiminin nasıl yapıldığını tanımlar.

## Koşul Sözdizimi

Bir challenge koşulu tam olarak şu biçimdedir:

```text
alan operatör tamsayı
```

Örnekler:

```text
watch_minutes_today >= 60
episodes_completed_today >= 3
watch_streak_days > 7
unique_genres_today == 2
```

- `eval()` **kullanılmaz**; koşullar regex tabanlı güvenli parser ile
  (`rules/condition_parser.py`) ayrıştırılır.
- Sağ taraf yalnızca tamsayı literal olabilir (negatif dahil).
- Bileşik koşullar (AND/OR) MVP'de desteklenmez (bkz. backlog).
- Biçime uymayan veya whitelist dışı alan içeren koşullar
  `RuleEvaluationError` üretir.

### Desteklenen Operatörler

`>=`, `>`, `<=`, `<`, `==`, `!=`

### Desteklenen Alanlar (whitelist)

Alan listesi `DailyUserState.to_rule_context()` tarafından tanımlanır:

| Alan | Anlamı |
|---|---|
| `watch_minutes_today` | Çalışma günündeki izleme dakikası |
| `watch_minutes_7d` | Son 7 gün (run_date dahil) toplam izleme dakikası |
| `episodes_completed_today` | Bugün tamamlanan bölüm sayısı |
| `episodes_completed_7d` | Son 7 gün tamamlanan bölüm sayısı |
| `unique_genres_today` | Bugün izlenen benzersiz tür sayısı |
| `watch_party_minutes_today` | Bugünkü watch party dakikası |
| `ratings_today` | Bugün verilen puanlama sayısı |
| `ratings_7d` | Son 7 gün verilen puanlama sayısı |
| `watch_streak_days` | Kesintisiz izleme günü serisi |

## Değerlendirme Akışı

1. `challenge_repository` aktif challenge'ları filtreler
   (`is_active=false` olanlar hiç değerlendirilmez).
2. `evaluator` her kullanıcı state'i için koşulları değerlendirir ve
   tetiklenen challenge listesi üretir.
3. `reward_selector` tetiklenenler arasından **tek** ödül seçer.

## Öncelik ve Tie-Break

- **Düşük `priority` sayısı = yüksek öncelik.** (priority 1, priority 5'i
  yener.)
- Eşit öncelikte tie-break: **alfabetik olarak küçük `challenge_id`** seçilir.
- Seçilmeyen tetiklenmiş challenge'lar `RewardEvent.suppressed_challenge_ids`
  içinde raporlanır; açıklama katmanı "neden alamadım" sorusunu buradan
  cevaplar.
- Bir kullanıcı **günde en fazla bir** ödül alır; aynı challenge farklı
  günlerde tekrar kazanılabilir. Aynı gün + aynı kullanıcı + aynı challenge
  için ledger duplicate guard tekrar puan yazılmasını engeller.

## Yeni Challenge Ekleme

Kod değişikliği gerekmez; `challenges.csv`'ye satır eklemek yeterlidir:

```csv
challenge_id,challenge_name,challenge_type,condition,reward_points,priority,is_active
CH-007,Tur Kasifi,DAILY,unique_genres_today >= 3,120,4,true
```

Kontrol listesi:

- [ ] `challenge_id` benzersiz (duplicate ID ingestion'da reddedilir).
- [ ] `condition` desteklenen alan + operatör + tamsayı biçiminde.
- [ ] `reward_points` ve `priority` pozitif.
- [ ] `challenge_type` geçerli: `DAILY`, `WEEKLY`, `STREAK`.
- [ ] Golden testler etkileniyorsa (fixture challenge'ları değiştiyse)
      goldenları yeniden üret (bkz. testing_and_determinism.md).

## Yeni Koşul Alanı Ekleme

Yeni bir metrik üzerinden kural yazılabilmesi için:

1. Metriği `state/metrics.py` içinde hesapla.
2. `DailyUserState` modeline alanı ekle (`domain/models.py`) ve
   `to_rule_context()` sözlüğüne kaydet — whitelist budur.
3. `ingestion` gerekiyorsa yeni CSV kolonunu parse et.
4. Unit test ekle; golden çıktılar değişeceği için goldenları yeniden üret.

## Yeni Rozet Ekleme

Rozet eşikleri `config/badge_config.py` içindedir:

```python
BADGE_THRESHOLDS = (
    BadgeThreshold(BadgeType.BRONZE, 500),
    BadgeThreshold(BadgeType.SILVER, 1500),
    BadgeThreshold(BadgeType.GOLD, 3000),
)
```

Yeni seviye için `BadgeType` enum'ına değer ekle, eşiği artan puan sırasında
listeye yerleştir. Badge engine eşiği geçen kullanıcıya eksik kalan tüm alt
rozetleri de verir; aynı rozet ikinci kez verilmez.
