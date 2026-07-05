"""
CSV Ingestion — harici aktivite verisi yükler.
Idempotent: aynı CSV iki kez yüklense duplicate olmaz.
"""

import csv
from datetime import datetime
from database.setup import get_db

REQUIRED_FIELDS = [
    "user_id", "date", "watch_minutes",
    "episodes_completed", "genres_watched",
    "watch_party_minutes", "ratings_given",
]


def validate_row(row: dict) -> tuple:
    if not row.get("user_id", "").strip():
        return False, "user_id bos"
    try:
        datetime.strptime(row["date"].strip(), "%Y-%m-%d")
    except (ValueError, KeyError):
        return False, f"Gecersiz tarih: {row.get('date')}"
    limits = {
        "watch_minutes":       (0, 1440),
        "episodes_completed":  (0, 100),
        "genres_watched":      (0, 50),
        "watch_party_minutes": (0, 1440),
        "ratings_given":       (0, 100),
    }
    for field, (mn, mx) in limits.items():
        try:
            v = float(row.get(field, 0))
            if not (mn <= v <= mx):
                return False, f"{field} aralik disi: {v}"
        except (ValueError, TypeError):
            return False, f"{field} sayisal degil"
    return True, ""


def load_csv(filepath: str) -> dict:
    db    = get_db()
    stats = {
        "total_rows":        0,
        "valid_rows":        0,
        "invalid_rows":      0,
        "inserted":          0,
        "skipped_duplicate": 0,
        "errors":            [],
    }
    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = [
                x for x in REQUIRED_FIELDS
                if x not in (reader.fieldnames or [])
            ]
            if missing:
                raise ValueError(f"Eksik kolon: {missing}")

            for i, row in enumerate(reader, 2):
                stats["total_rows"] += 1
                ok, err = validate_row(row)
                if not ok:
                    stats["invalid_rows"] += 1
                    stats["errors"].append(f"Satir {i}: {err}")
                    continue
                stats["valid_rows"] += 1

                uid  = row["user_id"].strip()
                date = row["date"].strip()

                user_ok = db.execute(
                    "SELECT id FROM users WHERE id=?", (uid,)
                ).fetchone()
                if not user_ok:
                    stats["invalid_rows"] += 1
                    stats["errors"].append(
                        f"Satir {i}: user bulunamadi: {uid}"
                    )
                    continue

                dup = db.execute("""
                    SELECT COUNT(*) AS c FROM user_activities
                    WHERE user_id=? AND activity_date=?
                      AND session_id='csv_import'
                """, (uid, date)).fetchone()
                if dup["c"] > 0:
                    stats["skipped_duplicate"] += 1
                    continue

                db.execute("""
                    INSERT INTO user_activities
                    (user_id, activity_date, watch_minutes,
                     episodes_completed, genres_watched,
                     watch_party_minutes, ratings_given,
                     session_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'csv_import', ?)
                """, (
                    uid, date,
                    float(row["watch_minutes"]),
                    int(float(row["episodes_completed"])),
                    int(float(row["genres_watched"])),
                    float(row["watch_party_minutes"]),
                    int(float(row["ratings_given"])),
                    datetime.now().isoformat(),
                ))
                stats["inserted"] += 1

        db.commit()
    except Exception as e:
        stats["errors"].append(f"Dosya hatasi: {e}")
    finally:
        db.close()
    return stats
