# -*- coding: utf-8 -*-
"""Sprint 30 canlı denetim — gerçek HTTP + gerçek GPT, mock yok."""
import sys, json, time, uuid
import requests

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://localhost:8000"
FAILS: list[str] = []
NOTES: list[str] = []

def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(f"{name}: {detail}")

def get(path, tok=None, **kw):
    h = {"Authorization": f"Bearer {tok}"} if tok else {}
    return requests.get(BASE + path, headers=h, timeout=90, **kw)

def post(path, tok=None, body=None):
    h = {"Authorization": f"Bearer {tok}"} if tok else {}
    return requests.post(BASE + path, headers=h, json=body, timeout=120)

def delete(path, tok=None):
    h = {"Authorization": f"Bearer {tok}"} if tok else {}
    return requests.delete(BASE + path, headers=h, timeout=30)

print("=" * 60)
print("1) STATİK DOSYALAR + PWA")
for p, frag in [("/", "html"), ("/catalog.html", "html"),
                ("/sw.js", "CACHE_NAME"), ("/manifest.json", "GE Engine"),
                ("/icon.svg", "svg")]:
    r = requests.get(BASE + p, timeout=10)
    check(f"GET {p}", r.status_code == 200 and frag.lower() in r.text.lower())

print("\n2) AUTH")
uname = "denetci_" + uuid.uuid4().hex[:6]
r = post("/api/auth/register", body={"username": uname, "password": "denetim1234"})
check("register", r.status_code == 200, r.text[:80])
TOK = r.json().get("token")
r = post("/api/auth/login", body={"username": uname, "password": "denetim1234"})
check("login", r.status_code == 200 and r.json().get("token"))
TOK = r.json()["token"]
r = post("/api/auth/login", body={"username": uname, "password": "yanlis"})
check("yanlış şifre reddi", r.status_code in (400, 401), str(r.status_code))
ADMIN = post("/api/auth/login", body={"username": "admin", "password": "admin123"}).json()["token"]

print("\n3) GÜVENLİK")
check("auth'suz /users/me 401", get("/api/users/me").status_code == 401)
check("normal kullanıcı admin metrics 403",
      get("/api/pipeline/metrics", TOK).status_code == 403)
check("normal kullanıcı content admin-list 403",
      get("/api/content/admin-list", TOK).status_code == 403)
check("public stats auth'suz 200", get("/api/stats/public").status_code == 200)

print("\n4) KATALOG + DETAY")
cat = get("/api/content/catalog", TOK).json()
check("katalog dolu", len(cat) >= 8, f"{len(cat)} video")
check("katalogda avg_rating alanı", "avg_rating" in cat[0])
det = get("/api/content/bb/detail", TOK).json()
check("detay: gerçek istatistik", det["watch_count"] >= 1 and det["content"]["title"] == "Big Buck Bunny")
check("detay: sentiment bloğu", "sentiment" in det and "distribution" in det["sentiment"])
check("detay: rating_dist 5 satır", len(det["rating_dist"]) == 5)

print("\n5) İZLEME AKIŞI (yeni kullanıcı)")
r = post("/api/watch/session/start", TOK, {"content_id": "vw"})
check("session start", r.status_code == 200, r.text[:80])
sid = r.json()["session_id"]
r = post("/api/watch/session/heartbeat", TOK, {"session_id": sid})
check("heartbeat", r.status_code == 200)
time.sleep(2)
r = post("/api/watch/session/end", TOK, {"session_id": sid})
end = r.json()
check("session end", r.status_code == 200 and "new_achievements" in end and "level_up" in end,
      f"dk={end.get('watch_minutes')} puan={end.get('points_earned')}")
r = post("/api/watch/session/end", TOK, {"session_id": sid})
check("çifte end reddi", r.status_code == 400)

print("\n6) RATING + YORUM + SENTIMENT")
r = post("/api/social/rate", TOK, {"content_id": "vw", "rating": 4,
                                   "comment": "Kısa ama bilgilendirici bir inceleme videosu."})
