import logging
import os
from datetime import datetime, timezone, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatMemberStatus
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, CallbackQueryHandler, filters
try:
    from zoneinfo import ZoneInfo
    TEHRAN_TZ = ZoneInfo("Asia/Tehran")
except Exception:
    TEHRAN_TZ = None
from .config import TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS, APP_URL, SOCIAL_TELEGRAM_URL, SOCIAL_INSTAGRAM_URL, SOCIAL_YOUTUBE_URL, SOCIAL_LINKEDIN_URL, WEBSITE_URL, SUPPORT_URL, MANDATORY_CHANNEL_ID, MANDATORY_CHANNEL_USERNAME, MANDATORY_CHANNEL_URL
import unicodedata
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
    get_categories_all,
    get_category_by_title,
    get_items_by_category_title,
    get_items_by_category,
    get_item_by_title,
    get_item_by_id,
    get_item_by_id_any,
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
    ensure_default_items,
    create_user_request,
    get_request_count_by_category,
    get_requests_by_category_admin,
    get_items_by_category_admin,
    set_item_active,
    set_item_main,
    add_category,
    add_item,
    add_item,
    add_tutorial,
    get_tutorials_all,
    get_tutorial_by_id,
    set_tutorial_active,
    delete_tutorial_by_id,
    get_items_main_titles,
)

STATE_ASK_QUESTION = 1
STATE_TUT_ADD = 2

MAIN_BUTTONS = [
    ["🚀 شروع همراهی 🚀"],
    ["📌 پیگیری سفارشاتم 📌"],
    ["🌿 ارتباط با ریشه", "🎥 آموزش تصویری"],
    ["🔎 چطور به ریشه اعتماد کنم؟ 🔎"],
    ["💬 اگه نمی‌دونی؛ از من بپرس! 💬"],
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

def user_main_kb() -> ReplyKeyboardMarkup:
    rows = [list(r) for r in MAIN_BUTTONS]
    try:
        mains = get_items_main_titles()
    except Exception:
        mains = []
    for it in mains:
        t = (it.get("title") or "").strip()
        if t:
            rows.append([t])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)

def _norm_fa(s: str) -> str:
    if not s:
        return ""
    s = str(s)
    s = s.replace("\u200c", "").replace("\u200f", "").replace("\u00a0", " ")
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = unicodedata.normalize("NFKC", s)
    s = " ".join(s.split())
    return s.strip()

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

def _mandatory_channel_id_or_username() -> str | int | None:
    cid = (MANDATORY_CHANNEL_ID or "").strip()
    if cid:
        # اگر شناسه عددی است، به int تبدیل شود
        try:
            return int(cid)
        except Exception:
            return cid
    uname = (MANDATORY_CHANNEL_USERNAME or "").strip()
    if uname:
        return uname
    return None

async def _is_member(bot, user_id: int) -> bool:
    channel = _mandatory_channel_id_or_username()
    if not channel:
        # اگر کانال تنظیم نشده، به‌صورت پیش‌فرض کاربر عضو در نظر گرفته می‌شود
        return True
    try:
        m = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        # سازگاری با نسخه‌های مختلف PTB: OWNER در v20+ و CREATOR در نسخه‌های قدیمی‌تر
        allowed = set()
        for name in ("MEMBER", "ADMINISTRATOR", "OWNER", "CREATOR"):
            val = getattr(ChatMemberStatus, name, None)
            if val is not None:
                allowed.add(val)
        return m.status in allowed if allowed else True
    except Exception as e:
        logger.warning("get_chat_member failed: %s", e)
        return False

