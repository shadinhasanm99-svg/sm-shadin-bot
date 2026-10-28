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
    pathan. SMS AutoPay chalu thakle: TrxID + amount jodi apnar
    phone-e asa bKash/Nagad SMS-er sathe exactly mile, tahole
    balance AUTO jog hobe, admin Approve lagbe na. Na mille
    ager moto admin-er kache Approve / Reject request jabe
    (backup, jate customer-er taka na atke).
    SMS ashe apnar phone-er SMS forwarder app theke, bot-er
    POST /sms endpoint-e, secret diye. PIN kokhono bot-ke
    dite hobe na, PIN charai ei system chole.
    Ek TrxID diye dubar balance deoa jabe na (used check ache).
  - Buy VPN: package beche Balance diye kinte parben (balance
    porjapto thakle dam kete jabe, order admin-er kache jabe, admin
    VPN account pathabe). Balance kom thakle age Deposit korte hobe.
  - Buy Proxy: 9Proxy / RapidProxy / 711Proxy / H143Proxy
    package beche VPN-er motoi Balance ba bKash/Nagad diye kena jay.
    Order admin-er kache jabe, admin Proxy details pathabe
    (/sendproxy diye).
  - Admin command: /addbalance <user_id> <taka>  (shudhu admin)
    /exportbalances  (shudhu admin, balance-er backup list)
  /broadcast <message>  (shudhu admin, sob user-ke message pathay)
  /sendvpn <user_id> <details>  (shudhu admin, customer-ke VPN account pathay)
  /sendproxy <user_id> <details>  (shudhu admin, customer-ke Proxy details pathay)
  /users  (shudhu admin, mot bot user sonkha dekhay)
  /away on | /away off  (shudhu admin, away mode chalu/bondho)

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
import json
import logging
import os
import re
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
# SMS AutoPay secret: Render env-e set korte hobe, code-e kokhono likhbe na.
# SMS forwarder app ei secret pathabe, na mille /sms request reject hobe.
# Secret na thakle /sms bondho thakbe, auto-match cholbe na.
SMS_SECRET = os.environ.get("SMS_SECRET", "")
DB_PATH = os.environ.get("DB_PATH", "balance.db")

BOT_USERNAME = "sm_shadin_shop_bot"
PAYMENT_NUMBER = "01879173170"
ORDER_LINK = "https://t.me/BestservicSM"
CHANNEL_LINK = "https://t.me/socialmarketing22"
# Force-join channel (2026-10-28, user-er deoa channel):
# Bot-e dhukar age ei channel-e join korte hobe, tarpor Verify Access.
# BOT KE EI CHANNEL-E ADMIN BANATE HOBE, na hole Telegram bot-ke
# getChatMember diye join check korte dibe na, ar sob user atke jabe.
FORCE_JOIN_CHANNEL = "@smshadinproxy"
FORCE_JOIN_LINK = "https://t.me/smshadinproxy"

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

# Proxy package: (name, duration, price in BDT)
# Screenshot-er dam-er upor protitite ৳10 jog kora hoyeche.
# Jemon: 9Proxy 10 IP 49 -> 59, 9Proxy 100 MB 15 -> 25, ityadi.
# Stock sonkha bot-e dekhano hoyni, karon bot stock auto komay na.
PROXIES = [
    ("10 IP (999999Proxy)", "TK", 59),
    ("100 MB (9Proxy)", "TK", 25),
    ("200 MB (9Proxy)", "TK", 35),
    ("100 MB (RapidProxy)", "TK", 25),
    ("200 MB (RapidProxy)", "TK", 35),
    ("100 MB (711Proxy)", "TK", 25),
    ("200 MB (711Proxy)", "TK", 35),
    ("100 MB (H143Proxy)", "TK", 19),
    ("200 MB (H143Proxy)", "TK", 23),
    ("200 MB (H143Proxy)", "TK", 23666),
]
]

