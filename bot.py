"""
SM SHADIN VPN Shop Bot - Auto Balance Version
=============================================
Customer ra ei bot diye package dekhte parbe, balance diye kinte
parbe, ar Deposit kore balance barate parbe.

Main menu (screenshot-er moto):
  Buy VPN, Buy Proxy, Balance, Deposit, Referral, Support

Auto Balance system (SQLite database):
  - /start korlei user-er account toiri hoy, balance surute ৳0
  - Balance button-e chap dile asol balance dekhay
  - Deposit: age taka-r poriman likhun, tarpor TrxID / screenshot
    pathan. Admin-er kache Approve / Reject button soho request jabe.
    Admin Approve chaplei balance-e taka jog hoye jabe, customer-ke
    janiye deoa hobe.
  - Buy VPN: package beche Balance diye kinte parben (balance
    porjapto thakle dam kete jabe, order admin-er kache jabe, admin
    VPN account pathabe). Balance kom thakle age Deposit korte hobe.
  - Admin command: /addbalance <user_id> <taka>  (shudhu admin)
    /exportbalances  (shudhu admin, balance-er backup list)
  /broadcast <message>  (shudhu admin, sob user-ke message pathay)
  /sendvpn <user_id> <details>  (shudhu admin, customer-ke VPN account pathay)

Guruttopurno sotorkota (Render FREE):
  Balance-er data ei bot-er SQLite file-e (balance.db) thake.
  Render-er free service restart / redeploy hole ei file-er data
  muche jete pare. Tai admin majhe majhe /exportbalances diye
  backup niye rakhben. Dirghomeade 100% nirapod rakhte pore
  external database (jemon Supabase / Neon) lagate hobe.

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

import asyncio
import logging
import os
import sqlite3
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
DB_PATH = os.environ.get("DB_PATH", "balance.db")

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
WAITING_DEPOSIT_AMOUNT = "waiting_deposit_amount"
WAITING_DEPOSIT_PROOF = "waiting_deposit_proof"

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛒 Buy VPN"), KeyboardButton("🌐 Buy Proxy")],
        [KeyboardButton("💳 Balance"), KeyboardButton("💰 Deposit")],
        [KeyboardButton("🔗 Referral"), KeyboardButton("🎧 Support")],
    ],
    resize_keyboard=True,
)


def admin_id_int():
    try:
        return int(ADMIN_ID)
    except (TypeError, ValueError):
        return None


def is_admin(user_id):
    admin = admin_id_int()
    return admin is not None and user_id == admin


# ---------------- Database ----------------

def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "user_id INTEGER PRIMARY KEY, "
        "username TEXT, "
        "first_name TEXT, "
        "balance INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS deposits ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER, "
        "username TEXT, "
        "amount INTEGER, "
        "trxid TEXT, "
        "status TEXT DEFAULT 'pending', "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()


def ensure_user(user):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, balance)"
        " VALUES (?, ?, ?, 0)",
        (user.id, user.username or "", user.full_name),
    )
    conn.execute(
        "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
        (user.username or "", user.full_name, user.id),
    )
    conn.commit()
    conn.close()


def get_balance(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def add_balance(user_id, amount):
    """Balance-e amount jog korun (negative hole katbe, 0-er niche jabe na)."""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)",
        (user_id,),
    )
    conn.execute(
        "UPDATE users SET balance = MAX(balance + ?, 0) WHERE user_id = ?",
        (amount, user_id),
    )
    row = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else 0


def create_deposit(user_id, username, amount, trxid):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO deposits (user_id, username, amount, trxid, status)"
        " VALUES (?, ?, ?, ?, 'pending')",
        (user_id, username or "", amount, trxid),
    )
    dep_id = cur.lastrowid
    conn.commit()
    conn.close()
    return dep_id


def get_deposit(dep_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT user_id, amount, status FROM deposits WHERE id = ?",
        (dep_id,),
    ).fetchone()
    conn.close()
    return row


def set_deposit_status(dep_id, status):
    conn = get_conn()
    conn.execute(
        "UPDATE deposits SET status = ? WHERE id = ?", (status, dep_id)
    )
    conn.commit()
    conn.close()


def get_all_user_ids():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [row[0] for row in rows]


# ---------------- Health server (Render free) ----------------

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


def customer_label(user):
    if user.username:
        return f"{user.full_name} (@{user.username})"
    return user.full_name


# ---------------- Menu handlers ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    context.user_data.clear()
    await update.message.reply_text(welcome_text(), reply_markup=MAIN_MENU)


async def packages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    await update.message.reply_text("📦 VPN প্যাকেজসমূহ:", reply_markup=package_keyboard())


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💬 কোনো সমস্যা বা প্রশ্ন থাকলে সরাসরি মেসেজ করুন:\n"
        f"👉 {ORDER_LINK}\n\n"
        f"📢 Community Channel: {CHANNEL_LINK}"
    )


async def menu_buy_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
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
    user = update.message.from_user
    ensure_user(user)
    balance = get_balance(user.id)
    await update.message.reply_text(
        f"💳 আপনার বর্তমান ব্যালেন্স: ৳{balance}\n\n"
        "ব্যালেন্স বাড়াতে নিচের Deposit অপশন ব্যবহার করুন।"
    )


async def menu_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    context.user_data["state"] = WAITING_DEPOSIT_AMOUNT
    context.user_data.pop("package", None)
    context.user_data.pop("deposit_amount", None)
    await update.message.reply_text(
        "💰 Deposit করতে প্রথমে কত টাকা জমা দেবেন, শুধু সংখ্যাটা লিখুন।\n"
        "Minimum deposit ৳20।\n"
        "যেমন: 100\n\n"
        f"টাকা পাঠাবেন এই নম্বরে:\nবিকাশ / নগদ: {PAYMENT_NUMBER}"
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


# ---------------- Package / buy with balance ----------------

async def package_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ensure_user(query.from_user)
    index = int(query.data.split(":")[1])
    name, duration, price = PACKAGES[index]
    balance = get_balance(query.from_user.id)
    context.user_data["package"] = (name, duration, price)
    text = (
        f"✅ আপনি বেছেছেন: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n"
        f"💳 আপনার ব্যালেন্স: ৳{balance}\n\n"
        "কীভাবে কিনতে চান, বেছে নিন:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"💳 Balance দিয়ে কিনুন (৳{price})",
            callback_data=f"paybal:{index}",
        )],
        [InlineKeyboardButton(
            "💵 বিকাশ / নগদ দিয়ে কিনুন",
            callback_data=f"paycash:{index}",
        )],
        [InlineKeyboardButton("⬅️ প্যাকেজ লিস্টে ফিরুন", callback_data="back")],
    ])
    await query.edit_message_text(text, reply_markup=keyboard)


async def pay_with_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    ensure_user(user)
    index = int(query.data.split(":")[1])
    name, duration, price = PACKAGES[index]
    if not ADMIN_ID:
        await query.answer("এখন অর্ডার নেওয়া যাচ্ছে না।", show_alert=True)
        await query.edit_message_text(
            "দুঃখিত, এখন অর্ডার নেওয়া যাচ্ছে না। সরাসরি এখানে মেসেজ করুন:\n"
            f"👉 {ORDER_LINK}"
        )
        return
    balance = get_balance(user.id)
    if balance < price:
        await query.answer(
            f"ব্যালেন্স কম! আপনার ব্যালেন্স ৳{balance}, দরকার ৳{price}। "
            "আগে Deposit করুন।",
            show_alert=True,
        )
        return
    new_balance = add_balance(user.id, -price)
    caption = (
        "🛒 নতুন অর্ডার (Balance দিয়ে পেমেন্ট)!\n"
        f"📦 প্যাকেজ: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n"
        f"👤 কাস্টমার: {customer_label(user)}\n"
        f"🆔 User ID: {user.id}\n"
        f"💳 বাকি ব্যালেন্স: ৳{new_balance}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=caption)
    context.user_data.clear()
    await query.answer("অর্ডার সম্পন্ন!")
    await query.edit_message_text(
        f"✅ অর্ডার সম্পন্ন! {name} - {duration} এর ৳{price} "
        f"আপনার ব্যালেন্স থেকে কাটা হয়েছে।\n"
        f"💳 বাকি ব্যালেন্স: ৳{new_balance}\n\n"
        "অ্যাডমিন যত দ্রুত সম্ভব আপনার VPN অ্যাকাউন্ট পাঠিয়ে দেবে।"
    )


async def pay_with_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


# ---------------- Deposit approve / reject (admin) ----------------

async def approve_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("শুধু অ্যাডমিন Approve করতে পারবে।", show_alert=True)
        return
    dep_id = int(query.data.split(":")[1])
    row = get_deposit(dep_id)
    if not row:
        await query.answer("এই Deposit পাওয়া যায়নি।", show_alert=True)
        return
    user_id, amount, status = row
    if status != "pending":
        await query.answer("এই request আগেই সম্পন্ন করা হয়েছে।", show_alert=True)
        return
    new_balance = add_balance(user_id, amount)
    set_deposit_status(dep_id, "approved")
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ আপনার Deposit Approve হয়েছে! ৳{amount} যোগ হয়েছে।\n"
            f"💳 বর্তমান ব্যালেন্স: ৳{new_balance}",
        )
    except Exception as exc:
        logger.warning("Customer-ke janate parini: %s", exc)
    await query.answer("Approve করা হয়েছে!")
    note = f"\n\n✅ Approved! ব্যালেন্সে ৳{amount} যোগ হয়েছে।"
    try:
        if query.message.photo:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + note
            )
        else:
            await query.edit_message_text(
                (query.message.text or "") + note
            )
    except Exception as exc:
        logger.warning("Admin message edit korte parini: %s", exc)


async def reject_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("শুধু অ্যাডমিন Reject করতে পারবে।", show_alert=True)
        return
    dep_id = int(query.data.split(":")[1])
    row = get_deposit(dep_id)
    if not row:
        await query.answer("এই Deposit পাওয়া যায়নি।", show_alert=True)
        return
    user_id, amount, status = row
    if status != "pending":
        await query.answer("এই request আগেই সম্পন্ন করা হয়েছে।", show_alert=True)
        return
    set_deposit_status(dep_id, "rejected")
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ আপনার ৳{amount} Deposit request Reject হয়েছে।\n"
            "কোনো ভুল হলে Support-এ মেসেজ করুন।",
        )
    except Exception as exc:
        logger.warning("Customer-ke janate parini: %s", exc)
    await query.answer("Reject করা হয়েছে!")
    note = "\n\n❌ Rejected!"
    try:
        if query.message.photo:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + note
            )
        else:
            await query.edit_message_text(
                (query.message.text or "") + note
            )
    except Exception as exc:
        logger.warning("Admin message edit korte parini: %s", exc)


# ---------------- Admin commands ----------------

async def addbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    if len(context.args) != 2:
        await update.message.reply_text(
            "ব্যবহার: /addbalance <user_id> <taka>\nযেমন: /addbalance 123456789 100"
        )
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("User ID আর টাকা, দুটোই সংখ্যায় লিখতে হবে।")
        return
    new_balance = add_balance(target_id, amount)
    await update.message.reply_text(
        f"✅ User {target_id}-এর ব্যালেন্স এখন ৳{new_balance} "
        f"({amount:+d} যোগ করা হয়েছে)।"
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"💳 অ্যাডমিন আপনার ব্যালেন্স আপডেট করেছে।\n"
            f"বর্তমান ব্যালেন্স: ৳{new_balance}",
        )
    except Exception:
        pass


async def exportbalances_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, username, balance FROM users "
        "WHERE balance != 0 ORDER BY balance DESC"
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("কোনো ব্যালেন্স জমা নেই (সবাই ৳0)।")
        return
    lines = ["💳 Balance Backup List:"]
    for user_id, username, balance in rows:
        name = f"@{username}" if username else ""
        lines.append(f"{user_id} {name} : ৳{balance}")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n... (আরও আছে)"
    await update.message.reply_text(text)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    message = " ".join(context.args).strip()
    if not message:
        await update.message.reply_text(
            "ব্যবহার: /broadcast <মেসেজ>\nযেমন: /broadcast নতুন অফার! আজ থেকে সব VPN-এ ছাড়।"
        )
        return
    if len(message) > 4000:
        await update.message.reply_text("মেসেজটা অনেক বড়, ৪০০০ অক্ষরের মধ্যে লিখুন।")
        return
    user_ids = get_all_user_ids()
    if not user_ids:
        await update.message.reply_text("কোনো ইউজার পাওয়া যায়নি। কেউ /start করলে তবেই broadcast যাবে।")
        return
    await update.message.reply_text(f"📢 Broadcast শুরু হচ্ছে, মোট ইউজার: {len(user_ids)} জন...")
    text = f"📢 SM SHADIN Shop:\n\n{message}"
    success = 0
    failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            success += 1
        except Exception as exc:
            logger.warning("Broadcast pathate parini %s: %s", uid, exc)
            failed += 1
        await asyncio.sleep(0.05)
    await update.message.reply_text(f"✅ Broadcast শেষ! পেয়েছে: {success} জন, পায়নি: {failed} জন।")


async def sendvpn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "ব্যবহার: /sendvpn <user_id> <VPN details>\n"
            "যেমন: /sendvpn 123456789 NordVPN username: abc password: xyz server: us1"
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID সংখ্যায় লিখতে হবে। যেমন: /sendvpn 123456789 username: abc")
        return
    details = " ".join(context.args[1:]).strip()
    if not details:
        await update.message.reply_text("VPN details লিখতে হবে। যেমন: /sendvpn 123456789 username: abc password: xyz")
        return
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 আপনার VPN অ্যাকাউন্ট রেডি!\n\n{details}\n\n"
            f"কোনো সমস্যা হলে Support-এ মেসেজ করুন:\n{ORDER_LINK}",
        )
    except Exception as exc:
        logger.warning("VPN pathate parini %s: %s", target_id, exc)
        await update.message.reply_text(
            f"❌ User {target_id}-কে পাঠানো যায়নি। ইউজার বট block করেছে বা User ID ভুল হতে পারে।"
        )
        return
    await update.message.reply_text(f"✅ VPN অ্যাকাউন্ট User {target_id}-কে পাঠানো হয়েছে।")


# ---------------- Text / photo input ----------------

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    package = context.user_data.get("package")
    user = update.message.from_user
    ensure_user(user)

    # Step 1: Deposit-er taka-r poriman
    if state == WAITING_DEPOSIT_AMOUNT:
        if update.message.photo:
            await update.message.reply_text(
                "আগে কত টাকা জমা দেবেন, শুধু সংখ্যাটা লিখুন। যেমন: 100"
            )
            return
        raw = (update.message.text or "").strip().replace("৳", "").replace(",", "")
        try:
            amount = int(raw)
        except ValueError:
            await update.message.reply_text(
                "শুধু সংখ্যাটা লিখুন। যেমন: 100"
            )
            return
        if amount < 20:
            await update.message.reply_text("Minimum deposit ৳20। 20 বা তার বেশি লিখুন। যেমন: 100")
            return
        context.user_data["deposit_amount"] = amount
        context.user_data["state"] = WAITING_DEPOSIT_PROOF
        await update.message.reply_text(
            f"💰 ৳{amount} Deposit-এর জন্য নিচের নম্বরে টাকা পাঠান:\n"
            f"বিকাশ / নগদ: {PAYMENT_NUMBER}\n\n"
            "পেমেন্ট করার পর TrxID লিখে পাঠান, অথবা পেমেন্টের স্ক্রিনশট পাঠান।"
        )
        return

    # Step 2: Deposit-er proman (TrxID / screenshot)
    if state == WAITING_DEPOSIT_PROOF:
        amount = context.user_data.get("deposit_amount", 0)
        if not ADMIN_ID:
            await update.message.reply_text(
                "দুঃখিত, এখন Deposit নেওয়া যাচ্ছে না। সরাসরি এখানে মেসেজ করুন:\n"
                f"👉 {ORDER_LINK}"
            )
            return
        if update.message.photo:
            trxid = (update.message.caption or "").strip()
        else:
            trxid = (update.message.text or "").strip()
        dep_id = create_deposit(user.id, user.username, amount, trxid)
        caption = (
            "💰 নতুন Deposit Request!\n"
            f"👤 কাস্টমার: {customer_label(user)}\n"
            f"🆔 User ID: {user.id}\n"
            f"💵 পরিমাণ: ৳{amount}\n"
            f"📝 TrxID / মেসেজ: {trxid or '-'}"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"dep_approve:{dep_id}"
                ),
                InlineKeyboardButton(
                    "❌ Reject", callback_data=f"dep_reject:{dep_id}"
                ),
            ]
        ])
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            await context.bot.send_photo(
                chat_id=ADMIN_ID, photo=photo_id,
                caption=caption, reply_markup=keyboard,
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID, text=caption, reply_markup=keyboard,
            )
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Deposit request পৌঁছেছে! অ্যাডমিন Approve করলেই "
            "আপনার ব্যালেন্সে টাকা যোগ হয়ে যাবে।"
        )
        return

    # Cash-e VPN kenar proman (ager moto, manual jachai)
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
        f"👤 কাস্টমার: {customer_label(user)}\n"
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
    init_db()
    start_health_server()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("packages", packages_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(CommandHandler("addbalance", addbalance_command))
    app.add_handler(CommandHandler("exportbalances", exportbalances_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("sendvpn", sendvpn_command))
    app.add_handler(MessageHandler(filters.Regex("Buy VPN"), menu_buy_vpn))
    app.add_handler(MessageHandler(filters.Regex("Buy Proxy"), menu_buy_proxy))
    app.add_handler(MessageHandler(filters.Regex("Balance"), menu_balance))
    app.add_handler(MessageHandler(filters.Regex("Deposit"), menu_deposit))
    app.add_handler(MessageHandler(filters.Regex("Referral"), menu_referral))
    app.add_handler(MessageHandler(filters.Regex("Support"), menu_support))
    app.add_handler(CallbackQueryHandler(package_selected, pattern=r"^pkg:\d+$"))
    app.add_handler(CallbackQueryHandler(pay_with_balance, pattern=r"^paybal:\d+$"))
    app.add_handler(CallbackQueryHandler(pay_with_cash, pattern=r"^paycash:\d+$"))
    app.add_handler(CallbackQueryHandler(back_to_list, pattern=r"^back$"))
    app.add_handler(CallbackQueryHandler(approve_deposit, pattern=r"^dep_approve:\d+$"))
    app.add_handler(CallbackQueryHandler(reject_deposit, pattern=r"^dep_reject:\d+$"))
    app.add_handler(
        MessageHandler(
            filters.PHOTO | (filters.TEXT & ~filters.COMMAND),
            handle_payment_proof,
        )
    )
    app.run_polling()


if __name__ == "__main__":
    main()
