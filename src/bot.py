import logging
import os
from datetime import datetime, timezone, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, CallbackQueryHandler, filters
try:
    from zoneinfo import ZoneInfo
    TEHRAN_TZ = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN_TZ = None
from .config import TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS, APP_URL, SOCIAL_TELEGRAM_URL, SOCIAL_INSTAGRAM_URL, SOCIAL_YOUTUBE_URL, SOCIAL_LINKEDIN_URL, WEBSITE_URL, SUPPORT_URL
from .db import (
    init_db,
    get_or_create_user,
    is_user_active,
    get_orders_for_user,
    get_orders_for_user_by_status,
    get_orders_for_user_by_statuses,
    get_orders_for_identity,
    get_orders_for_user_by_statuses_identity,
    get_order_by_id,
    get_order_stats_for_user,
    get_order_stats_for_identity,
    is_admin,
    cancel_order_by_id,
    set_content,
    get_content,
    create_ticket,
    add_order_for_user,
    get_categories_active,
    get_category_by_title,
    get_items_by_category_title,
    get_items_by_category,
    get_item_by_title,
    get_item_by_id,
    create_order_for_item,
    get_unfinished_counts_for_item_ids,
    get_orders_by_item_admin,
    get_order_detail_admin,
    get_all_statuses,
    update_order_status_id,
    get_all_users_admin,
    get_user_by_id,
    set_user_role,
    set_user_active,
    get_admin_telegram_ids,
)

STATE_ASK_QUESTION = 1

