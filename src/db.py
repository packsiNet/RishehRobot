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
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoryid INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(categoryid) REFERENCES categories(id)
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_items_categoryid ON items(categoryid)")
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

        items_by_category: dict[str, list[tuple[str, str]]] = {
            "👇 سلامت پیشگیرانه👇": [
                (
                    "سنجش سلامت 📋",
                    """
🩺 سنجش سلامت
یه ارزیابی جامع و پیشگیرانه برای اینکه تصویر دقیقی از وضعیت سلامت پدر یا مادرت داشته باشی — بدون مراجعه حضوری.
فقط با یک گفتگوی ۲۰ تا ۳۰ دقیقه‌ای با پزشک متخصص 👨🏻‍⚕️، شش حوزه کلیدی سلامت بررسی می‌شه و در پایان، یک نقشه روشن از وضعیت سلامت در سه سطح (مطلوب، قابل اصلاح، پرریسک) دریافت می‌کنی.
اقدامی ساده برای آگاهی قبل از بحران ⚠️
برای اطلاع از نحوه سفارش و اینکه سنجش سلامت چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
                (
                    "🧠 غربالگری آلزایمر",
                    """
🧠 غربالگری آلزایمر
این خدمت برای بررسی اولیه حافظه و عملکرد شناختی طراحی شده.
ریشه هماهنگ می‌کنه تا ارزیابی‌های استاندارد توسط بهترین پزشکان فوق‌تخصص مغز و اعصاب و در بهتریین مراکز MRI ایران انجام بشه 👩🏻‍⚕️ و نتیجه به‌صورت گزارش شفاف ارائه بشه.
اگه نیاز به بررسی تخصصی‌تر باشه، مسیر ارجاع هم مشخص می‌شه 📋
این کار کمک می‌کنه آلزایمر ۴ تا ۷ سال زودتر دیده بشه و مدیریت‌ش راحت‌تر باشه.
برای اطلاع از نحوه سفارش و اینکه غربالگری آلزایمر چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
                (
                    "چکاپ‌های تخصصی 🏥",
                    """
🩺 چکاپ‌های تخصصی
آگاهی قبل از بحران. ⚠️
این خدمت برای انجام چکاپ‌های تخصصی دوره‌ای طراحی شده؛
همون بررسی‌هایی که هر فرد در طول زندگی باید انجام بده تا از وضعیت دقیق سلامت خودش باخبر باشه.
از چکاپ‌های مرتبط با سن سالمندی 👵👴 گرفته تا بررسی‌هایی که بهتره در سنین پایین‌تر انجام بشه تا ریسک‌ها زودتر شناسایی بشن.
تو درخواست رو ثبت می‌کنی ✍️، ریشه هماهنگی با مراکز معتبر رو انجام می‌ده
و بعد از انجام چکاپ، گزارش شفاف برای خود فرد و در صورت درخواست برای تو ارسال می‌شه 📄
برای اطلاع از نحوه سفارش و اینکه چکاپ‌های تخصصی سلامت چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
                (
                    "🏠 بازطراحی محیط زندگی سالمندان",
                    """
🏠 بازطراحی محیط زندگی سالمند
این خدمت برای کم کردن ریسک حادثه در خانه ⚠️ مثل زمین خوردن و راحت‌تر شدن زندگی سالمند طراحی شده.
ریشه ارزیابی محیط رو هماهنگ می‌کنه، نقاط پرخطر مشخص می‌شه 🔎 و پیشنهادهای اصلاحی داده می‌شه.
اگه تأیید کنی، اجرای اصلاحات هم هماهنگ می‌شه؛ مثل ایمن‌سازی لبه‌های فرش، نصب تجهیزات کمکی تو سرویس‌های بهداشتی و حمام 🚿، بهتر کردن نور 💡 یا اصلاح چیدمان برای بهبود مسیرها.
در پایان هم گزارش ارزیابی و نتیجه اقدامات برای تو ارسال می‌شه 📄
برای اطلاع از نحوه سفارش و اینکه بازطراحی محیط زندگی چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
            ],
            "👇 ساخت لحظه‌های به‌یاد ماندنی از راه‌دور 👇": [
                (
                    "سور (مهمان‌کردن و ساخت تجربه) 🍽️",
                    """
🍽️ سور (مهمان‌کردن و ساخت تجربه)
اگه می‌خوای عزیزت رو مهمون کنی و یه تجربه خوب براش بسازی، این گزینه برای توئه 🎉
ریشه هماهنگی زمان و مکان، طراحی تجربه، اجرای برنامه و گزارش نهایی رو مدیریت می‌کنه.
تو جزئیات رو می‌گی ✍️، ما پیگیری می‌کنیم تا اتفاق درست و دقیق اجرا بشه ✨
برای اطلاع از نحوه سفارش و اینکه سور دادن چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
                (
                    "سورپرایز (اجرای غافلگیرکننده)🎶",
                    """
🎉 سورپرایز (اجرای غافلگیرکننده)
برای وقتی که می‌خوای یه لحظه غافلگیرکننده بسازی؛ مثل نوازنده 🎶، برنامه کوتاه هنری، تولد 🎂 یا یه اجرای ویژه در خانه یا لوکیشن مشخص.
ریشه هماهنگی‌ها رو انجام می‌ده، اجرای برنامه رو مدیریت می‌کنه و گزارش انجامش رو برات می‌فرسته 📸📄
برای اطلاع از نحوه سفارش و اینکه سورپرایزها چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
                (
                    "خرید هدیه، گل و شیرینی 🌸",
                    """
🎁 خرید هدیه، گل و شیرینی
اگه می‌خوای هدیه، گل 🌸 یا شیرینی 🍰 برای عزیزت در ایران ارسال کنی، اینجا ثبت کن.
ریشه از تأمین‌کننده‌های معتبر در شهر مقصد خرید رو هماهنگ می‌کنه و روند انتخاب، پرداخت، تحویل و تأیید انجام رو مدیریت می‌کنه.
تمرکز این خدمت روی کیفیت قابل اتکا ✔️، قیمت شفاف 💳، و اطمینان از تحویل 📦هست.
برای اطلاع از نحوه سفارش و اینکه خرید و رسوندن هدیه‌ات چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
            ],
            "👇 انجام نیازهای روزمره👇": [
                (
                    "خرید روزمره 🧺",
                    """
🛒 خریدهای روزمره (انجام امور روزانه)
اگه والدین یا عزیزت برای انجام خریدهای روزمره به کمک نیاز دارن،
اینجا می‌تونی درخواست ثبت کنی.
ریشه هماهنگ می‌کنه تا فرد معتمد خریدهای موردنیاز رو انجام بده؛
از خریدهای سوپرمارکتی 🏪 و دارویی 💊 گرفته
تا اقلام ضروری روزمره‌ای که خرید همزمانش برای سالمند سخت شده.
فرآیند خرید، تحویل 📦 و تأیید به طور کامل مدیریت می‌شه و گزارش برات ارسال می‌شه 📄
این خدمت برای وقت‌هایی طراحی شده که حضور تو لازمه، اما امکانش رو نداری 🤍
برای اطلاع از نحوه سفارش و اینکه خریدهای روزمره چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
                (
                    "حل مشکلات دیجیتالی 💻",
                    """
حل مشکلات دیجیتالی 💻
برای خیلی از سالمندان، انجام کارهای دیجیتال ساده نیست.
از خرید اشتراک پلتفرم‌های نمایش خانگی 🎬
گرفته تا خرید اینترنت 🌐، نصب و راه‌اندازی تجهیزات، تنظیم تلویزیون 📺 یا حتی نصب نرم‌افزارهای موردنیاز.
اگه عزیزت در انجام این کارها نیاز به همراهی داره،
ریشه هماهنگ می‌کنه تا فردی متخصص کمکش کنه 👨🏻‍🔧
تو درخواست رو ثبت می‌کنی ✍️،
ما هماهنگی و اجرا رو مدیریت می‌کنیم
و نتیجه انجام کار رو بهت گزارش می‌دیم 📄
هدف؛ کم‌کردن وابستگی و ساده‌تر کردن زندگی روزمره 🤍
برای اطلاع از نحوه سفارش و اینکه همراهی در خدمات دیجیتال چطور انجام میشه، حتما ویدیو/ فایل بالا رو نگاه کن 🎥📎
""",
                ),
            ],
        }

        for cat_title, items in items_by_category.items():
            c.execute("SELECT id FROM categories WHERE title=?", (cat_title,))
            cat_row = c.fetchone()
            if not cat_row:
                continue
            cat_id = cat_row["id"]
            for it_title, it_desc in items:
                c.execute(
                    "INSERT INTO items (categoryid, title, description) SELECT ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM items WHERE categoryid=? AND title=?)",
                    (cat_id, it_title, it_desc, cat_id, it_title),
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

def get_item_by_title(title: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT i.id, i.title, i.description, i.categoryid, c.title as category_title
            FROM items i
            JOIN categories c ON c.id = i.categoryid
            WHERE i.title=? AND i.active=1 AND c.active=1
            """,
            (title,),
        )
        row = c.fetchone()
        return dict(row) if row else None

def get_item_by_id(item_id: int):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT i.id, i.title, i.description, i.categoryid, c.title as category_title
            FROM items i
            JOIN categories c ON c.id = i.categoryid
            WHERE i.id=? AND i.active=1 AND c.active=1
            """,
            (item_id,),
        )
        row = c.fetchone()
        return dict(row) if row else None

def add_item(category_id: int, title: str, description: str | None = None, active: int = 1):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO items (categoryid, title, description, active) VALUES (?, ?, ?, ?)",
            (category_id, title, description, active),
        )
        return c.lastrowid

def get_items_by_category(category_id: int):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, categoryid, title, description, active, created_at FROM items WHERE categoryid=? AND active=1 ORDER BY id ASC",
            (category_id,),
        )
        return [dict(r) for r in c.fetchall()]

def get_items_by_category_title(title: str):
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM categories WHERE title=? AND active=1", (title,))
        row = c.fetchone()
        if not row:
            return []
        cat_id = row["id"]
        c.execute(
            "SELECT id, categoryid, title, description, active, created_at FROM items WHERE categoryid=? AND active=1 ORDER BY id ASC",
            (cat_id,),
        )
        return [dict(r) for r in c.fetchall()]