rr = r.json()
check("rate: ilk oy bonusu", rr["is_new"] and rr["bonus_points"] == 10)
check("rate: başarım döndü (İlk Oy)", any(a["id"] == "first_rating" for a in rr.get("new_achievements", [])),
      str([a["id"] for a in rr.get("new_achievements", [])]))
time.sleep(1)
cm = get("/api/social/comments/vw", TOK).json()
sent = [c.get("sentiment") for c in cm["comments"]]
check("yorum + GPT sentiment etiketi", cm["comments"] and sent[0] in ("pozitif", "negatif", "notr"), str(sent))

print("\n7) SOSYAL")
r = post("/api/social/follow/admin", TOK)
check("follow", r.status_code == 200 and r.json()["following"])
check("kendini takip 422", post(f"/api/social/follow/{uname}", TOK).status_code == 422)
feed = get("/api/social/feed", TOK).json()
check("feed dolu", len(feed["feed"]) > 0, f"{len(feed['feed'])} olay")
tr = get("/api/social/trending", TOK).json()
check("trending", "trending" in tr)
fl = get("/api/social/friends-leaderboard", TOK).json()["leaderboard"]
check("arkadaş ligi (ben+admin)", len(fl) == 2, str([u['username'] for u in fl]))

print("\n8) RIVALRY (gerçek GPT)")
rv = get(f"/api/social/rivalry/admin", TOK).json()
check("rivalry analizi", len(rv["answer"]) > 30 and rv["evidence"]["comparison"]["leader"] == "admin",
      f"llm={rv['llm_enhanced']}")
check("kendinle rivalry 422", get(f"/api/social/rivalry/{uname}", TOK).status_code == 422)

print("\n9) AI PAKETİ (gerçek GPT)")
ex = post("/api/ai/explain", TOK, {"question": "Kaç puanım var?"}).json()
check("explain: intent + evidence", ex["intent"] == "points_query" and "total_points" in ex["evidence"],
      f"llm={ex['llm_enhanced']}")
c1 = post("/api/ai/chat", TOK, {"question": "Bugün ne yapmalıyım?"}).json()
check("chat tur1", len(c1["answer"]) > 20, f"intent={c1['intent']}")
c2 = post("/api/ai/chat", TOK, {"question": "Peki bunlardan hangisi en çok puan verir?"}).json()
check("chat tur2 hafıza", c2["history_used"] >= 2, f"history={c2['history_used']}")
dp1 = get("/api/ai/daily-plan", TOK).json()
dp2 = get("/api/ai/daily-plan", TOK).json()
check("daily-plan üret + cache", dp1["cached"] == False and dp2["cached"] == True and dp1["answer"] == dp2["answer"])
rec = get("/api/ai/recommendations", TOK).json()
check("recommendations", len(rec["videos"]) > 0, f"llm={rec['llm_enhanced']}")
tips = get("/api/ai/challenge-tips", TOK).json()
check("challenge-tips", len(tips["tips"]) > 0)
wr = get("/api/ai/weekly-report", TOK).json()
check("weekly-report", "this_week_minutes" in wr["evidence"])

print("\n10) ARAMA")
s = get("/api/search?q=bunny", TOK).json()
check("klasik arama", any("Bunny" in v["title"] for v in s["videos"]))
ai_s = get("/api/search/ai?q=" + requests.utils.quote("10 dakikadan kısa otomobil videoları"), TOK).json()
check("AI arama: filtre + sonuç",
      ai_s["results"] and all(v["duration_minutes"] <= 10 and v["genre"] == "otomobil" for v in ai_s["results"]),
      ai_s["filter_summary"])

