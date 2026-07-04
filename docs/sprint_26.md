# Sprint 26 — Kullanıcı Dashboard'u (Faz 2)

Kullanıcının oyunlaştırma durumunu canlı gördüğü katman: panel, bildirim
merkezi ve kendi satırı vurgulu liderlik tablosu.

## Yeni sayfalar / bileşenler

| Parça | İçerik |
|---|---|
| `/dashboard` (`DashboardPage`) | Profil kartı (avatar, toplam puan, rozet chip'leri 🥉🥈🥇 + kazanım tarihi), "Bugünün Challenge'ları" — her kart canlı ilerleme çubuğu (`/me/challenges`, 30 sn'de bir tazelenir), koşul metni, `won_today` olan kart yeşil vurgulu; altta append-only puan geçmişi tablosu. |
| `/leaderboard` (`LeaderboardPage`) | 15 sn'de bir tazelenen canlı tablo; ilk 3'e madalya, kendi satırın yeşil vurgulu + "sen" etiketi, botlar 🤖 işaretli; üstte "şu an #N sıradasın" özeti + CANLI nabız rozeti. |
| `NotificationBell` | Navbar zili: `/me/notifications` listesi, okunmamış sayacı (localStorage `dge_notifications_seen` ile son görülme karşılaştırması), dışarı tıklayınca kapanan dropdown. |
| `useNotificationStream` | `EventSource` ile `/sse/notifications?token=...`; gelen her bildirimde toast + points/notifications/challenges/badges/leaderboard query'lerinin invalidation'ı. Tarayıcı kopan bağlantıyı kendisi yeniler. |

## Çift bildirim çözümü

Aynı ödül iki kanaldan gelebilir: event yanıtı (WatchPage kutlaması) ve
SSE yayını. `ToastProvider.push` artık ekranda duran birebir aynı mesajı
tekrar göstermez — kullanıcı tek toast görür.

## Navbar

Katalog / Panelim / Liderlik linkleri (`NavLink` aktif-durum stiliyle),
canlı puan chip'i, bildirim zili, çıkış.

## Kalite kapıları

- `npm run build` (tsc strict + vite) temiz — 225 kB JS / 71 kB gzip.
- Backend değişmedi; süit 294 passed, coverage %93.92 (S25'ten).
- Canlı smoke: SSE stream'e bağlanıldı, 60 dk izleme eşiği aşıldığı anda
  ödül bildirimi **akış üzerinden gerçek zamanlı** alındı; `/me/notifications`
  1 kayıt; leaderboard "#1 veli 80p". (Konsol cp1254 emoji basamadı —
  payload doğru.)
