"""
Append-only points ledger.
Sadece INSERT ve SELECT kullanilir — ledger degistirilemez.
"""

from database.setup import get_db
from datetime import datetime


def append_points(
    user_id: str,
    points: int,
    reason: str,
    activity_date: str,
    challenge_id: str = None,
    session_id: str = None,
) -> int:
    """
    Ledger'a yeni puan hareketi ekler.
    Mevcut kayıtları asla güncellemez.
    Döner: eklenen kaydın id'si
    """
    db = get_db()
    cur = db.execute("""
        INSERT INTO points_ledger
        (user_id, points, reason, challenge_id,
         activity_date, session_id, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (
        user_id, points, reason, challenge_id,
        activity_date, session_id,
        datetime.now().isoformat()
    ))
    ledger_id = cur.lastrowid
    db.commit()
    db.close()
    return ledger_id


def get_total_points(user_id: str) -> int:
    """Kullanıcının toplam puanını ledger SUM'dan hesaplar."""
    db = get_db()
    row = db.execute("""
        SELECT COALESCE(SUM(points), 0) AS total
        FROM points_ledger
        WHERE user_id = ?
    """, (user_id,)).fetchone()
    db.close()
    return int(row["total"])


def already_rewarded(
    user_id: str,
    challenge_id: str,
    activity_date: str
) -> bool:
    """
    Bu kullanıcı bu challenge için bugün zaten ödüllendirildiyse
    True döner. Pipeline idempotency için kritik.
    """
    db = get_db()
    row = db.execute("""
        SELECT COUNT(*) AS cnt
        FROM points_ledger
        WHERE user_id = ?
          AND challenge_id = ?
          AND activity_date = ?
    """, (user_id, challenge_id, activity_date)).fetchone()
    db.close()
    return row["cnt"] > 0


def get_history(user_id: str, limit: int = 100) -> list:
    """Kullanıcının puan geçmişini en yeniden eskiye döndürür."""
    db = get_db()
    rows = db.execute("""
        SELECT pl.id, pl.points, pl.reason, pl.challenge_id,
               pl.activity_date, pl.created_at,
               c.name AS challenge_name
        FROM points_ledger pl
        LEFT JOIN challenges c ON c.id = pl.challenge_id
        WHERE pl.user_id = ?
        ORDER BY pl.created_at DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    db.close()
    return [dict(r) for r in rows]