print("\n11) SEZON + BAŞARIM + SEVİYE")
sez = get("/api/seasons/current", TOK).json()
check("sezon current", sez["season_id"].startswith("20") and "standings" in sez)
hist = get("/api/seasons/history", TOK).json()
check("sezon history", len(hist["seasons"]) >= 1)
ach = get("/api/achievements/mine", TOK).json()
earned = [a["id"] for a in ach["achievements"] if a["earned"]]
check("başarımlar (izleme+oy+yorum+sohbet sonrası)", len(earned) >= 3, str(earned))
me = get("/api/users/me", TOK).json()
check("me: level bloğu", "level" in me and me["level"]["level"] >= 0)

print("\n12) BİLDİRİMLER")
nl = get("/api/notifications/list", TOK).json()["notifications"]
check("kalıcı bildirimler (başarım vs.)", len(nl) >= 1, f"{len(nl)} kayıt")
uc = get("/api/notifications/unread-count", TOK).json()["count"]
r = post("/api/notifications/read", TOK, {"all": True})
check("tümü okundu", r.json()["marked"] == uc and
      get("/api/notifications/unread-count", TOK).json()["count"] == 0)

print("\n13) SSE CANLI AKIŞ")
try:
    with requests.get(f"{BASE}/api/notifications/stream?token={TOK}", stream=True, timeout=8) as sr:
        first = next(sr.iter_lines(decode_unicode=True))
        check("SSE connected eventi", "connected" in (first or ""), str(first)[:60])
except Exception as e:
    check("SSE connected eventi", False, str(e)[:80])

print("\n14) WATCH PARTY")
p = post("/api/party/create", TOK, {"content_id": "bb"}).json()
check("parti kur", len(p["room_code"]) == 6)
j = post("/api/party/join", ADMIN, {"room_code": p["room_code"]}).json()
check("partiye katıl (admin)", len(j["members"]) == 2)
room = get(f"/api/party/room/{p['room_code']}", TOK).json()
check("oda durumu", room["is_active"] and len(room["members"]) == 2)
r = post("/api/party/end", TOK, {"room_code": p["room_code"]})
check("parti bitir (host)", r.json()["ended"])

print("\n15) LEADERBOARD")
lb = get("/api/leaderboard", TOK).json()
check("tüm zamanlar", lb["leaderboard"][0]["username"] == "admin" and "my_rank" in lb)
wk = get("/api/leaderboard/weekly", TOK).json()
check("haftalık + countdown", "seconds_left" in wk)
st = get("/api/leaderboard/streaks", TOK)
check("streaks", st.status_code == 200)

print("\n16) ADMİN PAKETİ (gerçek GPT)")
m = get("/api/pipeline/metrics", ADMIN).json()
check("metrics", m["total_users"] >= 8)
ins = get("/api/pipeline/insights", ADMIN).json()
check("AI insights + sentiment metriği",
      len(ins["answer"]) > 50 and "community_sentiment" in ins["metrics"],
      f"llm={ins['llm_enhanced']}")
cl = get("/api/content/admin-list", ADMIN).json()
check("content admin-list istatistikli", "watch_count" in cl[0])
sug = post("/api/challenges/ai-suggest", ADMIN).json()
check("AI görev önerileri (parser'dan geçmiş)",
      len(sug["suggestions"]) >= 1 and all(s["valid"] for s in sug["suggestions"]),
      f"llm={sug['llm_enhanced']} n={len(sug['suggestions'])}")
ast = get("/api/achievements/stats", ADMIN).json()
check("başarım istatistikleri", ast["total_users"] >= 8)

print("\n17) PROFİL + PUBLIC")
prof = get("/api/users/me/profile", TOK).json()
check("tam profil (level+takip+haftalık)", all(k in prof for k in ("level", "follower_count", "weekly")))
pub = get("/api/users/public/admin", TOK).json()
check("public profil (is_following)", pub["is_following"] == True and "level" in pub)

print("\n" + "=" * 60)
print(f"SONUÇ: {('TÜM TESTLER GEÇTİ' if not FAILS else str(len(FAILS)) + ' HATA')}")
for f in FAILS:
    print("  ✗", f)