def _force_join_kb(item_id: int) -> InlineKeyboardMarkup:
    join_url = (MANDATORY_CHANNEL_URL or "https://t.me/rishehapp")
    buttons = [
        [InlineKeyboardButton("📢 عضویت در کانال ریشه", url=join_url)],
        [InlineKeyboardButton("🔔 بررسی عضویت", callback_data=f"checkchannel:{item_id}")],
    ]
    return InlineKeyboardMarkup(buttons)

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> int:
    ids = _resolve_admin_ids()
    if not ids:
        logger.warning("no admin recipients to notify")
        return 0
    ok = 0
    for aid in ids:
        try:
            await context.bot.send_message(chat_id=aid, text=text, reply_markup=reply_markup)
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
        kb = user_main_kb()
    await update.message.reply_text(welcome_msg, reply_markup=kb)
    logger.info("/start handled for user_id=%s", user.id)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    user = update.effective_user
    pending_new = context.user_data.get("svc_new_item")
    pending_tut = context.user_data.get("tut_new")
    pending_cat = context.user_data.get("svc_new_cat")
    if pending_new:
        stage = pending_new.get("stage")
        cid = pending_new.get("cat_id")
        if text == BACK_TEXT:
            context.user_data.pop("svc_new_item", None)
            items_all = get_items_by_category_admin(cid) or []
            def marker(active):
                return "🟢" if (active or 0) != 0 else "⚪"
            buttons = [[InlineKeyboardButton(f"{marker(i['active'])} {i['title']}", callback_data=f"svcitem:{i['id']}:{cid}")] for i in items_all]
            buttons.append([InlineKeyboardButton("➕ افزودن آیتم جدید", callback_data=f"svcadd:{cid}")])
            inline_kb = InlineKeyboardMarkup(buttons) if buttons else None
            await update.message.reply_text("آیتم‌های این دسته:", reply_markup=inline_kb or KB_ADMIN)
            return ConversationHandler.END
        if stage == "ask_title":
            title = text
            if not title:
                await update.message.reply_text("عنوان معتبر وارد کن.")
                return ConversationHandler.END
            pending_new["title"] = title
            pending_new["stage"] = "ask_desc"
            context.user_data["svc_new_item"] = pending_new
            await update.message.reply_text("توضیحات آیتم را ارسال کن:")
            return ConversationHandler.END
        if stage == "ask_desc":
            desc = text
            title = pending_new.get("title")
            cid = int(cid)
            iid = add_item(cid, title, desc, 1)
            context.user_data.pop("svc_new_item", None)
            items_all = get_items_by_category_admin(cid) or []
            def marker(active):
                return "🟢" if (active or 0) != 0 else "⚪"
            buttons = [[InlineKeyboardButton(f"{marker(i['active'])} {i['title']}", callback_data=f"svcitem:{i['id']}:{cid}")] for i in items_all]
            buttons.append([InlineKeyboardButton("➕ افزودن آیتم جدید", callback_data=f"svcadd:{cid}")])
            inline_kb = InlineKeyboardMarkup(buttons) if buttons else None
            await update.message.reply_text("آیتم جدید اضافه شد ✅", reply_markup=inline_kb or KB_ADMIN)
            return ConversationHandler.END
    if pending_tut:
        stage = pending_tut.get("stage")
        if text == BACK_TEXT:
            context.user_data.pop("tut_new", None)
            tuts = get_tutorials_all()
            buttons = [[InlineKeyboardButton(t["title"], callback_data=f"tutitem:{t['id']}")] for t in tuts]
            buttons.append([InlineKeyboardButton("➕ افزودن آموزش جدید", callback_data="tutadd")])
            await update.message.reply_text("ویدیوهای آموزشی:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else KB_ADMIN)
            return ConversationHandler.END
        if stage == "ask_title":
            pending_tut["title"] = text
            pending_tut["stage"] = "ask_desc"
            context.user_data["tut_new"] = pending_tut
            await update.message.reply_text("توضیحات آموزش را ارسال کن:")
            return ConversationHandler.END
        if stage == "ask_desc":
            pending_tut["description"] = text
            pending_tut["stage"] = "ask_src"
            context.user_data["tut_new"] = pending_tut
            await update.message.reply_text("لینک ویدیو را ارسال کن یا فایل ویدیو را آپلود کن.")
            return ConversationHandler.END
        if stage == "ask_src":
            link = text.strip()
            if not link:
                await update.message.reply_text("لینک معتبر ارسال کن یا فایل ویدیو را آپلود کن.")
                return ConversationHandler.END
            title = pending_tut.get("title")
            desc = pending_tut.get("description")
            tid = add_tutorial(title, desc, None, link, 1)
            context.user_data.pop("tut_new", None)
            tuts = get_tutorials_all()
            buttons = [[InlineKeyboardButton(t["title"], callback_data=f"tutitem:{t['id']}")] for t in tuts]
            buttons.append([InlineKeyboardButton("➕ افزودن آموزش جدید", callback_data="tutadd")])
            await update.message.reply_text("آموزش جدید ذخیره شد ✅", reply_markup=InlineKeyboardMarkup(buttons) if buttons else KB_ADMIN)
            return ConversationHandler.END
    # فرآیند افزودن دسته‌بندی جدید
    if pending_cat:
        stage = pending_cat.get("stage")
        if text == BACK_TEXT:
            context.user_data.pop("svc_new_cat", None)
            cats = get_categories_all()
            rows = [[c["title"]] for c in cats] if cats else []
            rows.append(["➕ افزودن دسته‌بندی جدید"])
            rows.append([BACK_TEXT])
            kb = ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
            await update.message.reply_text("یک دسته‌بندی خدمات را انتخاب کن:", reply_markup=kb)
            return ConversationHandler.END
        if stage == "ask_title":
            pending_cat["title"] = text
            pending_cat["stage"] = "ask_desc"
            context.user_data["svc_new_cat"] = pending_cat
            await update.message.reply_text("توضیحات دسته را ارسال کن:")
            return ConversationHandler.END
        if stage == "ask_desc":
            title = (pending_cat.get("title") or "").strip()
            desc = text
            context.user_data.pop("svc_new_cat", None)
            add_category(title, desc, 0, 1)
            cats = get_categories_all()
            rows = [[c["title"]] for c in cats] if cats else []
            rows.append(["➕ افزودن دسته‌بندی جدید"])
            rows.append([BACK_TEXT])
            kb = ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
            await update.message.reply_text("دسته‌بندی جدید ذخیره شد ✅", reply_markup=kb)
            return ConversationHandler.END
    pending_cat = context.user_data.pop("awaiting_custom_request", None)
    if pending_cat is not None:
        try:
            cat_id = int(pending_cat)
        except Exception:
            cat_id = None
        get_or_create_user(user.id, user.username, user.first_name, user.last_name)
        rid = create_user_request(user.id, text, cat_id)
        if rid:
            await update.message.reply_text("درخواستت ثبت شد ✅", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
        else:
            await update.message.reply_text("ثبت درخواست انجام نشد.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
        return ConversationHandler.END
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
            context.user_data["svc_manage"] = True
            cats = get_categories_all()
            rows = [[c["title"]] for c in cats] if cats else []
            rows.append(["➕ افزودن دسته‌بندی جدید"])
            rows.append([BACK_TEXT])
            kb = ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
            await update.message.reply_text("یک دسته‌بندی خدمات را انتخاب کن:", reply_markup=kb)
            return ConversationHandler.END
        if text == "🎓 مدیریت بخش آموزش":
            tuts = get_tutorials_all()
            buttons = [[InlineKeyboardButton(t["title"], callback_data=f"tutitem:{t['id']}")] for t in tuts]
            buttons.append([InlineKeyboardButton("➕ افزودن آموزش جدید", callback_data="tutadd")])
            kb = InlineKeyboardMarkup(buttons) if buttons else None
            await update.message.reply_text("ویدیوهای آموزشی:", reply_markup=kb or KB_ADMIN)
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
        context.user_data.pop("svc_manage", None)
        await update.message.reply_text("بازگشت به منوی اصلی.", reply_markup=(KB_ADMIN if is_admin(user.id) else user_main_kb()))
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
            rows = [[c["title"]] for c in cats] + [[BACK_TEXT]]
            kb = ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
            await update.message.reply_text(msg, reply_markup=kb)
        else:
            await update.message.reply_text(msg, reply_markup=(KB_ADMIN if is_admin(user.id) else user_main_kb()))
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
        await update.message.reply_text(msg, reply_markup=(KB_ADMIN if is_admin(user.id) else user_main_kb()))
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
        tuts = [t for t in get_tutorials_all() if (t.get("active") or 0) != 0]
        if not tuts:
            await update.message.reply_text("آموزشی برای نمایش وجود ندارد.", reply_markup=(KB_ADMIN if is_admin(user.id) else KB_USER))
            return ConversationHandler.END
        start = 0
        page = tuts[start:start+10]
        buttons = [[InlineKeyboardButton(t["title"], callback_data=f"tutview:{t['id']}")] for t in page]
        nav = []
        if len(tuts) > 10:
            if start > 0:
                nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"tutpage:{max(0, start-10)}"))
            if start + 10 < len(tuts):
                nav.append(InlineKeyboardButton("▶️ بعدی", callback_data=f"tutpage:{start+10}"))
        if nav:
            buttons.append(nav)
        inline_kb = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("یک آموزش را انتخاب کن:", reply_markup=inline_kb)
        return ConversationHandler.END
    # جریان مدیریت خدمات برای ادمین
    if is_admin(user.id) and context.user_data.get("svc_manage"):
        # افزودن دسته‌بندی جدید
        if text == "➕ افزودن دسته‌بندی جدید":
            context.user_data["svc_new_cat"] = {"stage": "ask_title"}
            await update.message.reply_text("عنوان دسته‌بندی جدید را ارسال کن:")
            return ConversationHandler.END
        cats_all = get_categories_all()
        norm_text = _norm_fa(text)
        selected = None
        for c in cats_all:
            ct = _norm_fa(c.get("title") or "")
            if ct == norm_text or norm_text in ct or ct in norm_text:
                selected = c
                break
        if selected:
            items_all = get_items_by_category_admin(selected["id"]) or []
            def marker(active):
                return "🟢" if (active or 0) != 0 else "⚪"
            buttons = [
                [InlineKeyboardButton(f"{marker(i['active'])} {i['title']}", callback_data=f"svcitem:{i['id']}:{selected['id']}")]
                for i in items_all
            ]
            buttons.append([InlineKeyboardButton("➕ افزودن آیتم جدید", callback_data=f"svcadd:{selected['id']}")])
            inline_kb = InlineKeyboardMarkup(buttons) if buttons else None
            await update.message.reply_text("آیتم‌های این دسته:", reply_markup=inline_kb or KB_ADMIN)
            return ConversationHandler.END
        # اگر متن با هیچ دسته‌ای مطابق نبود، به منوی ادمین برگرد
        await update.message.reply_text("از لیست دسته‌ها انتخاب کن.", reply_markup=KB_ADMIN)
        context.user_data.pop("svc_manage", None)
        return ConversationHandler.END

    cats = get_categories_active()
    norm_text = _norm_fa(text)
    selected = None
    for c in cats:
        ct = _norm_fa(c.get("title") or "")
        if ct == norm_text or norm_text in ct or ct in norm_text:
            selected = c
            break
    cat = selected or get_category_by_title(text)
    items = get_items_by_category(selected["id"]) if selected else get_items_by_category_title(text)
    if is_admin(user.id):
        if items:
            ids = [i["id"] for i in items]
            counts = get_unfinished_counts_for_item_ids(ids)
            rows = [[InlineKeyboardButton(f"{i['title']} ({counts.get(i['id'], 0)})", callback_data=f"adminorders:{i['id']}")] for i in items]
            try:
                cat_id = (selected["id"] if selected else (cat["id"] if cat else None))
            except Exception:
                cat_id = None
            if cat_id is not None:
                rc = get_request_count_by_category(cat_id)
                rows.append([InlineKeyboardButton(f"درخواست های شخصی کاربران ({rc})", callback_data=f"adminreqs:{cat_id}")])
            inline_kb = InlineKeyboardMarkup(rows)
            await update.message.reply_text("آیتم را انتخاب کن:", reply_markup=inline_kb)
            return ConversationHandler.END
        await update.message.reply_text("آیتم فعالی در این دسته نیست.", reply_markup=KB_ADMIN)
        return ConversationHandler.END
    else:
        if items:
            buttons = [[InlineKeyboardButton(i["title"], callback_data=f"item:{i['id']}")] for i in items]
            cat_id = (selected["id"] if selected else (cat["id"] if cat else None))
            if cat_id is not None:
                buttons.append([InlineKeyboardButton("اونیکه میخوام نیست", callback_data=f"customreq:{cat_id}")])
            inline_kb = InlineKeyboardMarkup(buttons)
            msg = cat["description"] if (cat and cat.get("description")) else "لطفاً یک مورد را انتخاب کن."
            await update.message.reply_text(msg, reply_markup=inline_kb)
            return ConversationHandler.END
        if cat and cat.get("description"):
            rows = [[c["title"]] for c in cats] + [[BACK_TEXT]]
            kb = ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
            await update.message.reply_text(cat["description"], reply_markup=kb)
            return ConversationHandler.END
    item = get_item_by_title(text)
    if item:
        # اگر از منوی اصلی باشد (ismain=1)، فقط دکمه ثبت سفارش نمایش داده شود
        is_main = (item.get("ismain") or 0) != 0
        if is_main:
            inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ ثبت سفارش", callback_data=f"order:{item['id']}")]])
            await update.message.reply_text(item.get("description") or "", reply_markup=inline_kb)
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton("✅ ثبت سفارش", callback_data=f"order:{item['id']}")]]
        same_items = get_items_by_category_title(item["category_title"]) or []
        if same_items:
            buttons.extend([[InlineKeyboardButton(i["title"], callback_data=f"item:{i['id']}")] for i in same_items])
        try:
            cat_id = item.get("categoryid")
            if cat_id is not None:
                buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"back:cat:{cat_id}")])
        except Exception:
            pass
        inline_kb = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(item.get("description") or "", reply_markup=inline_kb)
        return ConversationHandler.END
        await update.message.reply_text("از منو انتخاب کن.", reply_markup=(KB_ADMIN if is_admin(user.id) else user_main_kb()))
    return ConversationHandler.END

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("منوی اصلی نمایش داده شد.", reply_markup=(KB_ADMIN if is_admin(user.id) else user_main_kb()))


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    user = update.effective_user
    create_ticket(user.id, q)
    await update.message.reply_text("سوالت ثبت شد. به‌زودی پاسخ می‌دیم.", reply_markup=(KB_ADMIN if is_admin(user.id) else user_main_kb()))
    logger.info("ticket created user_id=%s", user.id)
    return ConversationHandler.END

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_tut = context.user_data.get("tut_new")
    if not pending_tut or pending_tut.get("stage") != "ask_src":
        return
    v = update.message.video
    d = update.message.document
    file = None
    filename = None
    if v is not None:
        file = v
        filename = None
    elif d is not None and (d.mime_type or "").startswith("video/"):
        file = d
        filename = d.file_name
    if not file:
        return
    # آماده‌سازی مسیر ذخیره فایل
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    vid_dir = os.path.join(base_dir, "files", "videos")
    try:
        os.makedirs(vid_dir, exist_ok=True)
    except Exception:
        pass
    # نام فایل امن
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(filename)[1] if filename else ".mp4"
    dest_path = os.path.join(vid_dir, f"tut_{ts}{ext}")
    tg_file = await context.bot.get_file(file.file_id)
    try:
        await tg_file.download_to_drive(dest_path)
    except Exception:
        # fallback
        await tg_file.download(dest_path)
    title = pending_tut.get("title")
    desc = pending_tut.get("description")
    add_tutorial(title, desc, dest_path, None, 1)
    context.user_data.pop("tut_new", None)
    tuts = get_tutorials_all()
    buttons = [[InlineKeyboardButton(t["title"], callback_data=f"tutitem:{t['id']}")] for t in tuts]
    buttons.append([InlineKeyboardButton("➕ افزودن آموزش جدید", callback_data="tutadd")])
    await update.message.reply_text("آموزش جدید ذخیره شد ✅", reply_markup=InlineKeyboardMarkup(buttons) if buttons else KB_ADMIN)
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

