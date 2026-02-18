import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .config import DB_PATH

DB_DIR = Path(DB_PATH).parent
DB_DIR.mkdir(parents=True, exist_ok=True)

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'در حال بررسی',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                status TEXT DEFAULT 'ثبت شد',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        c.execute(
            """
            INSERT INTO content (key, value)
            SELECT 'about', 'ریشه؛ همراه رشد کسب‌وکار شماست.'
            WHERE NOT EXISTS (SELECT 1 FROM content WHERE key='about')
            """
        )
        c.execute(
            """
            INSERT INTO content (key, value)
            SELECT 'trust', 'برای اعتماد: نمونه‌کارها، رضایت مشتریان و شفافیت روند.'
            WHERE NOT EXISTS (SELECT 1 FROM content WHERE key='trust')
            """
        )

def get_or_create_user(telegram_id: int, username: str | None, name: str | None):
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = c.fetchone()
        if row:
            return row
        c.execute(
            "INSERT INTO users (telegram_id, username, name) VALUES (?, ?, ?)",
            (telegram_id, username, name),
        )
        c.execute("SELECT * FROM users WHERE id=?", (c.lastrowid,))
        return c.fetchone()

def update_user_name(telegram_id: int, name: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET name=? WHERE telegram_id=?", (name, telegram_id))

def add_order_for_user(telegram_id: int, title: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,))
        user = c.fetchone()
        if not user:
            return None
        c.execute(
            "INSERT INTO orders (user_id, title) VALUES (?, ?)",
            (user["id"], title),
        )
        return c.lastrowid

def get_orders_for_user(telegram_id: int):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT o.id, o.title, o.status, o.created_at
            FROM orders o
            JOIN users u ON u.id = o.user_id
            WHERE u.telegram_id=?
            ORDER BY o.created_at DESC
            """,
            (telegram_id,),
        )
        return [dict(r) for r in c.fetchall()]

def set_content(key: str, value: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO content (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
            (key, value),
        )

def get_content(key: str) -> str | None:
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM content WHERE key=?", (key,))
        row = c.fetchone()
        return row["value"] if row else None

def create_ticket(telegram_id: int, question: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,))
        user = c.fetchone()
        if not user:
            return None
        c.execute(
            "INSERT INTO tickets (user_id, question) VALUES (?, ?)",
            (user["id"], question),
        )
        return c.lastrowid
