"""
Achievement Engine — Sprint 19.
Tek seferlik kilometre taşı başarımları.

- Her başarımın koşulu GERÇEK DB sorgusudur (current/target) — ezber yok.
- check_achievements her çağrıda tüm tanımları tarar; UNIQUE(user_id,
  achievement_id) + INSERT OR IGNORE çifte kazanımı engeller (idempotent).
- Kazanım: user_achievements kaydı + points_ledger ödülü + kalıcı bildirim.
- Rozetlerden farkı: rozet puan eşiği, görev günlük tekrar; başarım tek sefer.
"""

from datetime import datetime
from database.setup import get_db
from api.notifications_store import push_notification

# (id, ad, açıklama, ikon, ödül puanı, progress_sql)
# progress_sql tek satır döndürür: current değeri; target sabittir.
ACHIEVEMENTS: list[dict] = [
    {
        "id": "first_watch", "name": "İlk Adım", "icon": "🎬",
        "description": "İlk videonu tamamla", "reward": 25, "target": 1,
        "sql": "SELECT COUNT(*) FROM watch_sessions WHERE user_id=? AND completed=1",
    },
    {
        "id": "binge_5", "name": "Dizi Kurdu", "icon": "📺",
        "description": "Bir günde 5 bölüm bitir", "reward": 100, "target": 5,
        "sql": ("SELECT COALESCE(MAX(day_eps),0) FROM ("
                "SELECT SUM(episodes_completed) AS day_eps FROM user_activities "
                "WHERE user_id=? GROUP BY activity_date)"),
    },
    {
        "id": "total_500min", "name": "Maratoncu", "icon": "⏱",
        "description": "Toplam 500 dakika izle", "reward": 100, "target": 500,
        "sql": "SELECT COALESCE(SUM(watch_minutes),0) FROM user_activities WHERE user_id=?",
    },
    {
        "id": "first_rating", "name": "İlk Oy", "icon": "⭐",
        "description": "İlk videonu oyla", "reward": 25, "target": 1,
        "sql": "SELECT COUNT(*) FROM content_ratings WHERE user_id=?",
    },
    {
        "id": "critic_10", "name": "Eleştirmen", "icon": "🎭",
        "description": "10 video oyla", "reward": 100, "target": 10,
        "sql": "SELECT COUNT(*) FROM content_ratings WHERE user_id=?",
    },
    {
        "id": "first_comment", "name": "İlk Yorum", "icon": "💬",
        "description": "İlk yorumunu yaz", "reward": 25, "target": 1,
        "sql": "SELECT COUNT(*) FROM content_comments WHERE user_id=?",
    },
    {
        "id": "first_follower", "name": "Sosyal Kelebek", "icon": "🦋",
        "description": "İlk takipçini kazan", "reward": 50, "target": 1,
        "sql": "SELECT COUNT(*) FROM follows WHERE following_id=?",
    },
    {
        "id": "popular_5", "name": "Popüler", "icon": "🌟",
        "description": "5 takipçiye ulaş", "reward": 150, "target": 5,
        "sql": "SELECT COUNT(*) FROM follows WHERE following_id=?",
    },
    {
        "id": "explorer", "name": "Kaşif", "icon": "🧭",
        "description": "Katalogdaki her türden en az 1 video tamamla",
        "reward": 150, "target": -1,  # target çalışma anında katalogdan gelir
        "sql": ("SELECT COUNT(DISTINCT cc.genre) FROM watch_sessions ws "
                "JOIN content_catalog cc ON cc.id = ws.content_id "
                "WHERE ws.user_id=? AND ws.completed=1"),
        "target_sql": "SELECT COUNT(DISTINCT genre) FROM content_catalog",
    },
    {
        "id": "first_party", "name": "Parti Kurucusu", "icon": "🎉",
        "description": "İlk watch party'ni kur", "reward": 50, "target": 1,
        "sql": "SELECT COUNT(*) FROM watch_parties WHERE host_user_id=?",
    },
    {
        "id": "first_chat", "name": "Meraklı", "icon": "🤖",
        "description": "AI koçla ilk sohbetini yap", "reward": 25, "target": 1,
        "sql": "SELECT COUNT(*) FROM chat_messages WHERE user_id=? AND role='user'",
    },
    {
        "id": "streak_7", "name": "Ateşli", "icon": "🔥",
        "description": "7 gün kesintisiz izle", "reward": 200, "target": 7,
        "sql": None,  # streak python tarafında hesaplanır (state_builder)
    },
    {
        "id": "level_5", "name": "Yükseliş", "icon": "🚀",
        "description": "Seviye 5'e ulaş", "reward": 150, "target": 5,
        "sql": None,  # level python tarafında hesaplanır (level_engine)
    },
    {
        "id": "season_champ", "name": "Şampiyon", "icon": "🏆",
        "description": "Bir sezonu 1. sırada bitir", "reward": 250, "target": 1,
        "sql": "SELECT COUNT(*) FROM season_results WHERE user_id=? AND rank=1 AND points>0",
    },
]


