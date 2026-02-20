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

def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}

def init_db():
    with connect() as conn:
        c = conn.cursor()
        # Users table per client's schema
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegramid INTEGER UNIQUE NOT NULL,
                username TEXT,
                firstname TEXT,
                lastname TEXT,
                phonenumber TEXT,
                createdat DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Backward compatibility: add missing columns if table pre-existed with old schema
        cols = _table_columns(conn, "users")
        expected = {
            "telegramid": "INTEGER",
            "username": "TEXT",
            "firstname": "TEXT",
            "lastname": "TEXT",
            "phonenumber": "TEXT",
            "createdat": "DATETIME",
        }
        for col, typ in expected.items():
            if col not in cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
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
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE NOT NULL,
                description TEXT,
                position INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

        defaults = [
            ("🚨 تماس اضطراری 🚨", "توضیحات تماس اضطراری", 1),
            ("👇 سلامت پیشگیرانه👇", "توضیحات سلامت پیشگیرانه", 2),
            ("👇 ساخت لحظه‌های به‌یاد ماندنی از راه‌دور 👇", "توضیحات لحظه‌های به‌یاد ماندنی", 3),
            ("👇 انجام نیازهای روزمره👇", "توضیحات نیازهای روزمره", 4),
        ]
        for t, d, p in defaults:
            c.execute(
                "INSERT INTO categories (title, description, position) SELECT ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM categories WHERE title=?)",
                (t, d, p, t),
            )

def get_or_create_user(telegram_id: int, username: str | None, first_name: str | None, last_name: str | None):
    with connect() as conn:
        c = conn.cursor()
        # Try client schema first
        c.execute("SELECT * FROM users WHERE telegramid=?", (telegram_id,))
        row = c.fetchone()
        if row:
            c.execute(
                "UPDATE users SET username=?, firstname=?, lastname=? WHERE telegramid=?",
                (username, first_name, last_name, telegram_id),
            )
            return row
        # Fallback to old schema search
        try:
            c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
            row_old = c.fetchone()
        except sqlite3.OperationalError:
            row_old = None
        if row_old:
            # Add new columns if needed and update
            c.execute(
                "UPDATE users SET telegramid=?, username=?, firstname=?, lastname=? WHERE id=?",
                (telegram_id, username, first_name, last_name, row_old["id"]),
            )
            return row_old
        # Insert new per client schema
        c.execute(
            "INSERT INTO users (telegramid, username, firstname, lastname) VALUES (?, ?, ?, ?)",
            (telegram_id, username, first_name, last_name),
        )
        c.execute("SELECT * FROM users WHERE id=?", (c.lastrowid,))
        return c.fetchone()

def update_user_contact(telegram_id: int, phone: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET phonenumber=? WHERE telegramid=?", (phone, telegram_id))

def add_order_for_user(telegram_id: int, title: str):
    with connect() as conn:
        c = conn.cursor()
        # prefer client schema
        try:
            c.execute("SELECT id FROM users WHERE telegramid=?", (telegram_id,))
        except sqlite3.OperationalError:
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
            WHERE (u.telegramid = ? OR u.telegram_id = ?)
            ORDER BY o.created_at DESC
            """,
            (telegram_id, telegram_id),
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

def get_categories_active():
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, title, description FROM categories WHERE active=1 ORDER BY position ASC, id ASC"
        )
        return [dict(r) for r in c.fetchall()]

def get_category_by_title(title: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, description FROM categories WHERE title=? AND active=1", (title,))
        row = c.fetchone()
        return dict(row) if row else None