async def membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ch = _mandatory_channel_id_or_username()
        user = update.effective_user
        st = await _is_member(context.bot, user.id)
        msg = f"کانال: {ch or '-'}\nوضعیت عضویت: {'عضو' if st else 'عضو نیست'}"
    except Exception as e:
        msg = f"بررسی ناموفق: {e}"
    await update.message.reply_text(msg)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception: %s", context.error)

def build_app():
    init_db()
    ensure_default_items()
    async def post_init(app: Application):
        text = "ربات با موفقیت راه‌اندازی شد ✅"
        if APP_URL:
            text += f"\nآدرس برنامه: {APP_URL}"
        try:
            ch = _mandatory_channel_id_or_username()
            if ch:
                text += f"\nکانال اجباری: {ch}"
        except Exception:
            pass
        for admin_id in ADMIN_USER_IDS:
            try:
                await app.bot.send_message(chat_id=admin_id, text=text)
            except Exception:
                pass
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("membership", membership))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("setcontent", setcontent))
    app.add_handler(CommandHandler("addorder", addorder))
    app.add_handler(CallbackQueryHandler(on_item_callback, pattern=r"^(item:\d+|order:\d+|back:cat:\d+|orderinfo:\d+|ordercancel:\d+|adminorders:\d+|adminorderinfo:\d+:\d+|adminstatus:\d+:\d+|adminstatusset:\d+:\d+|adminuser:\d+|adminuserrole:\d+|adminuserblock:\d+|adminusers|customreq:\d+|adminreqs:\d+|adminreqinfo:\d+:\d+|svcitem:\d+:\d+|svcset:\d+:\d+:\d+|svcmain:\d+:\d+:\d+|svcback:\d+|svcadd:\d+|tutitem:\d+|tutset:\d+:\d+|tutdel:\d+|tutback|tutadd|tutview:\d+|tutpage:\d+|checkchannel:\d+)$"))
    app.add_handler(MessageHandler((filters.VIDEO | filters.Document.ALL), handle_media))
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
    if data.startswith("svcitem:"):
        try:
            _, iid, cid = data.split(":", 2)
            iid = int(iid); cid = int(cid)
        except Exception:
            return
        it = get_item_by_id_any(iid)
        if not it:
            await query.message.reply_text("آیتم یافت نشد.")
            return
        active = (it.get("active") or 0) != 0
        ismain = (it.get("ismain") or 0) != 0
        toggle_label = "غیرفعال کردن" if active else "فعال کردن"
        toggle_to = 0 if active else 1
        main_label = "حذف از منوی اصلی" if ismain else "افزودن به منوی اصلی"
        main_to = 0 if ismain else 1
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"svcset:{it['id']}:{toggle_to}:{cid}")],
            [InlineKeyboardButton(main_label, callback_data=f"svcmain:{it['id']}:{main_to}:{cid}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"svcback:{cid}")],
        ])
        status_txt = "فعال" if active else "غیرفعال"
        main_txt = "بله" if ismain else "خیر"
        await query.message.reply_text(
            f"مدیریت آیتم: {it.get('title') or ''}\nوضعیت فعلی: {status_txt}\nدر منوی اصلی: {main_txt}",
            reply_markup=kb,
        )
        return
    if data.startswith("svcadd:"):
        try:
            cid = int(data.split(":", 1)[1])
        except Exception:
            return
        context.user_data["svc_new_item"] = {"cat_id": cid, "stage": "ask_title"}
        await query.message.reply_text("عنوان آیتم جدید را ارسال کن:")
        return
    if data.startswith("svcset:"):
        try:
            _, iid, val, cid = data.split(":", 3)
            iid = int(iid); val = int(val); cid = int(cid)
        except Exception:
            return
        ok = set_item_active(iid, val)
        it = get_item_by_id_any(iid)
        active = (it.get("active") or 0) != 0 if it else (val != 0)
        ismain = (it.get("ismain") or 0) != 0 if it else False
        toggle_label = "غیرفعال کردن" if active else "فعال کردن"
        toggle_to = 0 if active else 1
        main_label = "حذف از منوی اصلی" if ismain else "افزودن به منوی اصلی"
        main_to = 0 if ismain else 1
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"svcset:{iid}:{toggle_to}:{cid}")],
            [InlineKeyboardButton(main_label, callback_data=f"svcmain:{iid}:{main_to}:{cid}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"svcback:{cid}")],
        ])
        if ok:
            await query.message.reply_text("وضعیت آیتم به‌روزرسانی شد ✅", reply_markup=kb)
        else:
            await query.message.reply_text("به‌روزرسانی وضعیت انجام نشد.", reply_markup=kb)
        return
    if data.startswith("svcmain:"):
        try:
            _, iid, val, cid = data.split(":", 3)
            iid = int(iid); val = int(val); cid = int(cid)
        except Exception:
            return
        ok = set_item_main(iid, val)
        it = get_item_by_id_any(iid)
        active = (it.get("active") or 0) != 0 if it else True
        ismain = (it.get("ismain") or 0) != 0 if it else (val != 0)
        toggle_label = "غیرفعال کردن" if active else "فعال کردن"
        toggle_to = 0 if active else 1
        main_label = "حذف از منوی اصلی" if ismain else "افزودن به منوی اصلی"
        main_to = 0 if ismain else 1
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"svcset:{iid}:{toggle_to}:{cid}")],
            [InlineKeyboardButton(main_label, callback_data=f"svcmain:{iid}:{main_to}:{cid}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"svcback:{cid}")],
        ])
        if ok:
            await query.message.reply_text("منوی اصلی آیتم به‌روزرسانی شد ✅", reply_markup=kb)
        else:
            await query.message.reply_text("به‌روزرسانی منوی اصلی انجام نشد.", reply_markup=kb)
        return
    if data.startswith("svcback:"):
        try:
            cid = int(data.split(":", 1)[1])
        except Exception:
            return
        items_all = get_items_by_category_admin(cid) or []
        def marker(active):
            return "🟢" if (active or 0) != 0 else "⚪"
        buttons = [
            [InlineKeyboardButton(f"{marker(i['active'])} {i['title']}", callback_data=f"svcitem:{i['id']}:{cid}")]
            for i in items_all
        ]
        buttons.append([InlineKeyboardButton("➕ افزودن آیتم جدید", callback_data=f"svcadd:{cid}")])
        inline_kb = InlineKeyboardMarkup(buttons) if buttons else None
        if inline_kb:
            await query.message.reply_text("آیتم‌های این دسته:", reply_markup=inline_kb)
        else:
            await query.message.reply_text("آیتمی برای این دسته ثبت نشده.")
        return
    if data == "tutadd":
        context.user_data["tut_new"] = {"stage": "ask_title"}
        await query.message.reply_text("عنوان آموزش را ارسال کن:")
        return
    if data == "tutback":
        tuts = get_tutorials_all()
        buttons = [[InlineKeyboardButton(t["title"], callback_data=f"tutitem:{t['id']}")] for t in tuts]
        buttons.append([InlineKeyboardButton("➕ افزودن آموزش جدید", callback_data="tutadd")])
        await query.message.reply_text("ویدیوهای آموزشی:", reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)
        return
    if data.startswith("tutitem:"):
        try:
            tid = int(data.split(":", 1)[1])
        except Exception:
            return
        t = get_tutorial_by_id(tid)
        if not t:
            await query.message.reply_text("آموزش یافت نشد.")
            return
        active = (t.get("active") or 0) != 0
        toggle_to = 0 if active else 1
        toggle_label = "غیرفعال کردن" if active else "فعال کردن"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"tutset:{tid}:{toggle_to}")],
            [InlineKeyboardButton("🗑 حذف آموزش", callback_data=f"tutdel:{tid}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="tutback")],
        ])
        src = t.get("filelink") or t.get("filepath") or "—"
        await query.message.reply_text(f"آموزش: {t.get('title') or ''}\nوضعیت: {'فعال' if active else 'غیرفعال'}\nمنبع: {src}", reply_markup=kb)
        return
    if data.startswith("tutset:"):
        try:
            _, tid, val = data.split(":", 2)
            tid = int(tid); val = int(val)
        except Exception:
            return
        ok = set_tutorial_active(tid, val)
        if ok:
            await query.message.reply_text("وضعیت آموزش به‌روزرسانی شد ✅")
        else:
            await query.message.reply_text("به‌روزرسانی انجام نشد.")
        return
    if data.startswith("tutdel:"):
        try:
            tid = int(data.split(":", 1)[1])
        except Exception:
            return
        t = get_tutorial_by_id(tid)
        ok = delete_tutorial_by_id(tid)
        if ok:
            try:
                fp = (t.get("filepath") or "").strip() if t else ""
                if fp and os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
            await query.message.reply_text("آموزش حذف شد ✅")
        else:
            await query.message.reply_text("حذف انجام نشد.")
        return
    if data.startswith("tutview:"):
        try:
            tid = int(data.split(":", 1)[1])
        except Exception:
            return
        t = get_tutorial_by_id(tid)
        if not t or (t.get("active") or 0) == 0:
            await query.message.reply_text("آموزش یافت نشد یا غیرفعال است.")
            return
        title = t.get("title") or ""
        desc = t.get("description") or ""
        msg = f"{title}\n\n{desc}".strip()
        link = (t.get("filelink") or "").strip()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("مشاهده ویدیو", url=link)]]) if link else None
        fp = (t.get("filepath") or "").strip()
        if fp and os.path.isfile(fp):
            try:
                with open(fp, "rb") as f:
                    await query.message.reply_video(video=f, caption=msg, reply_markup=kb)
                return
            except Exception:
                pass
        await query.message.reply_text(msg, reply_markup=kb)
        return
    if data.startswith("tutpage:"):
        try:
            start = int(data.split(":", 1)[1])
        except Exception:
            return
        tuts_all = [t for t in get_tutorials_all() if (t.get("active") or 0) != 0]
        if not tuts_all:
            await query.message.reply_text("آموزشی برای نمایش وجود ندارد.")
            return
        if start < 0:
            start = 0
        if start >= len(tuts_all):
            start = max(0, (len(tuts_all) - 1) // 10 * 10)
        page = tuts_all[start:start+10]
        buttons = [[InlineKeyboardButton(t["title"], callback_data=f"tutview:{t['id']}")] for t in page]
        nav = []
        if len(tuts_all) > 10:
            if start > 0:
                nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"tutpage:{max(0, start-10)}"))
            if start + 10 < len(tuts_all):
                nav.append(InlineKeyboardButton("▶️ بعدی", callback_data=f"tutpage:{start+10}"))
        if nav:
            buttons.append(nav)
        await query.message.reply_text("یک آموزش را انتخاب کن:", reply_markup=InlineKeyboardMarkup(buttons))
        return
    if data.startswith("customreq:"):
        try:
            cid = int(data.split(":", 1)[1])
        except Exception:
            return
        context.user_data["awaiting_custom_request"] = cid
        await query.message.reply_text("لطفاً درخواستت رو کامل و دقیق بنویس و ارسال کن ✍️")
        return
    if data.startswith("adminreqs:"):
        try:
            cid = int(data.split(":", 1)[1])
        except Exception:
            return
        reqs = get_requests_by_category_admin(cid)
        if not reqs:
            await query.message.reply_text("درخواستی برای این دسته ثبت نشده.")
            return
        def label(r):
            uname = r.get("username") or ""
            if uname:
                base = f"@{uname}"
            else:
                fn = (r.get("firstname") or "").strip()
                ln = (r.get("lastname") or "").strip()
                base = (fn + " " + ln).strip() or "کاربر"
            desc = (r.get("description") or "").strip().split("\n")[0]
            if len(desc) > 20:
                desc = desc[:20] + "…"
            st = (r.get("status") or "").strip()
            return f"{base} — {desc} ({st})"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(label(r), callback_data=f"adminreqinfo:{r['id']}:{cid}")] for r in reqs[:50]]
        )
        await query.message.reply_text("درخواست را انتخاب کن:", reply_markup=kb)
        return
    if data.startswith("adminreqinfo:"):
        try:
            _, rid, cid = data.split(":", 2)
            rid = int(rid); cid = int(cid)
        except Exception:
            return
        # ساده: برای این نسخه، متن درخواست در همان لیست کافی است؛
        # در صورت نیاز می‌توان جزئیات بیشتر را اضافه کرد.
        reqs = get_requests_by_category_admin(cid)
        r = next((x for x in reqs if x.get("id") == rid), None)
        if not r:
            await query.message.reply_text("درخواست یافت نشد.")
            return
        uname = r.get("username") or ""
        name = f"@{uname}" if uname else ((r.get("firstname") or "") + " " + (r.get("lastname") or "")).strip() or "کاربر"
        st = r.get("status") or ""
        msg = f"درخواست #{r['id']}\nکاربر: {name}\nوضعیت: {st}\n\nمتن:\n{r.get('description') or ''}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"adminreqs:{cid}")]])
        await query.message.reply_text(msg, reply_markup=kb)
        return
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
        contact_url = None
        uname = (info.get("username") or "").strip()
        tid = info.get("telegramid") or info.get("telegram_id")
        if uname:
            contact_url = f"https://t.me/{uname}"
        elif tid:
            contact_url = f"tg://user?id={tid}"
        first_row = [InlineKeyboardButton("تغییر وضعیت", callback_data=f"adminstatus:{oid}:{iid}")]
        if contact_url:
            first_row.append(InlineKeyboardButton("ارتباط با کاربر", url=contact_url))
        kb = InlineKeyboardMarkup([
            first_row,
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
        if not await _is_member(context.bot, user.id):
            txt = (
                "📢 قبل از اینکه ادامه بدیم،\n"
                "لازمه عضو کانال رسمی ریشه باشی.\n"
                "بعد از عضویت، روی «بررسی عضویت» بزن تا ادامه بدیم."
            )
            await query.message.reply_text(txt, reply_markup=_force_join_kb(item_id))
            return
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
            manage_kb = InlineKeyboardMarkup([[InlineKeyboardButton("مدیریت سفارش", callback_data=f"adminorderinfo:{oid}:{item['id']}")]]) if (oid and item) else None
            await notify_admins(context, msg, reply_markup=manage_kb)
        except Exception as e:
            logger.warning("notify admins on new order failed: %s", e)
        return
    if data.startswith("checkchannel:"):
        try:
            item_id = int(data.split(":", 1)[1])
        except Exception:
            return
        item = get_item_by_id(item_id)
        if not item:
            return
        user = update.effective_user
        if not await _is_member(context.bot, user.id):
            txt = (
                "هنوز عضویت تایید نشد.\n"
                "پس از عضویت، دوباره روی «بررسی عضویت» بزن."
            )
            await query.message.reply_text(txt, reply_markup=_force_join_kb(item_id))
            return
        oid = create_order_for_item(user.id, item_id)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"back:cat:{item['categoryid']}")]]
        )
        await query.message.reply_text("سفارش ثبت شد ✅", reply_markup=kb)
        try:
            order = get_order_by_id(oid) if oid else None
            ts = order.get("created_at") if order else None
            j = to_jalali_str(ts) if ts else ""
            name = (user.first_name or "").strip() or (f"@{user.username}" if user.username else "کاربر")
            msg = f"سفارش جدید\nکاربر: {name}\nعنوان: {item['title']}\nتاریخ: {j}"
            manage_kb = InlineKeyboardMarkup([[InlineKeyboardButton("مدیریت سفارش", callback_data=f"adminorderinfo:{oid}:{item['id']}")]]) if (oid and item) else None
            await notify_admins(context, msg, reply_markup=manage_kb)
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
