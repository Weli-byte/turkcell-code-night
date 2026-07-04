# Sprint 21 — Auth ve Kullanıcı Yönetimi (Faz 2)

JWT tabanlı kimlik doğrulama; platform artık gerçek hesaplarla çalışıyor.

## Yapılanlar

### Yeni modüller

| Modül | Sorumluluk |
|---|---|
| `security.py` | bcrypt hash/verify + HS256 JWT üretme/doğrulama. FastAPI'den bağımsız saf yardımcılar; `TokenError` + `TokenPayload`. `now` parametresi test edilebilirlik için enjekte edilebilir. |
| `repositories/users.py` | `UserRepository` — create (uuid tabanlı id), get_by_username, get_by_id. |
| `api/schemas.py` | `RegisterRequest` (username 3-64 + pattern, parola min 8), `LoginRequest`, `UserResponse` (hash asla dışarı sızmaz), `TokenResponse`. |
| `api/auth.py` | `POST /auth/register` (201 + token; duplicate → 409), `POST /auth/login` (401 tek tip mesaj — kullanıcı var/yok bilgisi sızdırılmaz). |
| `api/me.py` | `GET /me` — kimliği doğrulanmış profil. |
| `api/admin.py` | `GET /admin/ping` — Sprint 27'de büyüyecek admin API'sinin çekirdeği. |

### Dependency zinciri (`api/deps.py`)

`HTTPBearer(auto_error=False)` → `get_current_user` (eksik/bozuk/expired
token → 401 + `WWW-Authenticate: Bearer`) → `get_current_admin` (rol yoksa
403). Kullanımı: `CurrentUserDep` / `AdminDep` (Annotated).

### Admin bootstrap

`GAMIFICATION_BACKEND_ADMIN_USERNAME` + `_ADMIN_PASSWORD` set edilirse
startup'ta admin hesabı bir kez oluşturulur (varsa dokunulmaz).

### Ayarlar (config.py — tek okuma noktası kuralı korunuyor)

`jwt_secret` (dev default; prod'da değiştirilmeli), `jwt_expires_minutes`
(1440), `bcrypt_rounds` (12; testlerde 4), `admin_username/password`.

## Testler (19 yeni; toplam 237, coverage %94.65)

- security: hash round-trip, salt farklılığı, token round-trip, expired /
  yanlış secret / bozuk / subject'siz token reddi.
- API e2e: register 201 + hash sızmaz, duplicate 409, kısa parola ve
  geçersiz username 422, login 200/401 (yanlış parola + bilinmeyen
  kullanıcı), /me 200/401 (token'sız + geçersiz token), admin ping 403
  (normal kullanıcı) / 200 (bootstrap'lı admin).

## Kalite kapıları

ruff + mypy strict temiz; canlı smoke test: register → /me → admin
bootstrap login → /admin/ping tamamı doğrulandı.