MAIN_BUTTONS = [
    ["🚀 شروع همراهی 🚀"],
    ["📌 پیگیری سفارشاتم 📌"],
    ["🔎 چطور به ریشه اعتماد کنم؟ 🔎"],
    ["💬 اگه نمی‌دونی؛ از من بپرس! 💬"],
    ["🌿 ارتباط با ریشه"],
]
ADMIN_MAIN_BUTTONS = [
    ["📦 لیست سفارشات"],
    ["🧰 مدیریت خدمات"],
    ["🎓 مدیریت بخش آموزش"],
    ["👥 مدیریت کاربران"],
]
KB_USER = ReplyKeyboardMarkup(MAIN_BUTTONS, resize_keyboard=True, is_persistent=True)
KB_ADMIN = ReplyKeyboardMarkup(ADMIN_MAIN_BUTTONS, resize_keyboard=True, is_persistent=True)
BACK_TEXT = "⬅️ بازگشت"
ORDER_MENU = ReplyKeyboardMarkup(
    [
        ["📊 اعلام وضعیت سفارش‌ها"],
        ["⏳ سفارش‌های درحال انجام"],
        ["✅ سفارش‌های تکمیل شده"],
        [BACK_TEXT],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

CONTACT_MENU = ReplyKeyboardMarkup(
    [
        ["📱 سوشال ریشه 📱"],
        ["🌐 وبسایت ریشه🌐"],
        ["💬 ادمین ریشه💬"],
        [BACK_TEXT],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("rishehbot")

def _resolve_admin_ids():
    try:
        ids = []
        try:
            ids.extend(get_admin_telegram_ids())
        except Exception:
            pass
        ids.extend(ADMIN_USER_IDS)
        out = []
        seen = set()
        for x in ids:
            try:
                xi = int(str(x).strip())
            except Exception:
                continue
            if xi not in seen:
                seen.add(xi)
                out.append(xi)
        logger.info("admin recipients resolved count=%d ids=%s", len(out), out)
        return out
    except Exception as e:
        logger.exception("resolve admin ids failed: %s", e)
        return list(ADMIN_USER_IDS)

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    ids = _resolve_admin_ids()
    if not ids:
        logger.warning("no admin recipients to notify")
        return 0
    ok = 0
    for aid in ids:
        try:
            await context.bot.send_message(chat_id=aid, text=text)
            ok += 1
        except Exception as e:
            logger.warning("notify admin %s failed: %s", aid, e)
    logger.info("admin notify success=%d/%d", ok, len(ids))
    return ok

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    # Blocked user check
    if not is_user_active(user.id):
        support_msg = (
            "اکانت شما فعال نیست. برای فعال‌سازی با پشتیبانی تماس بگیرید."
        )
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(" ارتباط با پشتیبانی", url=SUPPORT_URL)]]
        )
        await update.message.reply_text(support_msg, reply_markup=inline_kb)
        return
    if is_admin(user.id):
        welcome_msg = "سلام! به پنل ادمین خوش اومدی."
        kb = KB_ADMIN
    else:
        welcome_msg = (
            "🌿 ریشه؛ جایی برای اینکه حتی از دور هم کنار خانواده‌ت باشی\n\n"
            "🏠 ریشه برای وقت‌هایی شکل گرفت که از خونه دوری،\n"
            "اما نمی‌خوای فاصله باعث بشه از مراقبت و پیگیری جا بمونی. 🤍\n\n"
            "برای اینکه از وضعیت سلامت عزیزت باخبر باشی، 🩺\n"
            "نیازهاشون رو مدیریت کنی و با خیال راحت‌تری زندگی کنی. 🕊️\n\n"
            "اینجا خدمات سلامت، همراهی و کارهای روزمره خانواده تو یک ساختار یکپارچه کنار هم قرار گرفته 🔗\n\n"
            "تا بتونی با آگاهی بیشتر و دغدغه کمتر کنارشون بمونی. 🌱\n"
            "اگه آماده‌ای این همراهی رو شروع کنی، قدم اول رو تو بردار. 👣\n"
            "✨ از منو یکی از مسیرها رو انتخاب کن تا با هم جلو بریم."
        )
        kb = KB_USER
    await update.message.reply_text(welcome_msg, reply_markup=kb)
    logger.info("/start handled for user_id=%s", user.id)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    user = update.effective_user
    if is_admin(user.id):
        if text == "📦 لیست سفارشات":
            cats = get_categories_active()
            if cats:
                kb = ReplyKeyboardMarkup([[c["title"]] for c in cats] + [[BACK_TEXT]], resize_keyboard=True, is_persistent=True)
                await update.message.reply_text("یک دسته‌بندی را انتخاب کن:", reply_markup=kb)
            else:
                await update.message.reply_text("دسته‌بندی فعالی موجود نیست.", reply_markup=KB_ADMIN)
            return ConversationHandler.END
        if text == "🧰 مدیریت خدمات":
            await update.message.reply_text("مدیریت خدمات - به‌زودی.", reply_markup=KB_ADMIN)
            return ConversationHandler.END
        if text == "🎓 مدیریت بخش آموزش":
            await update.message.reply_text("مدیریت بخش آموزش - به‌زودی.", reply_markup=KB_ADMIN)
            return ConversationHandler.END
        if text == "👥 مدیریت کاربران":
            users = get_all_users_admin()
            if not users:
                await update.message.reply_text("کاربری یافت نشد.", reply_markup=KB_ADMIN)
                return ConversationHandler.END
            def label(u):
                if u.get("username"):
                    return f"@{u['username']}"
                fn = (u.get("firstname") or "").strip()
                if fn:
                    return fn
                return f"کاربر {u['id']}"
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton(label(u), callback_data=f"adminuser:{u['id']}")] for u in users]
            )
            await update.message.reply_text("یک کاربر را انتخاب کن:", reply_markup=kb)
            return ConversationHandler.END
    if text == BACK_TEXT:
        await update.message.reply_text("بازگشت به منوی اصلی.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
        return ConversationHandler.END
    if text in ("🌿 ارتباط با ریشه", "🌿 ارتباط با ریشه "):
        msg = (
            "اگه می‌خوای بیشتر با ریشه در ارتباط باشی، چند راه ساده پیش‌روته 👇\n"
            "📲 دنبال کردن صفحات مجازی ریشه\n"
            "توی شبکه‌های اجتماعی ریشه می‌تونی از آخرین خدمات، اطلاعیه‌ها، به‌روزرسانی‌ها و محتوای آموزشی باخبر بشی.\n"
            "کافیه روی لینک هر شبکه کلیک کنی و صفحه رو دنبال کنی تا همیشه در جریان باشی 🔔\n"
            "\n"
            "💬 ارتباط مستقیم با پشتیبانی\n"
            "اگه سؤال داری یا نیاز به راهنمایی بیشتری داری، می‌تونی مستقیم به پشتیبانی پیام بدی ✍️ یا ویس بفرستی 🎙️\n"
            "پیامت بررسی می‌شه و در سریع‌ترین زمان ممکن پاسخ می‌گیری ⏳\n"
            "\n"
            "🤍 ریشه اینجاست تا همراهی فقط یک شعار نباشه؛\n"
            "هر زمان نیاز داشتی، از همین مسیرها با ما در ارتباط باش."
        )
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        img_path = os.path.join(base_dir, "files", "images", "contactRisheh.jpg")
        try:
            with open(img_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=msg, reply_markup=CONTACT_MENU)
        except Exception:
            await update.message.reply_text(msg, reply_markup=CONTACT_MENU)
        return ConversationHandler.END
    if text in ("🚀 شروع همراهی 🚀", "🚀 شروع همیاری 🚀"):
        get_or_create_user(user.id, user.username, user.first_name, user.last_name)
        cats = get_categories_active()
        msg = (
            "🌿 همراهی از اینجا شروع میشه!\n"
            "همراهی می‌تونه از توجه به سلامتی 🩺، رسیدگی به امور روزمره 🛍️\n"
            "یا حتی یک سوپرایز که حال دل رو بهتر می‌کنه 🎁 شروع بشه.\n"
            "بهمون بگو ریشه چیکار می‌تونه برات انجام بده؟ 🤍\n"
            "برای اطلاعات بیشتر از هر سرویس، می‌تونی روی هرکدوم کلیک کنی تا توضیحات کامل برات ارسال بشه ✨"
        )
        if cats:
            rows = [[c["title"]] for c in cats] + [["🎥 آموزش تصویری"], [BACK_TEXT]]
            kb = ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
            await update.message.reply_text(msg, reply_markup=kb)
        else:
            await update.message.reply_text(msg, reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
        return ConversationHandler.END
    if text == "📌 پیگیری سفارشاتم 📌":
        msg = (
            "🔄 همراهی همیشه برقراره!\n"
            "اگه قبلاً از ریشه خدمتی گرفتی یا سفارشی ثبت کردی،\n"
            "اینجا می‌تونی وضعیتش رو ببینی 👀"
        )
        await update.message.reply_text(msg, reply_markup=ORDER_MENU)
        return ConversationHandler.END
    if text == "📱 سوشال ریشه 📱":
        msg = (
            "🌿 می‌خوای بیشتر با ریشه آشنا شی؟\n"
            "توی شبکه‌های اجتماعی ریشه، روایت‌های واقعی از خانواده‌ها 🤍\n"
            "و اطلاع‌رسانی خدمات جدید رو منتشر می‌کنیم ✨\n"
            "اگه دوست داری در جریان باشی 🔔 و ریشه رو بیرون از بات هم دنبال کنی،\n"
            "از اینجا وارد سوشال ریشه شو 👇\n\n"
        )
        buttons = []
        if (SOCIAL_TELEGRAM_URL or "").strip():
            buttons.append([InlineKeyboardButton("کانال تلگرام ریشه", url=SOCIAL_TELEGRAM_URL)])
        if (SOCIAL_INSTAGRAM_URL or "").strip():
            buttons.append([InlineKeyboardButton("صفحه اینستاگرام ریشه", url=SOCIAL_INSTAGRAM_URL)])
        if (SOCIAL_YOUTUBE_URL or "").strip():
            buttons.append([InlineKeyboardButton("صفحه یوتیوب ریشه", url=SOCIAL_YOUTUBE_URL)])
        if (SOCIAL_LINKEDIN_URL or "").strip():
            buttons.append([InlineKeyboardButton("صفحه لینکدین ریشه", url=SOCIAL_LINKEDIN_URL)])
        inline_kb = InlineKeyboardMarkup(buttons) if buttons else None
        await update.message.reply_text(msg, reply_markup=inline_kb or CONTACT_MENU)
        return ConversationHandler.END
    if text == "🌐 وبسایت ریشه🌐":
        msg = (
            "اگه می‌خوای کامل‌تر با خدمات و ساختار ریشه آشنا شی،\n"
            "پیشنهاد می‌کنیم یه سر به وبسایت بزنی 👀\n"
            "توی سایت می‌تونی جزئیات هر خدمت رو دقیق ببینی 📄،\n"
            "فرآیندها رو بخونی 🔎،\n"
            "سؤال‌های متداول رو بررسی کنی ❓\n"
            "و با خیال راحت تصمیم بگیری 🤍\n"
            "🌍 لینک وبسایت خارجی ریشه:\n"
            "لینک"
        )
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("وبسایت ریشه", url=WEBSITE_URL)]]) if (WEBSITE_URL or "").strip() else None
        await update.message.reply_text(msg, reply_markup=inline_kb or CONTACT_MENU)
        return ConversationHandler.END
    if text == "💬 ادمین ریشه💬":
        msg = (
            "💬 اگه درباره خدمات، ثبت سفارش یا هر بخش دیگه‌ای سؤال داری،\n"
            "برای این آیدی بنویس ✍️ یا ویس بفرست 🎙️\n"
            "پیامت مستقیم برای تیم پشتیبانی ریشه ارسال می‌شه 📩\n"
            "و کارشناسانمون در سریع‌ترین زمان ممکن بررسیش می‌کنن ⏳\n"
            "تا بتونیم به بهترین شکل ممکن راهنماییت کنیم 🤍\n"
            "کنارت هستیم.\n\n"
            "🆔 آیدی پشتیبانی:\n"
            "@rishehsupport"
        )
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton(" ارتباط با پشتیبانی", url=SUPPORT_URL)]])
        await update.message.reply_text(msg, reply_markup=inline_kb)
        return ConversationHandler.END
    if text == "🛠 پنل ادمین":
        if not is_admin(user.id):
            await update.message.reply_text("دسترسی نداری.", reply_markup=KB_USER)
            return ConversationHandler.END
        admin_msg = (
            "🛠 پنل ادمین\n"
            "برای مدیریت سریع محتوا از دستور زیر استفاده کن:\n"
            "/setcontent <about|trust> <متن>\n\n"
            "برای رصد سفارش‌ها از منوی پیگیری استفاده کن یا امکانات بیشتر را بگو تا اضافه کنم."
        )
        await update.message.reply_text(admin_msg, reply_markup=KB_ADMIN)
        return ConversationHandler.END
    if text == "📊 اعلام وضعیت سفارش‌ها":
        stats = get_order_stats_for_identity(user.id, user.username)
        msg = (
            f"تعداد کل سفارشات: {stats['total']}\n"
            f"تعداد سفارشات در حال انجام: {stats['doing']}\n"
            f"تعداد سفارشات تکمیل شده: {stats['done']}"
        )
        await update.message.reply_text(msg, reply_markup=ORDER_MENU)
        return ConversationHandler.END
    if text == "⏳ سفارش‌های درحال انجام":
        statuses = ["ثبت شده", "در دست بررسی", "در حال بررسی", "تایید شده برای انجام"]
        lst = get_orders_for_user_by_statuses_identity(user.id, user.username, statuses)
        if not lst:
            await update.message.reply_text("سفارشی در حال انجام نیست.", reply_markup=ORDER_MENU)
            return ConversationHandler.END
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(o["title"], callback_data=f"orderinfo:{o['id']}")] for o in lst]
        )
        await update.message.reply_text("سفارش‌ مورد نظر را انتخاب کن:", reply_markup=inline_kb)
        return ConversationHandler.END
    if text == "✅ سفارش‌های تکمیل شده":
        statuses = ["انجام شده", "رد شده"]
        lst = get_orders_for_user_by_statuses_identity(user.id, user.username, statuses)
        if not lst:
            await update.message.reply_text("سفارشی تکمیل‌شده ثبت نشده.", reply_markup=ORDER_MENU)
            return ConversationHandler.END
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(o["title"], callback_data=f"orderinfo:{o['id']}")] for o in lst]
        )
        await update.message.reply_text("سفارش‌ مورد نظر را انتخاب کن:", reply_markup=inline_kb)
        return ConversationHandler.END
    if text == "🔎 چطور به ریشه اعتماد کنم؟ 🔎":
        value = get_content("trust")
        msg = value if value else "محتوای اعتماد هنوز تنظیم نشده. از ادمین بخواهید /setcontent trust ... را اجرا کند."
        await update.message.reply_text(msg, reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
        return ConversationHandler.END
    if text == "💬 اگه نمی‌دونی؛ از من بپرس! 💬":
        support_msg = (
            "💬 اگه درباره خدمات، ثبت سفارش یا هر بخش دیگه‌ای سؤال داری،\n"
            "برای این آیدی بنویس ✍️ یا ویس بفرست 🎙️\n"
            "پیامت مستقیم برای تیم پشتیبانی ریشه ارسال می‌شه 📩\n"
            "و کارشناسانمون در سریع‌ترین زمان ممکن بررسیش می‌کنن ⏳\n"
            "تا بتونیم به بهترین شکل ممکن راهنماییت کنیم 🤍\n"
            "کنارت هستیم.\n\n"
            "🆔 آیدی پشتیبانی:\n"
            "@rishehsupport"
        )
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(" ارتباط با پشتیبانی", url=SUPPORT_URL)]]
        )
        await update.message.reply_text(support_msg, reply_markup=inline_kb)
        return ConversationHandler.END
    if text == "🎥 آموزش تصویری":
        value = get_content("about")
        msg = value if value else "محتوای معرفی هنوز تنظیم نشده. از ادمین بخواهید /setcontent about ... را اجرا کند."
        await update.message.reply_text(msg, reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
        return ConversationHandler.END
    cats = get_categories_active()
    if any(((c.get("title") or "").strip()) == text for c in cats):
        selected = next((c for c in cats if ((c.get("title") or "").strip()) == text), None)
        cat = selected or get_category_by_title(text)
        items = get_items_by_category(selected["id"]) if selected else get_items_by_category_title(text)
        if is_admin(user.id):
            if items:
                ids = [i["id"] for i in items]
                counts = get_unfinished_counts_for_item_ids(ids)
                inline_kb = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(f"{i['title']} ({counts.get(i['id'], 0)})", callback_data=f"adminorders:{i['id']}")] for i in items]
                )
                await update.message.reply_text("آیتم را انتخاب کن:", reply_markup=inline_kb)
                return ConversationHandler.END
            await update.message.reply_text("آیتم فعالی در این دسته نیست.", reply_markup=KB_ADMIN)
            return ConversationHandler.END
        else:
            if items:
                inline_kb = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(i["title"], callback_data=f"item:{i['id']}")] for i in items]
                )
                msg = cat["description"] if (cat and cat.get("description")) else "لطفاً یک مورد را انتخاب کن."
                await update.message.reply_text(msg, reply_markup=inline_kb)
                return ConversationHandler.END
            if cat and cat.get("description"):
                rows = [[c["title"]] for c in cats] + [["🎥 آموزش تصویری"], [BACK_TEXT]]
                kb = ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
                await update.message.reply_text(cat["description"], reply_markup=kb)
                return ConversationHandler.END
    item = get_item_by_title(text)
    if item:
        same_items = get_items_by_category_title(item["category_title"]) or []
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(i["title"], callback_data=f"item:{i['id']}")] for i in same_items]
        )
        await update.message.reply_text(item.get("description") or "", reply_markup=inline_kb)
        return ConversationHandler.END
    await update.message.reply_text("از منو انتخاب کن.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
    return ConversationHandler.END

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("منوی اصلی نمایش داده شد.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    user = update.effective_user
    create_ticket(user.id, q)
    await update.message.reply_text("سوالت ثبت شد. به‌زودی پاسخ می‌دیم.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
    logger.info("ticket created user_id=%s", user.id)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("لغو شد.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
    return ConversationHandler.END

async def setcontent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("دسترسی نداری.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("فرمت: /setcontent <about|trust> <متن>")
        return
    key = context.args[0]
    value = " ".join(context.args[1:])
    if key not in {"about", "trust"}:
        await update.message.reply_text("کلید نامعتبر است.")
        return
    set_content(key, value)
    await update.message.reply_text("ذخیره شد.")
    logger.info("content set key=%s by user_id=%s", key, user.id)

async def addorder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت: /addorder <عنوان>")
        return
    user = update.effective_user
    title = " ".join(context.args)
    oid = add_order_for_user(user.id, title)
    if oid:
        await update.message.reply_text(f"سفارش #{oid} ثبت شد.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
        try:
            j = ""
            order = get_order_by_id(oid)
            if order and order.get("created_at"):
                j = to_jalali_str(order["created_at"])
            name = (user.first_name or "").strip() or (f"@{user.username}" if user.username else "کاربر")
            msg = f"سفارش جدید\nکاربر: {name}\nعنوان: {title}\nتاریخ: {j}"
            await notify_admins(context, msg)
        except Exception as e:
            logger.warning("notify admins on /addorder failed: %s", e)
    else:
        await update.message.reply_text("عنوان آیتم نامعتبر است یا ابتدا /start را بزن.")
    logger.info("addorder user_id=%s title=%s", user.id, title)

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("OK ✅")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception: %s", context.error)

def build_app():
    init_db()
    async def post_init(app: Application):
        text = "ربات با موفقیت راه‌اندازی شد ✅"
        if APP_URL:
            text += f"\nآدرس برنامه: {APP_URL}"
        for admin_id in ADMIN_USER_IDS:
            try:
                await app.bot.send_message(chat_id=admin_id, text=text)
            except Exception:
                pass
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("setcontent", setcontent))
    app.add_handler(CommandHandler("addorder", addorder))
    app.add_handler(CallbackQueryHandler(on_item_callback, pattern=r"^(item:\d+|order:\d+|back:cat:\d+|orderinfo:\d+|ordercancel:\d+|adminorders:\d+|adminorderinfo:\d+:\d+|adminstatus:\d+:\d+|adminstatusset:\d+:\d+|adminuser:\d+|adminuserrole:\d+|adminuserblock:\d+|adminusers)$"))
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        states={
            STATE_ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_error_handler(error_handler)
    return app

async def on_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("orderinfo:"):
        try:
            oid = int(data.split(":", 1)[1])
        except Exception:
            return
        order = get_order_by_id(oid)
        if not order:
            await query.message.reply_text("سفارش یافت نشد.")
            return
        ts = order.get("created_at") or ""
        j = to_jalali_str(ts)
        msg = f"سفارش #{order['id']}\nعنوان: {order['title']}\nوضعیت: {order['status']}\nتاریخ: {j}"
        can_cancel = False
        sid = order.get("statusid")
        if sid is not None:
            can_cancel = sid in (1, 2)
        else:
            st = (order.get("status") or "").strip()
            can_cancel = st in ("ثبت شده", "در دست بررسی")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("لغو سفارش", callback_data=f"ordercancel:{order['id']}")]]) if can_cancel else None
        await query.message.reply_text(msg, reply_markup=kb)
        return
    if data.startswith("ordercancel:"):
        try:
            oid = int(data.split(":", 1)[1])
        except Exception:
            return
        user = update.effective_user
        ok = cancel_order_by_id(oid, user.id)
        if ok:
            await query.message.edit_text("سفارش لغو شد ✅")
            await query.message.edit_reply_markup(reply_markup=None)
        else:
            await query.message.reply_text("لغو سفارش ممکن نیست.")
        return
    if data.startswith("adminorders:"):
        try:
            iid = int(data.split(":", 1)[1])
        except Exception:
            return
        orders = get_orders_by_item_admin(iid)
        if not orders:
            await query.message.reply_text("برای این آیتم سفارشی یافت نشد.")
            return
        def name_of(o):
            uname = o.get("username") or ""
            if uname:
                return f"@{uname}"
            fn = (o.get("firstname") or "").strip()
            ln = (o.get("lastname") or "").strip()
            full = (fn + " " + ln).strip()
            return full if full else "کاربر"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(name_of(o), callback_data=f"adminorderinfo:{o['id']}:{iid}")] for o in orders]
        )
        await query.message.reply_text("سفارش مورد نظر را انتخاب کن:", reply_markup=kb)
        return
    if data.startswith("adminorderinfo:"):
        try:
            _, oid, iid = data.split(":", 2)
            oid = int(oid); iid = int(iid)
        except Exception:
            return
        info = get_order_detail_admin(oid)
        if not info:
            await query.message.reply_text("سفارش یافت نشد.")
            return
        ts = info.get("created_at") or ""
        j = to_jalali_str(ts)
        uname = info.get("username") or ""
        name = f"@{uname}" if uname else ((info.get("firstname") or "") + " " + (info.get("lastname") or "")).strip() or "کاربر"
        desc = info.get("item_description") or ""
        msg = (
            f"نام ثبت‌کننده: {name}\n\n"
            f"عنوان درخواست: {info.get('item_title') or ''}\n\n"
            f"تاریخ ثبت: {j}\n\n"
            f"آخرین وضعیت: {info.get('status') or ''}\n\n"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("تغییر وضعیت", callback_data=f"adminstatus:{oid}:{iid}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"adminorders:{iid}")],
        ])
        await query.message.reply_text(msg, reply_markup=kb)
        return
    if data.startswith("adminstatus:"):
        try:
            _, oid, iid = data.split(":", 2)
            oid = int(oid); iid = int(iid)
        except Exception:
            return
        sts = get_all_statuses()
        if not sts:
            await query.message.reply_text("وضعیتی برای تغییر وجود ندارد.")
            return
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(s["title"], callback_data=f"adminstatusset:{oid}:{s['id'] or 0}")] for s in sts]
            + [[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"adminorderinfo:{oid}:{iid}")]]
        )
        await query.message.reply_text("یک وضعیت را انتخاب کن:", reply_markup=kb)
        return
    if data.startswith("adminstatusset:"):
        try:
            _, oid, sid = data.split(":", 2)
            oid = int(oid); sid = int(sid)
        except Exception:
            return
        ok = update_order_status_id(oid, sid if sid != 0 else None)
        if ok:
            await query.message.reply_text("وضعیت سفارش با موفقیت تغییر کرد ✅")
            try:
                info = get_order_detail_admin(oid)
                if info and info.get("telegramid"):
                    info2 = get_order_detail_admin(oid)
                    st_title = info2.get("status") if info2 else None
                    it_title = info2.get("item_title") if info2 else ""
                    try:
                        await context.bot.send_message(chat_id=info["telegramid"], text=f"وضعیت سفارش «{it_title}» به «{st_title or ''}» تغییر کرد")
                        logger.info("status change notified to user %s for order %s", info["telegramid"], oid)
                    except Exception as e:
                        logger.warning("notify user %s on status change failed: %s", info["telegramid"], e)
            except Exception as e:
                logger.warning("prepare user status notification failed: %s", e)
        else:
            await query.message.reply_text("تغییر وضعیت انجام نشد.")
        return
    if data == "adminusers":
        users = get_all_users_admin()
        if not users:
            await query.message.reply_text("کاربری یافت نشد.")
            return
        def label(u):
            if u.get("username"):
                return f"@{u['username']}"
            fn = (u.get("firstname") or "").strip()
            if fn:
                return fn
            return f"کاربر {u['id']}"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(label(u), callback_data=f"adminuser:{u['id']}")] for u in users]
        )
        await query.message.reply_text("یک کاربر را انتخاب کن:", reply_markup=kb)
        return
    if data.startswith("adminuser:"):
        try:
            uid = int(data.split(":", 1)[1])
        except Exception:
            return
        u = get_user_by_id(uid)
        if not u:
            await query.message.reply_text("کاربر یافت نشد.")
            return
        name = f"@{u['username']}" if u.get('username') else ((u.get('firstname') or '') + ' ' + (u.get('lastname') or ''))
        role = u.get('roleid')
        active = u.get('active')
        target_role = 2 if role == 1 else 1
        role_label = "کاربر" if target_role == 2 else "ادمین"
        block_label = "مسدود کردن کاربر" if active else "رفع مسدودی کاربر"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"تغییر نقش به {role_label}", callback_data=f"adminuserrole:{uid}")],
            [InlineKeyboardButton(block_label, callback_data=f"adminuserblock:{uid}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="adminusers")],
        ])
        await query.message.reply_text(f"مدیریت کاربر: {name}", reply_markup=kb)
        return
    if data.startswith("adminuserrole:"):
        try:
            uid = int(data.split(":", 1)[1])
        except Exception:
            return
        u = get_user_by_id(uid)
        if not u:
            await query.message.reply_text("کاربر یافت نشد.")
            return
        new_role = 2 if u.get('roleid') == 1 else 1
        if set_user_role(uid, new_role):
            await query.message.reply_text("نقش کاربر با موفقیت تغییر کرد ✅")
        else:
            await query.message.reply_text("تغییر نقش انجام نشد.")
        return
    if data.startswith("adminuserblock:"):
        try:
            uid = int(data.split(":", 1)[1])
        except Exception:
            return
        u = get_user_by_id(uid)
        if not u:
            await query.message.reply_text("کاربر یافت نشد.")
            return
        new_active = 0 if (u.get('active') or 0) != 0 else 1
        if set_user_active(uid, new_active):
            await query.message.reply_text("وضعیت کاربر به‌روزرسانی شد ✅")
        else:
            await query.message.reply_text("به‌روزرسانی انجام نشد.")
        return
    if data.startswith("item:"):
        try:
            item_id = int(data.split(":", 1)[1])
        except Exception:
            return
        item = get_item_by_id(item_id)
        if not item:
            return
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ ثبت سفارش", callback_data=f"order:{item['id']}")],
                [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"back:cat:{item['categoryid']}")],
            ]
        )
        await query.message.edit_text(item.get("description") or "")
        await query.message.edit_reply_markup(reply_markup=kb)
        return
    if data.startswith("order:"):
        try:
            item_id = int(data.split(":", 1)[1])
        except Exception:
            return
        item = get_item_by_id(item_id)
        if not item:
            return
        user = update.effective_user
        oid = create_order_for_item(user.id, item_id)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"back:cat:{item['categoryid']}")]]
        )
        await query.message.edit_text("سفارش ثبت شد ✅")
        await query.message.edit_reply_markup(reply_markup=kb)
        try:
            order = get_order_by_id(oid) if oid else None
            ts = order.get("created_at") if order else None
            j = to_jalali_str(ts) if ts else ""
            name = (user.first_name or "").strip() or (f"@{user.username}" if user.username else "کاربر")
            msg = f"سفارش جدید\nکاربر: {name}\nعنوان: {item['title']}\nتاریخ: {j}"
            await notify_admins(context, msg)
        except Exception as e:
            logger.warning("notify admins on new order failed: %s", e)
        return
    if data.startswith("back:cat:"):
        try:
            cat_id = int(data.split(":", 2)[2])
        except Exception:
            return
        items = get_items_by_category(cat_id) or []
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(i["title"], callback_data=f"item:{i['id']}")] for i in items]
        )
        await query.message.edit_reply_markup(reply_markup=inline_kb)

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است")
    app = build_app()
    app.run_polling()