WAITING_PAYMENT = "waiting_payment"
WAITING_PROXY_PAYMENT = "waiting_proxy_payment"
WAITING_DEPOSIT_AMOUNT = "waiting_deposit_amount"
WAITING_DEPOSIT_PROOF = "waiting_deposit_proof"
WAITING_SUPPORT = "waiting_support"

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛒 Buy VPN"), KeyboardButton("🌐 Buy Proxy")],
        [KeyboardButton("💳 Balance"), KeyboardButton("💰 Deposit")],
        [KeyboardButton("🔗 Referral"), KeyboardButton("🎧 Support")],
        [KeyboardButton("📦 আমার অর্ডার")],
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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS settings ("
        "key TEXT PRIMARY KEY, "
        "value TEXT)"
    )
    # SMS AutoPay: forwarder app theke asa bKash/Nagad SMS-er record.
    # trxid PRIMARY KEY + used flag diye ek TrxID dubar credit atkay.
    # Sender phone number ekhane save kora hoy na, shudhu TrxID + amount.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sms_payments ("
        "trxid TEXT PRIMARY KEY, "
        "amount INTEGER, "
        "used INTEGER NOT NULL DEFAULT 0, "
        "received_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    # Referral + orders: purono DB-teo column/table na thakle jog hobe.
    _cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    for _col, _ddl in (
        ("referred_by", "INTEGER"),
        ("ref_orders_total", "INTEGER NOT NULL DEFAULT 0"),
        ("ref_bonus_paid", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if _col not in _cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {_col} {_ddl}")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS orders ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER, "
        "kind TEXT, "
        "name TEXT, "
        "duration TEXT, "
        "price INTEGER, "
        "pay_method TEXT, "
        "status TEXT DEFAULT 'done', "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()


def parse_sms_payment(text, trxid_hint="", amount_hint=0):
    """bKash/Nagad SMS text theke TrxID + amount ber korun.

    Returns (trxid, amount) ba (None, 0) jodi na paoa jay.
    PIN ba password kokhono ekhane asbe na, shudhu SMS-er TrxID/amount.
    """
    if not text:
        return (trxid_hint.upper() if trxid_hint else None, int(amount_hint or 0))
    upper = text.upper()
    trxid = None
    m = re.search(r"TRX\s*ID\s*[:\-]?\s*([A-Z0-9]{8,12})", upper)
    if m:
        trxid = m.group(1)
    elif trxid_hint:
        trxid = trxid_hint.upper()
    amount = 0
    m2 = re.search(r"TK\.?\s*([\d,]+(?:\.\d+)?)", upper)
    if m2:
        try:
            amount = int(round(float(m2.group(1).replace(",", ""))))
        except ValueError:
            amount = 0
    if not amount and amount_hint:
        amount = int(amount_hint)
    return (trxid, amount)


def save_sms_payment(trxid, amount):
    if not trxid or not amount:
        return False
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO sms_payments (trxid, amount, used)"
        " VALUES (?, ?, 0)",
        (trxid.upper(), int(amount)),
    )
    conn.commit()
    conn.close()
    return True


def find_unused_sms(trxid, amount):
    """TrxID + amount exactly mile, ekhono bebohar hoyni, amon SMS khujun."""
    conn = get_conn()
    row = conn.execute(
        "SELECT trxid, amount FROM sms_payments "
        "WHERE trxid = ? AND amount = ? AND used = 0",
        (trxid.upper(), int(amount)),
    ).fetchone()
    conn.close()
    return row is not None


def mark_sms_used(trxid):
    conn = get_conn()
    conn.execute(
        "UPDATE sms_payments SET used = 1 WHERE trxid = ?", (trxid.upper(),)
    )
    conn.commit()
    conn.close()


def is_trxid_already_credited(trxid):
    """Ei TrxID diye age balance deoa hoyeche kina (auto ba manual)."""
    if not trxid:
        return False
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM deposits WHERE UPPER(trxid) = ? "
        "AND status IN ('approved', 'auto_approved')",
        (trxid.upper(),),
    ).fetchone()
    conn.close()
    return row is not None


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


def set_referrer(user_id, referrer_id):
    """Notun user referral link diye asle, sudhu prothombar referrer set korun."""
    try:
        referrer_id = int(referrer_id)
    except (TypeError, ValueError):
        return
    if referrer_id == user_id:
        return
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)",
        (referrer_id,),
    )
    conn.execute(
        "UPDATE users SET referred_by = ? WHERE user_id = ? AND referred_by IS NULL",
        (referrer_id, user_id),
    )
    conn.commit()
    conn.close()


def get_referral_stats(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)
    ).fetchone()
    referred_count = row[0] if row else 0
    row = conn.execute(
        "SELECT ref_orders_total, ref_bonus_paid FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    total_orders = row[0] if row else 0
    bonus_paid = row[1] if row else 0
    return referred_count, total_orders, bonus_paid


def record_referral_order(buyer_id):
    """Balance order hole referrer-er count baran. 10 order porpor ৳5 bonus due hole True."""
    conn = get_conn()
    row = conn.execute(
        "SELECT referred_by FROM users WHERE user_id = ?", (buyer_id,)
    ).fetchone()
    if not row or not row[0]:
        conn.close()
        return None
    referrer_id = row[0]
    conn.execute(
        "UPDATE users SET ref_orders_total = ref_orders_total + 1 WHERE user_id = ?",
        (referrer_id,),
    )
    row = conn.execute(
        "SELECT ref_orders_total FROM users WHERE user_id = ?", (referrer_id,)
    ).fetchone()
    total = row[0] if row else 0
    bonus_due = (total > 0 and total % 10 == 0)
    if bonus_due:
        conn.execute(
            "UPDATE users SET ref_bonus_paid = ref_bonus_paid + 1 WHERE user_id = ?",
            (referrer_id,),
        )
    conn.commit()
    conn.close()
    return (referrer_id, total, bonus_due)


def record_order(user_id, kind, name, duration, price, pay_method, status="done"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO orders (user_id, kind, name, duration, price, pay_method, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, kind, name, duration, price, pay_method, status),
    )
    conn.commit()
    conn.close()


def get_user_orders(user_id, limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT kind, name, duration, price, pay_method, status, created_at"
        " FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_user_deposits(user_id, limit=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT amount, trxid, status, created_at FROM deposits"
        " WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


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


def get_user_count():
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    conn.close()
    return row[0] if row else 0


def get_setting(key, default=""):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


# ---------------- Health server (Render free) ----------------

def start_health_server():
    """Render free Web Service-er health check-er jonno $PORT-e server kholo.

    GET /  -> health text (keepalive ping er jonno)
    POST /sms -> SMS forwarder app theke SMS record ney.
      Secret chara /sms kokhono accept korbe na, nahole je keu
      vua TrxID pathiye free balance nite parto.
      Body JSON: {"text": "<bKash/Nagad SMS>", "secret": "..."}
      ba header X-Secret, ba ?secret=... . Secret Render env SMS_SECRET.
      Shudhu TrxID + amount save hoy, sender number save hoy na.
    """
    port = int(os.environ.get("PORT", "10000"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"SM SHADIN bot is running")

        def do_POST(self):
            try:
                if not self.path.startswith("/sms"):
                    self.send_response(404)
                    self.end_headers()
                    return
                if not SMS_SECRET:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"SMS_SECRET not set")
                    return
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length) if length > 0 else b""
                try:
                    data = json.loads(raw.decode("utf-8", "ignore")) if raw else {}
                except ValueError:
                    data = {}
                if not isinstance(data, dict):
                    data = {}
                secret = (
                    data.get("secret", "")
                    or self.headers.get("X-Secret", "")
                    or ""
                )
                # ?secret=... query-o allow, forwarder app-e subidhar jonno
                if "secret=" in self.path:
                    import urllib.parse as _up
                    q = _up.urlparse(self.path).query
                    secret = secret or _up.parse_qs(q).get("secret", [""])[0]
                if secret != SMS_SECRET:
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b"unauthorized")
                    return
                text = data.get("text", "") or data.get("message", "") or data.get("sms", "")
                trxid, amount = parse_sms_payment(
                    text,
                    data.get("trxid", ""),
                    data.get("amount", 0),
                )
                if not trxid or not amount:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"trxid or amount not found")
                    return
                save_sms_payment(trxid, amount)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "trxid": trxid, "amount": amount}).encode())
            except Exception as exc:
                logger.warning("SMS endpoint error: %s", exc)
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception:
                    pass

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


