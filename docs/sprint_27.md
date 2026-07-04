# Sprint 27 — Admin Paneli (Faz 2)

Challenge yönetimi, kullanıcı listesi, koşu geçmişi ve simülatör iskeleti.

## Backend (`api/admin.py` genişledi)

| Endpoint | İşlev |
|---|---|
| `GET /admin/challenges` | Pasifler dahil tüm challenge'lar (öncelik + id sıralı). |
| `POST /admin/challenges` | Yeni challenge; **koşul motorun güvenli parser'ından geçmeden hiçbir şey yazılmaz** (`services/condition_validation.py`). Duplicate id → 409. |
| `PUT /admin/challenges/{id}` | Kısmi güncelleme (verilmeyen alanlar korunur); koşul yine doğrulanır; bilinmeyen id → 404. Yalnızca **gelecek** değerlendirmeleri etkiler — verilmiş ödüller append-only ledger'da, asla değişmez. |
| `GET /admin/users` | Tüm hesaplar puan toplamlarıyla (username sıralı, bot/admin bayraklı). |
| `GET /admin/simulator` | Durum iskeleti (S28'de start/stop gelecek). |

`condition_validation.allowed_condition_fields()` whitelist'i sıfır değerli
bir `DailyUserState.to_rule_context()`'ten türetir — motor alan ekleyince
otomatik senkron kalır, eval yasağı korunur.

## Frontend (`/admin`, yalnızca admin görür)

Sekmeli panel:

- **Challenge'lar** — tablo + oluştur/düzenle formu. Form alanları: id,
  isim, tür (DAILY/WEEKLY/STREAK), koşul, puan, öncelik, aktiflik. Geçersiz
  koşulda backend'in Türkçe 422 mesajı formda gösterilir.
- **Kullanıcılar** — üye/admin/bot rolleri + puan toplamları.
- **Koşular** — run geçmişi + "▶ Batch'i şimdi çalıştır" (sonuç toast'la
  özetlenir: kullanıcı/ödül/rozet sayıları).
- **Simülatör** — durum kartı (S28 placeholder).

Navbar'da "Admin" linki yalnızca `is_admin` kullanıcıda; admin olmayan
`/admin`'e girerse ana sayfaya yönlendirilir (backend zaten 403 döner).

## Testler (15 yeni; toplam 307, coverage %93.88)

Koşul doğrulama helper'ı (eval girişimi, bilinmeyen alan, alan-alan
karşılaştırması reddi); liste pasifleri içerir; normal kullanıcıya tüm admin
uçları 403; create 201/409/422 (güvensiz koşul + sıfır puan); partial
update alan koruması; update koşul doğrulaması; 404; pasife çekilen
challenge'ın kullanıcı görünümünden düşmesi; kullanıcı listesi sıralama +
toplamlar; simülatör iskeleti.

## Kalite kapıları

ruff + mypy strict temiz; `npm run build` temiz (232 kB / 73 kB gzip).
Canlı smoke: admin login → CH-100 oluşturuldu → `__import__` koşulu 422 ile
reddedildi → kullanıcı listesi + simülatör durumu doğrulandı.