def g2j(y, m, d):
    g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334]
    if y > 1600:
        jy = 979
        y -= 1600
    else:
        jy = 0
        y -= 621
    gy = y + 621
    leap_g = (gy+3)//4 - (gy+99)//100 + (gy+399)//400
    day = 365*y + (y+3)//4 - (y+99)//100 + (y+399)//400 - 80 + d + g_d_m[m-1]
    if m>2 and ((gy%4==0 and gy%100!=0) or (gy%400==0)):
        day += 1
    jy += 33*(day//12053)
    day %= 12053
    jy += 4*(day//1461)
    day %= 1461
    if day > 365:
        jy += (day-1)//365
        day = (day-1)%365
    jm = 1 + (day<186 and day//31 or (day-186)//30)
    jd = 1 + (day<186 and day%31 or (day-186)%30)
    return jy, jm, jd

def to_jalali_str(ts: str) -> str:
    try:
        dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        if TEHRAN_TZ is not None:
            ldt = dt.astimezone(TEHRAN_TZ)
        else:
            ldt = dt + timedelta(hours=3, minutes=30)
        jy,jm,jd = g2j(ldt.year, ldt.month, ldt.day)
        return f"{jy:04d}/{jm:02d}/{jd:02d} {ldt.strftime('%H:%M')}"
    except Exception:
        return ts

if __name__ == "__main__":
    main()