def proxy_keyboard():
    buttons = []
    for i, (name, duration, price) in enumerate(PROXIES):
        buttons.append([
            InlineKeyboardButton(
                f"{name} - {duration} - ৳{price}", callback_data=f"proxy:{i}"
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


# ---------------- Force join (channel join + Verify Access) ----------------

async def is_channel_member(bot, user_id):
    """True = joined, False = not joined, None = check kora jayni (bot admin na / channel vul)."""
    try:
        member = await bot.get_chat_member(chat_id=FORCE_JOIN_CHANNEL, user_id=user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception as e:
        logger.warning(f"Force-join check failed for {user_id}: {e}")
        return None


def force_join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Now", url=FORCE_JOIN_LINK)],
        [InlineKeyboardButton("Verify Access", callback_data="verify_join")],
    ])


def force_join_text():
    # Screenshot-er lekha hubuhu, shobdo bodlano hoyni.
    # VIP badge-ta Telegram-er custom icon, text hisebe copy kora jay na,
    # tai header-e shudhu lekha-tai rakha hoyeche. Channel-er link
    # Join Now button-e ache, message-er modhye alada link deoa hoyni,
    # screenshot-eo message-er modhye link chilo na.
    return (
        "<b>ACCESS RESTRICTED</b>\n"
        "—————————————————\n\n"
        "👥 প্রিয় ইউজার, আমাদের বটের সম্পূর্ণ সার্ভিস এবং সিকিউর ট্রানজেকশন "
        "উপভোগ করতে আমাদের অফিসিয়াল কমিউনিটিতে যুক্ত হওয়া বাধ্যতামূলক।\n\n"
        "<b>📢 নিচের চ্যানেলগুলোতে জয়েন করে আপনার এক্সেস আনলক করুন:</b>\n\n"
        "—————————————————\n\n"
        "📌 জয়েন করা সম্পন্ন হলে নিচের '<b><u>Verify Access</u></b>' বাটনে ক্লিক করুন।"
    )


async def check_force_join(message, bot, user_id):
    """Menu/message handler-er jonno: allowed hole True, gate dekhale False."""
    if is_admin(user_id):
        return True
    member = await is_channel_member(bot, user_id)
    if member is True:
        return True
    if member is None:
        await message.reply_text(
            "⚠️ ভেরিফাই চেক করা যাচ্ছে না। বটকে চ্যানেলে অ্যাডমিন করা আছে কিনা দেখুন।\n"
            f"চ্যানেল: {FORCE_JOIN_LINK}\n"
            f"সরাসরি যোগাযোগ: {ORDER_LINK}"
        )
        return False
    await message.reply_text(force_join_text(), reply_markup=force_join_keyboard(), parse_mode="HTML")
    return False


async def verify_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if is_admin(user_id):
        await query.message.reply_text(welcome_text(), reply_markup=MAIN_MENU)
        return
    member = await is_channel_member(context.bot, user_id)
    if member is True:
        await query.message.reply_text(
            "✅ ভেরিফাই সফল! আপনি চ্যানেলে জয়েন করেছেন।\n\n" + welcome_text(),
            reply_markup=MAIN_MENU,
        )
    elif member is None:
        await query.message.reply_text(
            "⚠️ ভেরিফাই চেক করা যাচ্ছে না। বটকে চ্যানেলে অ্যাডমিন করা আছে কিনা দেখুন।\n"
            f"চ্যানেল: {FORCE_JOIN_LINK}\n"
            f"সরাসরি যোগাযোগ: {ORDER_LINK}"
        )
    else:
        await query.answer(
            "❌ আপনি এখনো জয়েন করেননি। প্রথমে Join Now দিয়ে চ্যানেলে জয়েন করুন, তারপর Verify Access চাপুন।",
            show_alert=True,
        )
        await query.message.reply_text(
            "❌ আপনি এখনো জয়েন করেননি।\n"
            "প্রথমে Join Now দিয়ে চ্যানেলে জয়েন করুন, তারপর Verify Access চাপুন।",
            reply_markup=force_join_keyboard(),
        )


# ---------------- Menu handlers ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    if context.args and context.args[0].isdigit():
        set_referrer(update.message.from_user.id, context.args[0])
    context.user_data.clear()
    if not await check_force_join(update.message, context.bot, update.message.from_user.id):
        return
    await update.message.reply_text(welcome_text(), reply_markup=MAIN_MENU)


async def packages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    if not await check_force_join(update.message, context.bot, update.message.from_user.id):
        return
    await update.message.reply_text("📦 VPN প্যাকেজসমূহ:", reply_markup=package_keyboard())


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    if not await check_force_join(update.message, context.bot, update.message.from_user.id):
        return
    context.user_data["state"] = WAITING_SUPPORT
    await update.message.reply_text(
        "🎧 Support: আপনার সমস্যা বা প্রশ্ন এখানে লিখে পাঠান, অ্যাডমিন বট থেকেই উত্তর দেবে।\n\n"
        "সরাসরি মেসেজ করতে চাইলে:\n"
        f"👉 {ORDER_LINK}\n\n"
        f"📢 Community Channel: {CHANNEL_LINK}"
    )


async def menu_buy_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    if not await check_force_join(update.message, context.bot, update.message.from_user.id):
        return
    await update.message.reply_text(
        "📦 VPN প্যাকেজসমূহ:", reply_markup=package_keyboard()
    )


async def menu_buy_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    if not await check_force_join(update.message, context.bot, update.message.from_user.id):
        return
    await update.message.reply_text(
        "🌐 Proxy প্যাকেজসমূহ:", reply_markup=proxy_keyboard()
    )


async def menu_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    ensure_user(user)
    if not await check_force_join(update.message, context.bot, user.id):
        return
    balance = get_balance(user.id)
    await update.message.reply_text(
        f"💳 আপনার বর্তমান ব্যালেন্স: ৳{balance}\n\n"
        "ব্যালেন্স বাড়াতে নিচের Deposit অপশন ব্যবহার করুন।"
    )


async def menu_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    if not await check_force_join(update.message, context.bot, update.message.from_user.id):
        return
    context.user_data["state"] = WAITING_DEPOSIT_AMOUNT
    context.user_data.pop("package", None)
    context.user_data.pop("proxy", None)
    context.user_data.pop("deposit_amount", None)
    await update.message.reply_text(
        "💰 Deposit করতে প্রথমে কত টাকা জমা দেবেন, শুধু সংখ্যাটা লিখুন।\n"
        "Minimum deposit ৳20।\n\n"
        f"টাকা পাঠাবেন এই নম্বরে:\nবিকাশ / নগদ: {PAYMENT_NUMBER}"
    )


async def menu_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    ensure_user(user)
    if not await check_force_join(update.message, context.bot, user.id):
        return
    link = f"https://t.me/{BOT_USERNAME}?start={user.id}"
    referred_count, total_orders, bonus_paid = get_referral_stats(user.id)
    progress = total_orders % 10
    remaining = 10 - progress if progress else 10
    if total_orders == 0:
        remaining = 10
    await update.message.reply_text(
        "🔗 আপনার Referral লিংক:\n"
        f"{link}\n\n"
        f"👥 আপনি রেফার করেছেন: {referred_count} জন\n"
        f"🛒 তাদের মোট অর্ডার: {total_orders} টা\n"
        f"🎁 বোনাস পেয়েছেন: ৳{bonus_paid * 5}\n"
        f"⏳ পরের ৳5 বোনাসের জন্য আরো {remaining} টা অর্ডার লাগবে\n\n"
        "নিয়ম: আপনার লিংক দিয়ে আসা বন্ধুরা মোট 10 টা Balance অর্ডার করলেই "
        "আপনি ৳5 বোনাস পাবেন, প্রতি 10 অর্ডারে আবার ৳5।"
    )


async def menu_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    ensure_user(user)
    if not await check_force_join(update.message, context.bot, user.id):
        return
    orders = get_user_orders(user.id, 10)
    deposits = get_user_deposits(user.id, 5)
    if not orders and not deposits:
        await update.message.reply_text(
            "📦 আপনার এখনো কোনো অর্ডার বা Deposit নেই।\n"
            "Buy VPN বা Buy Proxy থেকে প্রথম অর্ডার করুন।"
        )
        return
    lines = ["📦 আপনার শেষ অর্ডার:"]
    for kind, name, duration, price, pay_method, status, created_at in orders:
        lines.append(f"• {kind}: {name} - {duration} - ৳{price} ({status})")
    if deposits:
        lines.append("\n💰 শেষ Deposit:")
        for amount, trxid, status, created_at in deposits:
            lines.append(f"• ৳{amount} - {status}")
    lines.append(f"\n💳 বর্তমান ব্যালেন্স: ৳{get_balance(user.id)}")
    await update.message.reply_text("\n".join(lines))


async def menu_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user)
    if not await check_force_join(update.message, context.bot, update.message.from_user.id):
        return
    context.user_data["state"] = WAITING_SUPPORT
    await update.message.reply_text(
        "🎧 Support: আপনার সমস্যা বা প্রশ্ন এখানে লিখে পাঠান, অ্যাডমিন বট থেকেই উত্তর দেবে।\n\n"
        "সরাসরি মেসেজ করতে চাইলে:\n"
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
    record_order(user.id, "VPN", name, duration, price, "balance", "done")
    _ref = record_referral_order(user.id)
    caption = (
        "🛒 নতুন অর্ডার (Balance দিয়ে পেমেন্ট)!\n"
        f"📦 প্যাকেজ: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n"
        f"👤 কাস্টমার: {customer_label(user)}\n"
        f"🆔 User ID: {user.id}\n"
        f"💳 বাকি ব্যালেন্স: ৳{new_balance}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=caption)
    if _ref and _ref[2]:
        _ref_id, _ref_total, _ = _ref
        add_balance(_ref_id, 5)
        try:
            await context.bot.send_message(
                chat_id=_ref_id,
                text="🎁 Referral বোনাস! আপনার রেফার করা বন্ধুদের মোট অর্ডার "
                f"{_ref_total} টা হয়েছে, তাই আপনার ব্যালেন্সে ৳5 যোগ হয়েছে।",
            )
        except Exception as exc:
            logger.warning("Referral bonus janate parini: %s", exc)
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


# ---------------- Proxy / buy with balance ----------------

async def proxy_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ensure_user(query.from_user)
    index = int(query.data.split(":")[1])
    name, duration, price = PROXIES[index]
    balance = get_balance(query.from_user.id)
    context.user_data["proxy"] = (name, duration, price)
    text = (
        f"✅ আপনি বেছেছেন: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n"
        f"💳 আপনার ব্যালেন্স: ৳{balance}\n\n"
        "কীভাবে কিনতে চান, বেছে নিন:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"💳 Balance দিয়ে কিনুন (৳{price})",
            callback_data=f"proxpaybal:{index}",
        )],
        [InlineKeyboardButton(
            "💵 বিকাশ / নগদ দিয়ে কিনুন",
            callback_data=f"proxpaycash:{index}",
        )],
        [InlineKeyboardButton("⬅️ Proxy লিস্টে ফিরুন", callback_data="proxyback")],
    ])
    await query.edit_message_text(text, reply_markup=keyboard)


