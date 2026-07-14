"""
engine/csv_ingestion.py — Gercek CSV aktivite verisini user_activities'e yukler.

Format: user_id, date, watch_minutes, episodes_completed, genres_watched,
        watch_party_minutes, ratings_given

- Ayni (user_id, date) icin csv_import kaydi zaten varsa atlanir (idempotent).
- CSV'de gecen ama users tablosunda olmayan kullanicilar ingestion hesabi olarak
  acilir (gercek veri setindeki gercek kullanicilar; parola bilinmez, giris yapilamaz).
"""

import os
import csv
import uuid
import hashlib
from datetime import datetime

from database.setup import get_db

CSV_MARKER = "csv_import"
EXPECTED_FIELDS = [
    "user_id", "date", "watch_minutes", "episodes_completed",
    "genres_watched", "watch_party_minutes", "ratings_given",
]


def _ensure_user(db, user_id: str) -> None:
    """CSV kullanicisi users'ta yoksa olusturur (giris yapilamayan veri hesabi)."""
    row = db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone()
    if row:
        return
    unknowable = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()
    db.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?,?,?,?,?)",
        (user_id, user_id, unknowable, "user", datetime.now().isoformat()),
    )


def load_csv(path: str) -> dict:
    """
    CSV dosyasini user_activities'e yukler.
    Doner: {filename, total_rows, valid_rows, invalid_rows, inserted,
            skipped_duplicate, errors}
    """
    filename = os.path.basename(path)
    total = valid = invalid = inserted = skipped = 0
    errors = []

    db = get_db()
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh, skipinitialspace=True)
            header = [h.strip() for h in (reader.fieldnames or [])]
            missing = [f for f in EXPECTED_FIELDS if f not in header]
            if missing:
                return {
                    "filename": filename, "total_rows": 0, "valid_rows": 0,
                    "invalid_rows": 0, "inserted": 0, "skipped_duplicate": 0,
                    "errors": [f"Eksik kolon(lar): {missing}"],
                }

            for line_no, raw in enumerate(reader, start=2):
                total += 1
                row = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k}
                try:
                    user_id = row["user_id"]
                    date = row["date"]
                    datetime.strptime(date, "%Y-%m-%d")  # format kontrolu
                    wm = float(row["watch_minutes"])
                    ep = int(row["episodes_completed"])
                    gw = int(row["genres_watched"])
                    wp = float(row["watch_party_minutes"])
                    rg = int(row["ratings_given"])
                    if not user_id or wm < 0 or ep < 0 or gw < 0 or wp < 0 or rg < 0:
                        raise ValueError("negatif/eksik deger")
                except (KeyError, ValueError) as e:
                    invalid += 1
                    errors.append(f"satir {line_no}: {e}")
                    continue

                valid += 1

                dup = db.execute(
                    "SELECT 1 FROM user_activities "
                    "WHERE user_id=? AND activity_date=? AND session_id=?",
                    (user_id, date, CSV_MARKER),
                ).fetchone()
                if dup:
                    skipped += 1
                    continue

                _ensure_user(db, user_id)
                db.execute(
                    """
                    INSERT INTO user_activities
                        (user_id, activity_date, watch_minutes, episodes_completed,
                         genres_watched, watch_party_minutes, ratings_given,
                         session_id, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (user_id, date, wm, ep, gw, wp, rg, CSV_MARKER,
                     datetime.now().isoformat()),
                )
                inserted += 1

        db.commit()
    finally:
        db.close()

    return {
        "filename": filename,
        "total_rows": total,
        "valid_rows": valid,
        "invalid_rows": invalid,
        "inserted": inserted,
        "skipped_duplicate": skipped,
        "errors": errors[:20],
    }
