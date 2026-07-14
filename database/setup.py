"""
database/setup.py — DGE AI-Native Gamification Engine
SQLite schema + deterministik seed (admin, challenge'lar, video katalogu).

Kurallar:
- eval/exec/random YOK.
- points_ledger append-only: hicbir UPDATE/DELETE trigger yok.
- Tum tablolar IF NOT EXISTS. Seed INSERT OR IGNORE (idempotent).
- ID'ler ya sabit seed ID (admin, challenge, video) ya rowid (INTEGER PRIMARY KEY) — hardcode calisma verisi degil.
"""

import os
import sqlite3
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gamification.db")

VIDEO_BASE = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/"


def get_db() -> sqlite3.Connection:
    """SQLite baglantisi dondurur. row_factory=Row, foreign_keys ON."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- Sema ---------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_catalog (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    content_type     TEXT NOT NULL,
    genre            TEXT,
    duration_minutes INTEGER NOT NULL,
    series_id        TEXT,
    episode_number   INTEGER,
    stream_url       TEXT NOT NULL,
    thumbnail_color  TEXT
);

CREATE TABLE IF NOT EXISTS watch_sessions (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    content_id    TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    watch_minutes REAL NOT NULL DEFAULT 0,
    completed     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (content_id) REFERENCES content_catalog(id)
);

CREATE TABLE IF NOT EXISTS user_activities (
    id                  INTEGER PRIMARY KEY,
    user_id             TEXT NOT NULL,
    activity_date       TEXT NOT NULL,
    watch_minutes       REAL NOT NULL DEFAULT 0,
    episodes_completed  INTEGER NOT NULL DEFAULT 0,
    genres_watched      INTEGER NOT NULL DEFAULT 0,
    watch_party_minutes REAL NOT NULL DEFAULT 0,
    ratings_given       INTEGER NOT NULL DEFAULT 0,
    session_id          TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
-- Not: session_id yumusak referans (CSV ile gelen aktivitelerin session'i yoktur).

CREATE TABLE IF NOT EXISTS points_ledger (
    id            INTEGER PRIMARY KEY,
    user_id       TEXT NOT NULL,
    points        INTEGER NOT NULL,
    reason        TEXT NOT NULL,
    challenge_id  TEXT,
    activity_date TEXT,
    session_id    TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_badges (
    id                    INTEGER PRIMARY KEY,
    user_id               TEXT NOT NULL,
    badge_tier            TEXT NOT NULL,
    awarded_at            TEXT NOT NULL,
    total_points_at_award INTEGER NOT NULL,
    UNIQUE (user_id, badge_tier),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS challenges (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    condition     TEXT NOT NULL,
    reward_points INTEGER NOT NULL,
    priority      INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                 INTEGER PRIMARY KEY,
    run_date           TEXT NOT NULL,
    users_processed    INTEGER NOT NULL DEFAULT 0,
    badges_awarded     INTEGER NOT NULL DEFAULT 0,
    points_distributed INTEGER NOT NULL DEFAULT 0,
    duration_ms        INTEGER NOT NULL DEFAULT 0,
    ran_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_memory (
    id         INTEGER PRIMARY KEY,
    user_id    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_calls_log (
    id              INTEGER PRIMARY KEY,
    model           TEXT NOT NULL,
    tokens_in       INTEGER NOT NULL DEFAULT 0,
    tokens_out      INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    grounding_score REAL,
    cost            REAL NOT NULL DEFAULT 0,
    user_id         TEXT,
    intent          TEXT,
    created_at      TEXT NOT NULL
);
"""


# --- Seed verisi --------------------------------------------------------

# (id, name, condition, reward_points, priority)
SEED_CHALLENGES = [
    ("c_daily_60",   "Gunun Izleyicisi", "watch_minutes_today >= 60",       80,  5),
    ("c_binge_3",    "Bolum Bitirici",   "episodes_completed_today >= 3",   150, 8),
    ("c_party_90",   "Parti Kurdu",      "watch_party_minutes_today >= 90", 200, 7),
    ("c_weekly_600", "Haftalik Maraton", "watch_minutes_7d >= 600",         380, 9),
    ("c_daily_300",  "Maraton Gunu",     "watch_minutes_today >= 300",      800, 10),
]

# (id, title, content_type, genre, duration_minutes, filename, thumbnail_color)
SEED_VIDEOS = [
    ("bb",      "Big Buck Bunny",                   "film",     "animasyon",   9,  "BigBuckBunny.mp4",                 "#F2A93B"),
    ("ed",      "Elephants Dream",                  "film",     "bilim-kurgu", 10, "ElephantsDream.mp4",               "#5B6EE1"),
    ("sintel",  "Sintel",                           "film",     "fantastik",   14, "Sintel.mp4",                       "#8E44AD"),
    ("tos",     "Tears of Steel",                   "film",     "bilim-kurgu", 12, "TearsOfSteel.mp4",                 "#2C93C4"),
    ("bullrun", "We Are Going On Bullrun",          "belgesel", "macera",      9,  "WeAreGoingOnBullrun.mp4",          "#E74C3C"),
    ("carcan",  "What Car Can You Get For A Grand",  "belgesel", "macera",      4,  "WhatCarCanYouGetForAGrand.mp4",    "#27AE60"),
    ("subaru",  "Subaru WRX STI",                   "kisa",     "otomobil",    3,  "SubaruOutbackOnStreetAndDirt.mp4", "#16A085"),
    ("vw",      "Volkswagen GTI Review",            "kisa",     "otomobil",    1,  "VolkswagenGTIReview.mp4",          "#C0392B"),
]

ADMIN_ID = "user_admin_001"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def hash_password(password: str) -> str:
    """SHA256 hex digest."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db() -> None:
    """Semayi olusturur ve deterministik seed'i (idempotent) yazar."""
    db = get_db()
    try:
        db.executescript(SCHEMA)

        now = datetime.now().isoformat()

        # Admin kullanici
        db.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, role, created_at) "
            "VALUES (?,?,?,?,?)",
            (ADMIN_ID, ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "admin", now),
        )

        # Challenge'lar
        db.executemany(
            "INSERT OR IGNORE INTO challenges (id, name, condition, reward_points, priority, is_active) "
            "VALUES (?,?,?,?,?,1)",
            SEED_CHALLENGES,
        )

        # Video katalogu
        for cid, title, ctype, genre, dur, filename, color in SEED_VIDEOS:
            db.execute(
                "INSERT OR IGNORE INTO content_catalog "
                "(id, title, content_type, genre, duration_minutes, series_id, episode_number, stream_url, thumbnail_color) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, title, ctype, genre, dur, None, None, VIDEO_BASE + filename, color),
            )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    db = get_db()
    try:
        n_challenges = db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
        n_videos = db.execute("SELECT COUNT(*) FROM content_catalog").fetchone()[0]
        print("OK DB hazir: database/gamification.db")
        print("OK Admin: admin / admin123")
        print("OK Challenge sayisi:", n_challenges)
        print("OK Video sayisi:", n_videos)
    finally:
        db.close()
