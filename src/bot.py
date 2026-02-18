from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from .config import TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS, APP_URL
from .db import init_db, get_or_create_user, update_user_name, get_orders_for_user, set_content, get_content, create_ticket, add_order_for_user

STATE_ASK_NAME = 1
STATE_ASK_QUESTION = 2

MAIN_BUTTONS = [
    ["🚀 شروع همراهی 🚀"],
    ["📌 پیگیری سفارشاتم 📌"],
    ["🔎 چطور به ریشه اعتماد کنم؟ 🔎"],
    ["💬 اگه نمی‌دونی؛ از من بپرس! 💬"],
    ["🌿 ریشه چیه؟ 🌿"],
]

KB = ReplyKeyboardMarkup(MAIN_BUTTONS, resize_keyboard=True, is_persistent=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.full_name)
    await update.message.reply_text("خوش اومدی! از منوی زیر انتخاب کن.", reply_markup=KB)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    if text == "🚀 شروع همراهی 🚀":
        with_name = get_or_create_user(user.id, user.username, user.full_name)
        if not with_name["name"]:
            await update.message.reply_text("اسم قشنگتو بفرست تا با هم شروع کنیم ✨", reply_markup=KB)
            return STATE_ASK_NAME
        await update.message.reply_text("همراهی‌مون شروع شده؛ از دکمه‌ها استفاده کن.", reply_markup=KB)
        return ConversationHandler.END
    if text == "📌 پیگیری سفارشاتم 📌":
        orders = get_orders_for_user(user.id)
        if not orders:
            await update.message.reply_text("هنوز سفارشی ثبت نشده.", reply_markup=KB)
        else:
            lines = [f"#{o['id']} • {o['title']} • {o['status']}" for o in orders]
            await update.message.reply_text("\n".join(lines), reply_markup=KB)
        return ConversationHandler.END
    if text == "🔎 چطور به ریشه اعتماد کنم؟ 🔎":
        value = get_content("trust")
        msg = value if value else "محتوای اعتماد هنوز تنظیم نشده. از ادمین بخواهید /setcontent trust ... را اجرا کند."
        await update.message.reply_text(msg, reply_markup=KB)
        return ConversationHandler.END
    if text == "💬 اگه نمی‌دونی؛ از من بپرس! 💬":
        await update.message.reply_text("سوالت رو بنویس، ثبتش می‌کنم.", reply_markup=KB)
        return STATE_ASK_QUESTION
    if text == "🌿 ریشه چیه؟ 🌿":
        value = get_content("about")
        msg = value if value else "محتوای معرفی هنوز تنظیم نشده. از ادمین بخواهید /setcontent about ... را اجرا کند."
        await update.message.reply_text(msg, reply_markup=KB)
        return ConversationHandler.END
    await update.message.reply_text("از منو انتخاب کن.", reply_markup=KB)
    return ConversationHandler.END

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("منوی اصلی نمایش داده شد.", reply_markup=KB)

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user = update.effective_user
    update_user_name(user.id, name)
    await update.message.reply_text(f"خوشحالم {name}! آماده‌ایم.", reply_markup=KB)
    return ConversationHandler.END

async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    user = update.effective_user
    create_ticket(user.id, q)
    await update.message.reply_text("سوالت ثبت شد. به‌زودی پاسخ می‌دیم.", reply_markup=KB)
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
        await update.message.reply_text("ابتدا /start را بزن.")

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
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("setcontent", setcontent))
    app.add_handler(CommandHandler("addorder", addorder))
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        states={
            STATE_ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            STATE_ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    return app

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است")
    app = build_app()
    app.run_polling()

if __name__ == "__main__":
    main()
