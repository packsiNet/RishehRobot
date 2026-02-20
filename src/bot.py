import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, CallbackQueryHandler, filters
from .config import TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS, APP_URL
from .db import (
    init_db,
    get_or_create_user,
    get_orders_for_user,
    get_orders_for_user_by_status,
    get_orders_for_user_by_statuses,
    get_orders_for_identity,
    get_orders_for_user_by_statuses_identity,
    get_order_by_id,
    get_order_stats_for_user,
    get_order_stats_for_identity,
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
)

STATE_ASK_QUESTION = 1

MAIN_BUTTONS = [
    ["🚀 شروع همراهی 🚀"],
    ["📌 پیگیری سفارشاتم 📌"],
    ["🔎 چطور به ریشه اعتماد کنم؟ 🔎"],
    ["💬 اگه نمی‌دونی؛ از من بپرس! 💬"],
    ["🌿 ریشه چیه؟ 🌿"],
]

KB = ReplyKeyboardMarkup(MAIN_BUTTONS, resize_keyboard=True, is_persistent=True)
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("rishehbot")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    welcome_msg = (
        "🌿 ریشه؛ جایی برای اینکه حتی از دور هم کنار خانواده‌ت باشی\n"
        "ریشه برای وقت‌هایی شکل گرفت که از خونه دوری، 🏠\n"
        "اما نمی‌خوای فاصله باعث بشه از مراقبت و پیگیری جا بمونی. 🤍\n"
        "برای اینکه از وضعیت سلامت عزیزت باخبر باشی، 🩺\n"
        "نیازهاشون رو مدیریت کنی و با خیال راحت‌تری زندگی کنی. 🕊️\n"
        "اینجا خدمات سلامت، همراهی و کارهای روزمره خانواده تو یک ساختار یکپارچه کنار هم قرار گرفته 🔗\n"
        "تا بتونی با آگاهی بیشتر و دغدغه کمتر کنارشون بمونی. 🌱\n"
        "اگه آماده‌ای این همراهی رو شروع کنی، قدم اول رو تو بردار. 👣\n"
        "✨ از منو یکی از مسیرها رو انتخاب کن تا با هم جلو بریم."
    )
    await update.message.reply_text(welcome_msg, reply_markup=KB)
    logger.info("/start handled for user_id=%s", user.id)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    if text == BACK_TEXT:
        await update.message.reply_text("بازگشت به منوی اصلی.", reply_markup=KB)
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
            kb = ReplyKeyboardMarkup([[c["title"]] for c in cats] + [[BACK_TEXT]], resize_keyboard=True, is_persistent=True)
            await update.message.reply_text(msg, reply_markup=kb)
        else:
            await update.message.reply_text(msg, reply_markup=KB)
        return ConversationHandler.END
    if text == "📌 پیگیری سفارشاتم 📌":
        msg = (
            "🔄 همراهی همیشه برقراره!\n"
            "اگه قبلاً از ریشه خدمتی گرفتی یا سفارشی ثبت کردی،\n"
            "اینجا می‌تونی وضعیتش رو ببینی 👀"
        )
        await update.message.reply_text(msg, reply_markup=ORDER_MENU)
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
        await update.message.reply_text(msg, reply_markup=KB)
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
            [[InlineKeyboardButton(" ارتباط با پشتیبانی", url="https://t.me/rishehsupport")]]
        )
        await update.message.reply_text(support_msg, reply_markup=inline_kb)
        return ConversationHandler.END
    if text == "🌿 ریشه چیه؟ 🌿":
        value = get_content("about")
        msg = value if value else "محتوای معرفی هنوز تنظیم نشده. از ادمین بخواهید /setcontent about ... را اجرا کند."
        await update.message.reply_text(msg, reply_markup=KB)
        return ConversationHandler.END
    cats = get_categories_active()
    if any(c["title"] == text for c in cats):
        cat = get_category_by_title(text)
        items = get_items_by_category_title(text)
        if items:
            inline_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton(i["title"], callback_data=f"item:{i['id']}")] for i in items]
            )
            msg = cat["description"] if (cat and cat.get("description")) else "لطفاً یک مورد را انتخاب کن."
            await update.message.reply_text(msg, reply_markup=inline_kb)
            return ConversationHandler.END
        if cat and cat.get("description"):
            kb = ReplyKeyboardMarkup([[c["title"]] for c in cats] + [[BACK_TEXT]], resize_keyboard=True, is_persistent=True)
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
    await update.message.reply_text("از منو انتخاب کن.", reply_markup=KB)
    return ConversationHandler.END

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("منوی اصلی نمایش داده شد.", reply_markup=KB)


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    user = update.effective_user
    create_ticket(user.id, q)
    await update.message.reply_text("سوالت ثبت شد. به‌زودی پاسخ می‌دیم.", reply_markup=KB)
    logger.info("ticket created user_id=%s", user.id)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد.", reply_markup=KB)
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
        await update.message.reply_text(f"سفارش #{oid} ثبت شد.", reply_markup=KB)
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
    app.add_handler(CallbackQueryHandler(on_item_callback, pattern=r"^(item:\d+|order:\d+|back:cat:\d+|orderinfo:\d+|ordercancel:\d+)$"))
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
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("لغو سفارش", callback_data=f"ordercancel:{order['id']}")]])
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
        create_order_for_item(user.id, item_id)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"back:cat:{item['categoryid']}")]]
        )
        await query.message.edit_text("سفارش ثبت شد ✅")
        await query.message.edit_reply_markup(reply_markup=kb)
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
        jy,jm,jd = g2j(dt.year, dt.month, dt.day)
        return f"{jy:04d}/{jm:02d}/{jd:02d} {dt.strftime('%H:%M')}"
    except Exception:
        return ts

if __name__ == "__main__":
    main()
