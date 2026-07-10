import sys
import sqlite3
import hashlib
import os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "database/gamification.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    os.makedirs("database", exist_ok=True)
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS watch_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        content_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        watch_minutes REAL DEFAULT 0,
        completed INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS user_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        activity_date TEXT NOT NULL,
        watch_minutes REAL DEFAULT 0,
        episodes_completed INTEGER DEFAULT 0,
        genres_watched INTEGER DEFAULT 0,
        watch_party_minutes REAL DEFAULT 0,
        ratings_given INTEGER DEFAULT 0,
        session_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS points_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        points INTEGER NOT NULL,
        reason TEXT NOT NULL,
        challenge_id TEXT,
        activity_date TEXT NOT NULL,
        session_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS user_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        badge_tier TEXT NOT NULL,
        awarded_at TEXT NOT NULL,
        total_points_at_award INTEGER NOT NULL,
        UNIQUE(user_id, badge_tier),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS content_catalog (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content_type TEXT NOT NULL,
        genre TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        series_id TEXT,
        episode_number INTEGER,
        stream_url TEXT NOT NULL,
        thumbnail_color TEXT DEFAULT '#1a1a2e'
    );
    CREATE TABLE IF NOT EXISTS challenges (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        condition TEXT NOT NULL,
        reward_points INTEGER NOT NULL,
        priority INTEGER NOT NULL,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date TEXT NOT NULL,
        users_processed INTEGER DEFAULT 0,
        badges_awarded INTEGER DEFAULT 0,
        points_distributed INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        ran_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS content_ratings (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        content_id TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, content_id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS content_comments (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        content_id TEXT NOT NULL,
        comment TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS watch_parties (
        id TEXT PRIMARY KEY,
        room_code TEXT UNIQUE NOT NULL,
        host_user_id TEXT NOT NULL,
        content_id TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        ended_at TEXT,
        FOREIGN KEY (host_user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS watch_party_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        party_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        joined_at TEXT NOT NULL,
        left_at TEXT,
        UNIQUE(party_id, user_id),
        FOREIGN KEY (party_id) REFERENCES watch_parties(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user','assistant')),
        content TEXT NOT NULL,
        intent TEXT,
        model TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT,
        payload TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS seasons (
        id TEXT PRIMARY KEY,
        week_start TEXT NOT NULL,
        week_end TEXT NOT NULL,
        finalized_at TEXT
    );
    CREATE TABLE IF NOT EXISTS season_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        season_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        rank INTEGER NOT NULL,
        points INTEGER NOT NULL,
        reward_points INTEGER DEFAULT 0,
        UNIQUE(season_id, user_id),
        FOREIGN KEY (season_id) REFERENCES seasons(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS follows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id TEXT NOT NULL,
        following_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(follower_id, following_id),
        CHECK(follower_id != following_id),
        FOREIGN KEY (follower_id) REFERENCES users(id),
        FOREIGN KEY (following_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS user_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        achievement_id TEXT NOT NULL,
        awarded_at TEXT NOT NULL,
        UNIQUE(user_id, achievement_id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS content_ai_summaries (
        content_id TEXT PRIMARY KEY,
        summary TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        model TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS comment_sentiments (
        comment_id TEXT PRIMARY KEY,
        sentiment TEXT NOT NULL CHECK(sentiment IN ('pozitif','negatif','notr')),
        model TEXT NOT NULL,
        analyzed_at TEXT NOT NULL,
        FOREIGN KEY (comment_id) REFERENCES content_comments(id)
    );
    """)
    cur.execute("""
        INSERT OR IGNORE INTO users
        (id, username, password_hash, role, created_at)
        VALUES (?,?,?,'admin',?)
    """, ("user_admin_001", "admin",
          hashlib.sha256("admin123".encode()).hexdigest(),
          datetime.now().isoformat()))
    challenges = [
        ("c_daily_60",   "Günün İzleyicisi",  "watch_minutes_today >= 60",        80,  5),
        ("c_binge_3",    "Bölüm Bitirici",    "episodes_completed_today >= 3",    150,  8),
        ("c_party_90",   "Parti Kurdu",        "watch_party_minutes_today >= 90", 200,  7),
        ("c_weekly_600", "Haftalık Maraton",   "watch_minutes_7d >= 600",         380,  9),
        ("c_daily_300",  "Maraton Günü",       "watch_minutes_today >= 300",      800, 10),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO challenges
        (id, name, condition, reward_points, priority)
        VALUES (?,?,?,?,?)
    """, challenges)
    content = [
        ("bb",     "Big Buck Bunny",           "film",     "animasyon",   9, None,       None, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",        "#4a90d9"),
        ("ed",     "Elephants Dream",          "film",     "bilim-kurgu",10, None,       None, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",      "#7b68ee"),
        ("sintel", "Sintel",                   "film",     "fantastik",  14, None,       None, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",              "#e8a87c"),
        ("tos",    "Tears of Steel",           "film",     "bilim-kurgu",12, None,       None, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",        "#00b4d8"),
        ("bullrun","We Are Going On Bullrun",  "belgesel", "macera",      9, "s_macera", 1,   "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4", "#f77f00"),
        ("carcan", "What Car Can Do",          "belgesel", "macera",      4, "s_macera", 2,   "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WhatCarCanDo.mp4",        "#f77f00"),
        ("subaru", "Subaru WRX STI",           "kisa",     "otomobil",    3, None,       None, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4", "#2d6a4f"),
        ("vw",     "Volkswagen GTI",           "kisa",     "otomobil",    1, None,       None, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/VolkswagenGTIReview.mp4", "#d62828"),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO content_catalog
        (id, title, content_type, genre, duration_minutes,
         series_id, episode_number, stream_url, thumbnail_color)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, content)
    conn.commit()
    conn.close()
    print("✓ DB hazır:", DB_PATH)
    print("✓ Admin: admin / admin123")
    print("✓ Challenge sayısı:", len(challenges))
    print("✓ Video sayısı:", len(content))

if __name__ == "__main__":
    init_db()