def _current_value(db, a: dict, user_id: str) -> float:
    """Başarımın anlık gerçek değeri."""
    if a["sql"]:
        row = db.execute(a["sql"], (user_id,)).fetchone()
        return float(row[0] or 0)
    if a["id"] == "streak_7":
        from engine.state_builder import build_user_state
        return float(build_user_state(user_id)["streak_days"])
    if a["id"] == "level_5":
        from engine.level_engine import get_level
        total = db.execute(
            "SELECT COALESCE(SUM(points),0) FROM points_ledger WHERE user_id=?",
            (user_id,),
        ).fetchone()[0]
        return float(get_level(int(total))["level"])
    return 0.0


def _target_value(db, a: dict) -> float:
    if a.get("target_sql"):
        return float(db.execute(a["target_sql"]).fetchone()[0] or 1)
    return float(a["target"])


def check_achievements(user_id: str) -> list[dict]:
    """
    Tüm başarımları kontrol eder; yeni kazanılanları işler ve döndürür.
    İdempotent — kazanılmış başarım tekrar işlenmez.
    """
    db = get_db()
    earned_ids = {
        r["achievement_id"] for r in db.execute(
            "SELECT achievement_id FROM user_achievements WHERE user_id=?",
            (user_id,),
        ).fetchall()
    }

    newly: list[dict] = []
    today   = datetime.now().strftime("%Y-%m-%d")
    now_iso = datetime.now().isoformat()

    for a in ACHIEVEMENTS:
        if a["id"] in earned_ids:
            continue
        current = _current_value(db, a, user_id)
        target  = _target_value(db, a)
        if current >= target and target > 0:
            cur = db.execute(
                "INSERT OR IGNORE INTO user_achievements "
                "(user_id, achievement_id, awarded_at) VALUES (?, ?, ?)",
                (user_id, a["id"], now_iso),
            )
            if cur.rowcount == 0:
                continue  # yarışta başka istek kazandı — çifte ödül yok
            db.execute(
                "INSERT INTO points_ledger "
                "(user_id, points, reason, activity_date, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, a["reward"], f"Başarım: {a['name']}", today, now_iso),
            )
            newly.append({
                "id": a["id"], "name": a["name"], "icon": a["icon"],
                "description": a["description"], "reward": a["reward"],
            })

    db.commit()
    db.close()

    for a in newly:
        push_notification(user_id, {
            "type":    "points",
            "points":  a["reward"],
            "reason":  f"{a['icon']} Başarım: {a['name']}",
        })
    return newly


def get_achievements_status(user_id: str) -> dict:
    """Tüm başarımlar: kazanılanlar (tarihli) + kilitliler (gerçek ilerlemeyle)."""
    db     = get_db()
    earned = {
        r["achievement_id"]: r["awarded_at"] for r in db.execute(
            "SELECT achievement_id, awarded_at FROM user_achievements WHERE user_id=?",
            (user_id,),
        ).fetchall()
    }

    items = []
    for a in ACHIEVEMENTS:
        target  = _target_value(db, a)
        if a["id"] in earned:
            items.append({
                "id": a["id"], "name": a["name"], "icon": a["icon"],
                "description": a["description"], "reward": a["reward"],
                "earned": True, "awarded_at": earned[a["id"]],
                "current": target, "target": target, "pct": 100.0,
            })
        else:
            current = _current_value(db, a, user_id)
            pct     = min(100.0, round(current / target * 100, 1)) if target > 0 else 0.0
            items.append({
                "id": a["id"], "name": a["name"], "icon": a["icon"],
                "description": a["description"], "reward": a["reward"],
                "earned": False, "awarded_at": None,
                "current": round(current, 1), "target": target, "pct": pct,
            })
    db.close()

    earned_count = sum(1 for i in items if i["earned"])
    return {
        "achievements": items,
        "earned_count": earned_count,
        "total_count":  len(items),
        "total_reward_earned": sum(i["reward"] for i in items if i["earned"]),
    }