async def pay_proxy_with_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    ensure_user(user)
    index = int(query.data.split(":")[1])
    name, duration, price = PROXIES[index]
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
    record_order(user.id, "Proxy", name, duration, price, "balance", "done")
    _ref = record_referral_order(user.id)
    caption = (
        "🛒 নতুন Proxy অর্ডার (Balance দিয়ে পেমেন্ট)!\n"
        f"🌐 প্যাকেজ: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n"
        f"👤 কাস্টমার: {customer_label(user)}\n"
        f"🆔 User ID: {user.id}\n"
        f"💳 বাকি ব্যালেন্স: ৳{new_balance}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=caption)
    if _ref and _ref[2]:
        _ref_id, _ref_total, _ = _ref
        add_balance(_ref_id, 5)
        try:
            await context.bot.send_message(
                chat_id=_ref_id,
                text="🎁 Referral বোনাস! আপনার রেফার করা বন্ধুদের মোট অর্ডার "
                f"{_ref_total} টা হয়েছে, তাই আপনার ব্যালেন্সে ৳5 যোগ হয়েছে।",
            )
        except Exception as exc:
            logger.warning("Referral bonus janate parini: %s", exc)
    context.user_data.clear()
    await query.answer("অর্ডার সম্পন্ন!")
    await query.edit_message_text(
        f"✅ অর্ডার সম্পন্ন! {name} - {duration} এর ৳{price} "
        f"আপনার ব্যালেন্স থেকে কাটা হয়েছে।\n"
        f"💳 বাকি ব্যালেন্স: ৳{new_balance}\n\n"
        "অ্যাডমিন যত দ্রুত সম্ভব আপনার Proxy details পাঠিয়ে দেবে।"
    )


async def pay_proxy_with_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split(":")[1])
    name, duration, price = PROXIES[index]
    context.user_data["proxy"] = (name, duration, price)
    context.user_data["state"] = WAITING_PROXY_PAYMENT
    text = (
        f"✅ আপনি বেছেছেন: {name} - {duration}\n"
        f"💰 দাম: ৳{price}\n\n"
        f"💳 পেমেন্ট করুন:\n"
        f"বিকাশ / নগদ: {PAYMENT_NUMBER}\n\n"
        "পেমেন্ট করার পর TrxID লিখে পাঠান, অথবা পেমেন্টের স্ক্রিনশট পাঠান।\n"
        "আমরা যাচাই করে আপনার Proxy details পাঠিয়ে দেবো।"
    )
    back = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Proxy লিস্টে ফিরুন", callback_data="proxyback")],
    ])
    await query.edit_message_text(text, reply_markup=back)


