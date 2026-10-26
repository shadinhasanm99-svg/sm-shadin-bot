"""
SM SHADIN VPN Shop Bot
======================
Customer ra ei bot diye package dekhte parbe, order korte parbe,
ar payment-er TrxID / screenshot pathate parbe. Order gulo admin-er
kache forward hoye jabe.

Main menu (screenshot-er moto):
  Buy VPN, Buy Proxy, Balance, Deposit, Referral, Support

Ei version ta Render-er FREE Web Service-e cholar jonno toiri:
Render Web Service health check-er jonno $PORT-e ekta choto server
khola lage, tai bot-er sathe ekta health server-o cholbe.

Setup (token kokhono ei file-e likhbe na):
  BOT_TOKEN : @BotFather theke pawa token
  ADMIN_ID  : tomar nijer Telegram numeric ID (@userinfobot theke pawa jay)

Run:
  pip install -r requirements.txt
  BOT_TOKEN=... ADMIN_ID=... python bot.py
"""

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")

BOT_USERNAME = "sm_shadin_shop_bot"
PAYMENT_NUMBER = "01879173170"
ORDER_LINK = "https://t.me/BestservicSM"
CHANNEL_LINK = "https://t.me/socialmarketing22"

# (VPN name, duration, price in BDT)
PACKAGES = [
    ("Nord VPN", "7 din", 25),
    ("Express VPN", "3 din", 20),
    ("CyberGhost VPN", "3 din", 20),
    ("PIA VPN", "3 din", 20),
    ("Surfshark VPN", "7 din", 25),
    ("IPVanish VPN", "7 din", 25),
    ("HMA VPN", "7 din", 25),
    ("Proton VPN", "14 din", 50),
    ("Nord VPN", "30 din", 110),
    ("HMA VPN", "30 din", 50),
]

WAITING_PAYMENT = "waiting_payment"
WAITING_DEPOSIT = "waiting_deposit"

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛒 Buy VPN"), KeyboardButton("🌐 Buy Proxy")],
        [KeyboardButton("💳 Balance"), KeyboardButton("💰 Deposit")],
        [KeyboardButton("🔗 Referral"), KeyboardButton("🎧 Support")],
    ],
    resize_keyboard=True,
)


def start_health_server():
    """Render free Web Service-er health check-er jonno $PORT-e server kholo."""
    port = int(os.environ.get("PORT", "10000"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"SM SHADIN bot is running")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server cholche, port: %s", port)


def package_keyboard():
    buttons = []
    for i, (name, duration, price) in enumerate(PACKAGES):
        buttons.append([
            InlineKeyboardButton(
                f"{name} - {duration} - ৳{price}", callback_data=f"pkg:{i}"
            )
        ])
    buttons.append([InlineKeyboardButton("📢 Community Channel", url=CHANNEL_LINK)])
    buttons.append([InlineKeyboardButton("💬 Support", url=ORDER_LINK)])
    return InlineKeyboardMarkup(buttons)


def welcome_text():
    return (
        "👋 স্বাগতম! SM SHADIN VPN Shop-এ।\n\n"
        "নিচের মেনু থেকে অপশন বেছে নিন।"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(welcome_text(), reply_markup=MAIN_MENU)


async def packages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 VPN প্যাকেজসমূহ:", reply_markup=package_keyboard())


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💬 কোনো সমস্যা বা প্রশ্ন থাকলে সরাসরি মেসেজ করুন:\n"
        f"👉 {ORDER_LINK}\n\n"
        f"📢 Community Channel: {CHANNEL_LINK}"
    )


async def menu_buy_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 VPN প্যাকেজসমূহ:", reply_markup=package_keyboard()
    )


async def menu_buy_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Proxy প্যাকেজ এখনো এই বটে যোগ করা হয়নি।\n\n"
        "Proxy কিনতে চাইলে সরাসরি Support-এ মেসেজ করুন:\n"
        f"👉 {ORDER_LINK}"
    )


async def menu_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 আপনার ব্যালেন্সের হিসাব অ্যাডমিনের কাছে থাকে।\n\n"
        "ব্যালেন্স জানতে Support-এ মেসেজ করুন, অ্যাডমিন জানিয়ে দেবে:\n"
        f"👉 {ORDER_LINK}\n\n"
        "ব্যালেন্স বাড়াতে নিচের Deposit অপশন ব্যবহার করুন।"
    )


async def menu_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = WAITING_DEPOSIT
    context.user_data.pop("package", None)
    await update.message.reply_text(
        "💰 Deposit করতে নিচের নম্বরে টাকা পাঠান:\n"
        f"বিকাশ / নগদ: {PAYMENT_NUMBER}\n\n"
        "পেমেন্ট করার পর TrxID লিখে পাঠান, অথবা পেমেন্টের স্ক্রিনশট পাঠান।\n"
        "অ্যাডমিন যাচাই করে আপনার ব্যালেন্সে টাকা যোগ করে দেবে।"
    )


