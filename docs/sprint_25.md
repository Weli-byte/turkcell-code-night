# Sprint 25 — React SPA Temeli + Video Platformu (Faz 2)

Kullanıcının sistemi gerçekten *kullandığı* arayüz: kayıt ol, giriş yap,
katalogdan video seç, izle — izlediğin her saniye motora rapor edilir.

## Stack

- Vite 5 + React 18 + TypeScript (strict) — `frontend/`
- React Router 6 (korumalı rotalar), TanStack Query 5 (server state)
- Ekstra UI kütüphanesi yok; tek `styles.css` (koyu tema + yeşil aksan,
  landing estetiği taşındı)
- Dev'de Vite proxy → `http://127.0.0.1:8000` (CORS'suz); ayrıca backend'e
  CORSMiddleware eklendi (`GAMIFICATION_BACKEND_CORS_ORIGINS`, virgüllü)

## Sayfalar

| Rota | İçerik |
|---|---|
| `/login`, `/register` | Auth ekranları; başarıda token localStorage'a, profil context'e. |
| `/` (korumalı) | Katalog: filmler grid'i + diziler (bölümler izleme sırasında), tür etiketleri. |
| `/watch/:videoId` (korumalı) | HTML5 player + yıldızlı puanlama + ödül toast'ları. |

Navbar: canlı puan chip'i (`/me/points`, 30 sn'de bir + event sonrası
invalidate), kullanıcı adı, çıkış.

## İzleme ölçümü (sprintin kalbi — `WatchPage.tsx`)

- `timeupdate` delta'ları yalnızca video normal ilerlerken birikir
  (`0 < delta < 2sn`) — **seek etmek, duraklatmak veya sekmeyi açık
  bırakmak izleme sayılmaz**.
- Biriken saniyeler 15 sn'de bir heartbeat olarak gönderilir; pause /
  sayfadan ayrılma / bitiş anında da flush edilir (istek başına ≤300 sn,
  backend sınırıyla uyumlu).
- `ended` → `POST /events/complete`; yıldızlar → `POST /events/rating`.
- Event yanıtındaki `reward` / `new_badges` anında toast olarak kutlanır
  ve puan chip'i tazelenir.

## Çalıştırma

```bash
uvicorn gamification_backend.main:app          # API :8000
cd frontend && npm install && npm run dev      # SPA :5173 (proxy'li)
```

## Kalite kapıları

- `npm run build` = `tsc --noEmit` (strict) + vite build → temiz
  (216 kB JS / 69 kB gzip).
- Backend: ruff + mypy strict temiz; 294 test (CORS preflight + origin
  parse testleri eklendi), coverage %93.92.
- Canlı smoke: Vite :5173 sayfa 200 → proxy üzerinden health/register/
  catalog/heartbeat uçtan uca doğrulandı.

## Notlar

- `frontend/node_modules` ve `frontend/dist` gitignore'da.
- Frontend unit test altyapısı (vitest) bilinçli ertelendi; kritik iş
  mantığı backend testlerinde. S26'da bildirim merkezi SSE'ye bağlanacak.
