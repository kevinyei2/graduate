"""SQLite 儲存：每一則「貼文」有多個「平台任務」(targets)。"""
import json
import sqlite3
import time
from contextlib import contextmanager

from config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_path TEXT NOT NULL,
    original_name TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    options TEXT NOT NULL,          -- JSON：標題、說明、hashtag、隱私設定等
    scheduled_at INTEGER NOT NULL,  -- Unix 秒；立即發佈 = 建立時間
    status TEXT NOT NULL,           -- pending / running / done / failed / cancelled
    result TEXT,                    -- 成功時的網址或 ID
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_targets_due ON targets(status, scheduled_at);
"""


@contextmanager
def connect():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        # 程式中途被關掉時，把卡在 running 的任務放回佇列
        conn.execute(
            "UPDATE targets SET status='pending', updated_at=? WHERE status='running'",
            (int(time.time()),),
        )


def create_post(video_path, original_name, targets):
    now = int(time.time())
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO posts (video_path, original_name, created_at) VALUES (?,?,?)",
            (video_path, original_name, now),
        )
        post_id = cur.lastrowid
        for t in targets:
            conn.execute(
                "INSERT INTO targets (post_id, platform, options, scheduled_at, status, updated_at)"
                " VALUES (?,?,?,?, 'pending', ?)",
                (post_id, t["platform"], json.dumps(t["options"], ensure_ascii=False),
                 int(t["scheduled_at"]), now),
            )
    return post_id


def claim_due_targets(now=None):
    """取出到期的任務並標成 running，避免重複執行。"""
    now = int(now or time.time())
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.*, p.video_path, p.original_name FROM targets t JOIN posts p ON p.id=t.post_id"
            " WHERE t.status='pending' AND t.scheduled_at<=? ORDER BY t.scheduled_at",
            (now,),
        ).fetchall()
        claimed = []
        for r in rows:
            cur = conn.execute(
                "UPDATE targets SET status='running', attempts=attempts+1, updated_at=?"
                " WHERE id=? AND status='pending'",
                (now, r["id"]),
            )
            if cur.rowcount:
                claimed.append(dict(r))
        return claimed


def finish_target(target_id, ok, result=None, error=None):
    with connect() as conn:
        conn.execute(
            "UPDATE targets SET status=?, result=?, error=?, updated_at=? WHERE id=?",
            ("done" if ok else "failed", result, error, int(time.time()), target_id),
        )


def retry_target(target_id):
    with connect() as conn:
        conn.execute(
            "UPDATE targets SET status='pending', error=NULL, scheduled_at=?, updated_at=?"
            " WHERE id=? AND status IN ('failed','cancelled')",
            (int(time.time()), int(time.time()), target_id),
        )


def cancel_target(target_id):
    with connect() as conn:
        conn.execute(
            "UPDATE targets SET status='cancelled', updated_at=? WHERE id=? AND status='pending'",
            (int(time.time()), target_id),
        )


def list_posts(limit=50):
    with connect() as conn:
        posts = [dict(r) for r in conn.execute(
            "SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
        for p in posts:
            p["targets"] = []
            for r in conn.execute(
                    "SELECT * FROM targets WHERE post_id=? ORDER BY id", (p["id"],)).fetchall():
                t = dict(r)
                t["options"] = json.loads(t["options"])
                p["targets"].append(t)
        return posts


def post_has_unfinished_targets(post_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM targets WHERE post_id=? AND status IN ('pending','running')",
            (post_id,),
        ).fetchone()
        return row[0] > 0