async def back_to_proxy_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "🌐 Proxy প্যাকেজসমূহ:", reply_markup=proxy_keyboard()
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


async def sendproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "ব্যবহার: /sendproxy <user_id> <Proxy details>\n"
            "যেমন: /sendproxy 123456789 host: x.x.x.x port: 8080 username: abc password: xyz"
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("User ID সংখ্যায় লিখতে হবে। যেমন: /sendproxy 123456789 host: x.x.x.x")
        return
    details = " ".join(context.args[1:]).strip()
    if not details:
        await update.message.reply_text("Proxy details লিখতে হবে।")
        return
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 আপনার Proxy রেডি!\n\n{details}\n\n"
            f"কোনো সমস্যা হলে Support-এ মেসেজ করুন:\n{ORDER_LINK}",
        )
    except Exception as exc:
        logger.warning("Proxy pathate parini %s: %s", target_id, exc)
        await update.message.reply_text(
            f"❌ User {target_id}-কে পাঠানো যায়নি। ইউজার বট block করেছে বা User ID ভুল হতে পারে।"
        )
        return
    await update.message.reply_text(f"✅ Proxy details User {target_id}-কে পাঠানো হয়েছে।")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    count = get_user_count()
    await update.message.reply_text(f"👥 মোট বট ইউজার: {count} জন\n(এরা সবাই বটে /start করেছে।)")


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /reply <user_id> <message> — Support-এ আসা কাস্টমারকে বট থেকে উত্তর।"""
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text(
            "ব্যবহার: /reply <user_id> <মেসেজ>\nযেমন: /reply 123456789 আপনার VPN রেডি!"
        )
        return
    target_id = int(context.args[0])
    text = " ".join(context.args[1:])
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎧 Support থেকে উত্তর:\n{text}",
        )
        await update.message.reply_text(f"✅ {target_id}-কে উত্তর পাঠানো হয়েছে।")
    except Exception as exc:
        logger.warning("Reply pathate parini: %s", exc)
        await update.message.reply_text(
            "❌ ওই ইউজারকে মেসেজ পাঠানো যায়নি। হয়তো সে বট /start করেনি।"
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    conn = get_conn()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_balance = conn.execute("SELECT COALESCE(SUM(balance), 0) FROM users").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    order_total = conn.execute(
        "SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'done'"
    ).fetchone()[0]
    dep_count = conn.execute(
        "SELECT COUNT(*) FROM deposits WHERE status IN ('approved', 'auto_approved')"
    ).fetchone()[0]
    dep_total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM deposits WHERE status IN ('approved', 'auto_approved')"
    ).fetchone()[0]
    ref_users = conn.execute(
        "SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    await update.message.reply_text(
        "📊 SM SHADIN Stats:\n"
        f"👥 মোট ইউজার: {total_users} জন\n"
        f"💳 ইউজারদের মোট ব্যালেন্স: ৳{total_balance}\n"
        f"🛒 মোট অর্ডার: {total_orders} টা (৳{order_total})\n"
        f"💰 Approve হওয়া Deposit: {dep_count} টা (৳{dep_total})\n"
        f"🔗 Referral দিয়ে আসা ইউজার: {ref_users} জন"
    )


async def away_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not is_admin(user.id):
        await update.message.reply_text("এই কমান্ড শুধু অ্যাডমিন ব্যবহার করতে পারবে।")
        return
    if context.args and context.args[0].lower() in ("on", "off"):
        mode = context.args[0].lower()
        set_setting("away", mode)
        if mode == "on":
            await update.message.reply_text(
                "✅ Away mode ON হয়েছে। এখন থেকে কাস্টমার ফ্রি-টেক্সট লিখলে "
                "অফলাইন মেসেজ পাবে।"
            )
        else:
            await update.message.reply_text(
                "✅ Away mode OFF হয়েছে। কাস্টমার আবার আগের মতো মেনু গাইড পাবে।"
            )
        return
    current = get_setting("away", "off")
    await update.message.reply_text(
        f"Away mode এখন: {current.upper()}\n"
        "চালু করতে: /away on\n"
        "বন্ধ করতে: /away off"
    )


# ---------------- Auto reply (preset, keyword based) ----------------
# Admin-er manual reply charai customer-er sadharon proshner uttor dey.
# Kono keyword na mille ager away/menu-guide logic cholbe.

def auto_reply_text(text):
    if not text:
        return None
    t = text.lower()
    if any(k in t for k in ("deposit", "ডিপোজিট", "জমা")):
        return (
            "💰 Deposit করতে Deposit বোতাম চাপুন, তারপর টাকার পরিমাণ লিখুন।\n"
            "Minimum deposit ৳20।\n"
            f"বিকাশ / নগদ Send Money করুন: {PAYMENT_NUMBER}\n\n"
            "✅ TrxID সেন্ট করেন, আপনার ব্যালেন্স সাথে সাথে এড হয়ে যাবে অটো বট চেকের মাধ্যমে।\n"
            "ধন্যবাদ।"
        )
    if any(k in t for k in ("payment", "bkash", "nagad", "বিকাশ", "নগদ", "পেমেন্ট", "টাকা পাঠ")):
        return (
            "💳 পেমেন্ট করুন:\n"
            f"বিকাশ / নগদ Send Money: {PAYMENT_NUMBER}\n\n"
            "টাকা পাঠানোর পর TrxID এখানে লিখে পাঠান।\n"
            "✅ TrxID সেন্ট করেন, আপনার ব্যালেন্স সাথে সাথে এড হয়ে যাবে অটো বট চেকের মাধ্যমে।"
        )
    if any(k in t for k in ("proxy", "প্রক্সি")):
        return (
            "🌐 Proxy প্যাকেজ:\n"
            "10 IP (9Proxy) ৳59, 100 MB (9Proxy) ৳25, 200 MB (9Proxy) ৳35,\n"
            "100 MB (RapidProxy) ৳25, 200 MB (RapidProxy) ৳35,\n"
            "100 MB (711Proxy) ৳25, 200 MB (711Proxy) ৳35,\n"
            "100 MB (H143Proxy) ৳19, 200 MB (H143Proxy) ৳23\n\n"
            "কিনতে নিচের মেনু থেকে Buy Proxy চাপুন।"
        )
    if any(k in t for k in ("price", "dam", "দাম", "প্রাইস", "package", "প্যাকেজ", "list", "লিস্ট")):
        return (
            "📦 VPN প্যাকেজ:\n"
            "Nord 7 দিন ৳25, Express 3 দিন ৳20, CyberGhost 3 দিন ৳20, PIA 3 দিন ৳20,\n"
            "Surfshark 7 দিন ৳25, IPVanish 7 দিন ৳25, HMA 7 দিন ৳25,\n"
            "Proton 14 দিন ৳50, Nord 30 দিন ৳110, HMA 30 দিন ৳50\n\n"
            "কিনতে নিচের মেনু থেকে Buy VPN চাপুন।"
        )
    if any(k in t for k in ("kinbo", "kinte", "kivabe", "কিনবো", "কিনতে", "কিভাবে", "কেমনে", "order", "অর্ডার")):
        return (
            "🛒 কিভাবে কিনবেন:\n"
            "১. নিচের মেনু থেকে Buy VPN বা Buy Proxy চাপুন\n"
            "২. প্যাকেজ বেছে নিন\n"
            "৩. Balance দিয়ে কিনুন, অথবা বিকাশ / নগদে টাকা পাঠিয়ে TrxID পাঠান\n"
            "৪. পেমেন্ট যাচাই হলে অ্যাকাউন্ট পাঠিয়ে দেওয়া হবে"
        )
    if any(k in t for k in ("kobe", "kখন", "কবে", "কখন", "delivery", "ডেলিভারি", "account", "অ্যাকাউন্ট", "পাবো")):
        return (
            "⏳ পেমেন্ট যাচাই হলে যত দ্রুত সম্ভব আপনার VPN / Proxy অ্যাকাউন্ট পাঠিয়ে দেওয়া হবে।\n"
            "দেরি হলে Support-এ মেসেজ করুন।"
        )
    if any(k in t for k in ("balance", "ব্যালেন্স")):
        return (
            "💳 আপনার ব্যালেন্স দেখতে নিচের মেনু থেকে Balance চাপুন।\n"
            "ব্যালেন্স বাড়াতে Deposit চাপুন। Minimum deposit ৳20।"
        )
    if any(k in t for k in ("support", "help", "সমস্যা", "problem", "kotha", "কথা")):
        return (
            "🎧 Support-এর জন্য এখানে মেসেজ করুন:\n"
            f"👉 {ORDER_LINK}\n"
            "অথবা কমিউনিটি চ্যানেল: https://t.me/socialmarketing22"
        )
    if any(k in t for k in ("referral", "রেফার", "invite", "ইনভাইট")):
        return (
            "🔗 Referral লিংক আর আপনার রেফার কাউন্ট দেখতে নিচের মেনু থেকে Referral চাপুন।\n"
            "নিয়ম: আপনার লিংক দিয়ে আসা বন্ধুদের মোট 10 টা Balance অর্ডার হলে আপনি ৳5 বোনাস পাবেন।"
        )
    if any(k in t for k in ("meyad", "মেয়াদ", "expiry", "শেষ", "sesh")):
        return (
            "📅 প্যাকেজের মেয়াদ শেষ হলে আবার নতুন করে একই প্যাকেজ কিনতে হবে।\n"
            "মেয়াদ শেষ হওয়ার আগেই নতুন প্যাকেজ কিনে রাখতে পারেন।"
        )
    if any(k in t for k in ("hi", "hello", "salam", "সালাম", "হাই", "আসসালামু")):
        return (
            "👋 আসসালামু আলাইকুম! SM SHADIN Shop-এ স্বাগতম।\n"
            "নিচের মেনু থেকে Buy VPN চাপ দিয়ে প্যাকেজ বেছে নিন, "
            "অথবা দাম লিখলে প্যাকেজের দাম দেখতে পাবেন।"
        )
    return None


# ---------------- Text / photo input ----------------

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    package = context.user_data.get("package")
    user = update.message.from_user
    ensure_user(user)
    if not await check_force_join(update.message, context.bot, user.id):
        return

    # Support: Support button chaple porer message admin-er kache jabe.
    if state == WAITING_SUPPORT:
        if not ADMIN_ID:
            await update.message.reply_text(
                "দুঃখিত, এখন Support মেসেজ পাঠানো যাচ্ছে না। সরাসরি এখানে মেসেজ করুন:\n"
                f"👉 {ORDER_LINK}"
            )
            context.user_data.clear()
            return
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=update.message.photo[-1].file_id,
                caption=(
                    "🎧 নতুন Support মেসেজ!\n"
                    f"👤 কাস্টমার: {customer_label(user)}\n"
                    f"🆔 User ID: {user.id}\n"
                    f"📝 মেসেজ: {update.message.caption or ''}\n"
                    "উত্তর দিতে: /reply "
                    f"{user.id} <আপনার মেসেজ>"
                ),
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🎧 নতুন Support মেসেজ!\n"
                    f"👤 কাস্টমার: {customer_label(user)}\n"
                    f"🆔 User ID: {user.id}\n"
                    f"📝 মেসেজ: {update.message.text}\n"
                    "উত্তর দিতে: /reply "
                    f"{user.id} <আপনার মেসেজ>"
                ),
            )
        context.user_data.clear()
        await update.message.reply_text(
            "✅ আপনার মেসেজ অ্যাডমিনের কাছে পৌঁছেছে! অ্যাডমিন বট থেকেই উত্তর দেবে।"
        )
        return

    # Step 1: Deposit-er taka-r poriman
    if state == WAITING_DEPOSIT_AMOUNT:
        if update.message.photo:
            await update.message.reply_text(
                "আগে কত টাকা জমা দেবেন, শুধু সংখ্যাটা লিখুন।"
            )
            return
        raw = (update.message.text or "").strip().replace("৳", "").replace(",", "")
        try:
            amount = int(raw)
        except ValueError:
            await update.message.reply_text(
                "শুধু সংখ্যাটা লিখুন।"
            )
            return
        if amount < 20:
            await update.message.reply_text("Minimum deposit ৳20। 20 বা তার বেশি লিখুন।")
            return
        context.user_data["deposit_amount"] = amount
        context.user_data["state"] = WAITING_DEPOSIT_PROOF
        await update.message.reply_text(
            f"💰 ৳{amount} Deposit করুন:\n"
            f"বিকাশ / নগদ Send Money করুন: {PAYMENT_NUMBER}\n\n"
            "✅ TrxID সেন্ট করেন, আপনার ব্যালেন্স সাথে সাথে এড হয়ে যাবে অটো বট চেকের মাধ্যমে।\n"
            "ধন্যবাদ।"
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
        # ---- SMS AutoPay: text TrxID hole age auto-match check korun ----
        if not update.message.photo and trxid:
            trxid_clean = trxid.upper().strip()
            if " " in trxid_clean:
                _m = re.search(r"\b[A-Z0-9]{8,12}\b", trxid_clean)
                if _m:
                    trxid_clean = _m.group(0)
            if is_trxid_already_credited(trxid_clean):
                context.user_data.clear()
                await update.message.reply_text(
                    "❌ এই TrxID দিয়ে আগেই ব্যালেন্স দেওয়া হয়েছে।\n"
                    "একই TrxID দুবার ব্যবহার করা যাবে না।\n"
                    "এটা আপনার পেমেন্ট হলে Support-এ মেসেজ করুন।"
                )
                return
            if find_unused_sms(trxid_clean, amount):
                dep_id = create_deposit(user.id, user.username, amount, trxid_clean)
                set_deposit_status(dep_id, "auto_approved")
                mark_sms_used(trxid_clean)
                new_balance = add_balance(user.id, amount)
                context.user_data.clear()
                await update.message.reply_text(
                    f"✅ Auto Payment সফল! ৳{amount} আপনার ব্যালেন্সে যোগ হয়েছে।\n"
                    f"💳 বর্তমান ব্যালেন্স: ৳{new_balance}\n"
                    f"📝 TrxID: {trxid_clean}"
                )
                if ADMIN_ID:
                    try:
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=(
                                "🤖 Auto-credited (SMS match, kono manual kaj lageni)!\n"
                                f"👤 কাস্টমার: {customer_label(user)}\n"
                                f"🆔 User ID: {user.id}\n"
                                f"💵 পরিমাণ: ৳{amount}\n"
                                f"📝 TrxID: {trxid_clean}\n"
                                f"💳 বর্তমান ব্যালেন্স: ৳{new_balance}"
                            ),
                        )
                    except Exception:
                        pass
                return
        dep_id = create_deposit(user.id, user.username, amount, trxid)
        caption = (
            "💰 নতুন Deposit Request!\n"
            f"👤 কাস্টমার: {customer_label(user)}\n"
            f"🆔 User ID: {user.id}\n"
            f"💵 পরিমাণ: ৳{amount}\n"
            f"📝 TrxID / মেসেজ: {trxid or '-'}\n"
            "⚠️ Auto-match hoyni (SMS ekhono aseni ba TrxID mileni) — manual check korun."
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
            "✅ Deposit request পৌঁছেছে! SMS-এর সাথে TrxID মেলেনি, তাই "
            "অটো হয়নি — অ্যাডমিন চেক করে Approve করলে "
            "আপনার ব্যালেন্সে টাকা যোগ হয়ে যাবে।"
        )
        return

    # Cash-e Proxy kenar proman (manual jachai)
    proxy = context.user_data.get("proxy")
    if state == WAITING_PROXY_PAYMENT and proxy:
        if not ADMIN_ID:
            logger.warning("ADMIN_ID set kora nei, tai proxy order forward kora jayni.")
            await update.message.reply_text(
                "দুঃখিত, এখন অর্ডার নেওয়া যাচ্ছে না। সরাসরি এখানে মেসেজ করুন:\n"
                f"👉 {ORDER_LINK}"
            )
            return
        pname, pduration, pprice = proxy
        pcaption = (
            "🛒 নতুন Proxy অর্ডার!\n"
            f"🌐 প্যাকেজ: {pname} - {pduration}\n"
            f"💰 দাম: ৳{pprice}\n"
            f"👤 কাস্টমার: {customer_label(user)}\n"
            f"🆔 User ID: {user.id}"
        )
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            text = update.message.caption or ""
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo_id,
                caption=pcaption + (f"\n📝 মেসেজ: {text}" if text else ""),
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=pcaption + f"\n📝 TrxID / মেসেজ: {update.message.text}",
            )
        record_order(user.id, "Proxy", pname, pduration, pprice, "cash", "pending")
        context.user_data.clear()
        await update.message.reply_text(
            "✅ অর্ডার পৌঁছেছে! আমরা পেমেন্ট যাচাই করে যত দ্রুত সম্ভব "
            "আপনার Proxy details পাঠিয়ে দেবো।"
        )
        return

    # Cash-e VPN kenar proman (ager moto, manual jachai)
    if state != WAITING_PAYMENT or not package:
        # Age preset auto-reply check: keyword mille preset uttor, state clear hobe na
        # jate customer tarporo TrxID / order pathate pare.
        if update.message.text:
            _auto = auto_reply_text(update.message.text)
            if _auto:
                await update.message.reply_text(_auto)
                return
        if get_setting("away", "off") == "on":
            await update.message.reply_text(
                "⏳ শাদিন ভাই এখন অফলাইন আছেন। অনলাইন আসলে আপনার "
                "মেসেজের রিপ্লাই দেবেন।\n\n"
                "জরুরি হলে Support-এ মেসেজ করুন:\n"
                f"👉 {ORDER_LINK}"
            )
        else:
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
    record_order(user.id, "VPN", name, duration, price, "cash", "pending")
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
    app.add_handler(CommandHandler("sendproxy", sendproxy_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("away", away_command))
    app.add_handler(CommandHandler("reply", reply_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.Regex("Buy VPN"), menu_buy_vpn))
    app.add_handler(MessageHandler(filters.Regex("Buy Proxy"), menu_buy_proxy))
    app.add_handler(MessageHandler(filters.Regex("Balance"), menu_balance))
    app.add_handler(MessageHandler(filters.Regex("Deposit"), menu_deposit))
    app.add_handler(MessageHandler(filters.Regex("Referral"), menu_referral))
    app.add_handler(MessageHandler(filters.Regex("Support"), menu_support))
    app.add_handler(MessageHandler(filters.Regex("আমার অর্ডার"), menu_my_orders))
    app.add_handler(CallbackQueryHandler(verify_join_callback, pattern=r"^verify_join$"))
    app.add_handler(CallbackQueryHandler(package_selected, pattern=r"^pkg:\d+$"))
    app.add_handler(CallbackQueryHandler(pay_with_balance, pattern=r"^paybal:\d+$"))
    app.add_handler(CallbackQueryHandler(pay_with_cash, pattern=r"^paycash:\d+$"))
    app.add_handler(CallbackQueryHandler(back_to_list, pattern=r"^back$"))
    app.add_handler(CallbackQueryHandler(proxy_selected, pattern=r"^proxy:\d+$"))
    app.add_handler(CallbackQueryHandler(pay_proxy_with_balance, pattern=r"^proxpaybal:\d+$"))
    app.add_handler(CallbackQueryHandler(pay_proxy_with_cash, pattern=r"^proxpaycash:\d+$"))
    app.add_handler(CallbackQueryHandler(back_to_proxy_list, pattern=r"^proxyback$"))
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
