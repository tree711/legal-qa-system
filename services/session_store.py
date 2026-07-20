# -*- coding: utf-8 -*-
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "sessions.db"
_LOCK = threading.Lock()


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            messages TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    return conn


def create_session(title: str = "新对话") -> dict:
    now = time.time()
    session_id = str(uuid.uuid4())
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO sessions(id,title,messages,created_at,updated_at) VALUES(?,?,?,?,?)",
            (session_id, title.strip() or "新对话", "[]", now, now),
        )
    return get_session(session_id)


def list_sessions() -> list[dict]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT id,title,messages,created_at,updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [_row_to_dict(r, include_messages=False) for r in rows]


def get_session(session_id: str) -> dict | None:
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT id,title,messages,created_at,updated_at FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    return _row_to_dict(row, include_messages=True) if row else None


def save_messages(session_id: str, messages: list[dict], title: str | None = None) -> dict | None:
    now = time.time()
    with _LOCK, _connect() as conn:
        if title is None:
            conn.execute(
                "UPDATE sessions SET messages=?, updated_at=? WHERE id=?",
                (json.dumps(messages, ensure_ascii=False), now, session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET title=?, messages=?, updated_at=? WHERE id=?",
                (title, json.dumps(messages, ensure_ascii=False), now, session_id),
            )
    return get_session(session_id)


def clear_session(session_id: str) -> dict | None:
    return save_messages(session_id, [], "新对话")


def delete_session(session_id: str) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    return cur.rowcount > 0


def _row_to_dict(row, include_messages: bool) -> dict:
    item = {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_messages:
        item["messages"] = json.loads(row["messages"] or "[]")
    return item
