"""
engine/ledger.py — Append-only puan defteri.

Bu dosyada SADECE INSERT ve SELECT vardir. Guncelleme/silme statement'i yoktur
(points_ledger append-only tutulur). Boylece puan gecmisi denetlenebilir kalir.
"""

from datetime import datetime

from database.setup import get_db


def append_points(user_id, points, reason, activity_date,
                  challenge_id=None, session_id=None) -> int:
    """
    points_ledger'a yeni bir puan kaydi ekler (sadece INSERT).
    Doner: eklenen kaydin id'si (lastrowid).
    """
    db = get_db()
    try:
        cur = db.execute(
            """
            INSERT INTO points_ledger
                (user_id, points, reason, challenge_id, activity_date, session_id, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (user_id, points, reason, challenge_id, activity_date, session_id,
             datetime.now().isoformat()),
        )
        db.commit()
        return int(cur.lastrowid)
    finally:
        db.close()


def get_total_points(user_id: str) -> int:
    """Kullanicinin toplam puani (points_ledger SUM)."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT COALESCE(SUM(points), 0) AS total FROM points_ledger WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return int(row["total"])
    finally:
        db.close()


def already_rewarded(user_id: str, challenge_id: str, activity_date: str) -> bool:
    """
    Kullanici bu challenge icin bu tarihte zaten odullendirildi mi?
    Pipeline idempotency'si icin kritik. SELECT COUNT(*) ile kontrol.
    """
    db = get_db()
    try:
        row = db.execute(
            """
            SELECT COUNT(*) AS n FROM points_ledger
            WHERE user_id=? AND challenge_id=? AND activity_date=?
            """,
            (user_id, challenge_id, activity_date),
        ).fetchone()
        return int(row["n"]) > 0
    finally:
        db.close()


def get_history(user_id: str, limit: int = 100) -> list:
    """
    Kullanicinin puan gecmisi, en yeniden eskiye.
    points_ledger LEFT JOIN challenges ile challenge_name de gelir.
    Doner: list of dict.
    """
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                pl.id,
                pl.user_id,
                pl.points,
                pl.reason,
                pl.challenge_id,
                pl.activity_date,
                pl.session_id,
                pl.created_at,
                c.name AS challenge_name
            FROM points_ledger pl
            LEFT JOIN challenges c ON c.id = pl.challenge_id
            WHERE pl.user_id=?
            ORDER BY pl.id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()