async def menu_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    link = f"https://t.me/{BOT_USERNAME}?start={user.id}"
    await update.message.reply_text(
        "🔗 আপনার Referral লিংক:\n"
        f"{link}\n\n"
        "এই লিংক দিয়ে বন্ধুদের বটে আনুন। "
        "Referral বোনাসের ব্যাপারে Support-এ মেসেজ করে জেনে নিন:\n"
        f"👉 {ORDER_LINK}"
    )


async def menu_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎧 Support:\n"
        f"👉 {ORDER_LINK}\n\n"
        f"📢 Community Channel: {CHANNEL_LINK}"
    )


async def package_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split(":")[1])
    name, duration, price = PACKAGES[index]
    context.user_data["package"] = (name, duration, price)
    context.user_data["state"] = WAITING_PAYMENT
    text = (
        f"✅ আপনি বেছেছেন: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n\n"
        f"💳 পেমেন্ট করুন:\n"
        f"বিকাশ / নগদ: {PAYMENT_NUMBER}\n\n"
        "পেমেন্ট করার পর TrxID লিখে পাঠান, অথবা পেমেন্টের স্ক্রিনশট পাঠান।\n"
        "আমরা যাচাই করে আপনার অ্যাকাউন্ট পাঠিয়ে দেবো।"
    )
    back = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ প্যাকেজ লিস্টে ফিরুন", callback_data="back")],
    ])
    await query.edit_message_text(text, reply_markup=back)


async def back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "📦 VPN প্যাকেজসমূহ:", reply_markup=package_keyboard()
    )


async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    package = context.user_data.get("package")
    user = update.message.from_user
    customer = f"{user.full_name} (@{user.username})" if user.username else user.full_name

    if state == WAITING_DEPOSIT:
        caption = (
            "💰 নতুন Deposit Request!\n"
            f"👤 কাস্টমার: {customer}\n"
            f"🆔 User ID: {user.id}"
        )
        if not ADMIN_ID:
            await update.message.reply_text(
                "দুঃখিত, এখন Deposit নেওয়া যাচ্ছে না। সরাসরি এখানে মেসেজ করুন:\n"
                f"👉 {ORDER_LINK}"
            )
            return
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            text = update.message.caption or ""
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo_id,
                caption=caption + (f"\n📝 মেসেজ: {text}" if text else ""),
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=caption + f"\n📝 TrxID / মেসেজ: {update.message.text}",
            )
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Deposit request পৌঁছেছে! অ্যাডমিন যাচাই করে "
            "আপনার ব্যালেন্সে টাকা যোগ করে দেবে।"
        )
        return

    if state != WAITING_PAYMENT or not package:
        await update.message.reply_text(
            "নিচের মেনু থেকে Buy VPN চাপ দিয়ে একটি প্যাকেজ বেছে নিন, "
            "তারপর TrxID বা স্ক্রিনশট পাঠান।"
        )
        return

    name, duration, price = package
    caption = (
        "🛒 নতুন অর্ডার!\n"
        f"📦 প্যাকেজ: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n"
        f"👤 কাস্টমার: {customer}\n"
        f"🆔 User ID: {user.id}"
    )
    if not ADMIN_ID:
        logger.warning("ADMIN_ID set kora nei, tai order forward kora jayni.")
        await update.message.reply_text(
            "দুঃখিত, এখন অর্ডার নেওয়া যাচ্ছে না। সরাসরি এখানে মেসেজ করুন:\n"
            f"👉 {ORDER_LINK}"
        )
        return
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        text = update.message.caption or ""
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=caption + (f"\n📝 মেসেজ: {text}" if text else ""),
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=caption + f"\n📝 TrxID / মেসেজ: {update.message.text}",
        )
    context.user_data.clear()
    await update.message.reply_text(
        "✅ অর্ডার পৌঁছেছে! আমরা পেমেন্ট যাচাই করে যত দ্রুত সম্ভব "
        "আপনার VPN অ্যাকাউন্ট পাঠিয়ে দেবো।"
    )


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable set kora nei!")
    start_health_server()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("packages", packages_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(MessageHandler(filters.Regex("Buy VPN"), menu_buy_vpn))
    app.add_handler(MessageHandler(filters.Regex("Buy Proxy"), menu_buy_proxy))
    app.add_handler(MessageHandler(filters.Regex("Balance"), menu_balance))
    app.add_handler(MessageHandler(filters.Regex("Deposit"), menu_deposit))
    app.add_handler(MessageHandler(filters.Regex("Referral"), menu_referral))
    app.add_handler(MessageHandler(filters.Regex("Support"), menu_support))
    app.add_handler(CallbackQueryHandler(package_selected, pattern=r"^pkg:\d+$"))
    app.add_handler(CallbackQueryHandler(back_to_list, pattern=r"^back$"))
    app.add_handler(
        MessageHandler(
            filters.PHOTO | (filters.TEXT & ~filters.COMMAND),
            handle_payment_proof,
        )
    )
    app.run_polling()


if __name__ == "__main__":
    main()
