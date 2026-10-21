import os
import re
import json
import math
import time
import random
import secrets
import hashlib
import asyncio
import logging
import webbrowser
from getpass import getpass
import sqlite3
import aiohttp
from aiohttp import web

from datetime import datetime, date, timezone
from urllib.parse import urlparse

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.error import TelegramError, BadRequest, NetworkError
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

# =========================================================
# ULTIMATE SMM BOT - PYTHON 3.13 | شحن Telegram Stars داخل البوت الأساسي
# Programmer: محمود (@mlojlkkkj)
# Branding/location label supplied by owner: سوريا - محافظة دير الزور
# This label is static metadata; the bot does not collect device fingerprints or GPS location.
# =========================================================

import os  # required for environment-based configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
except (TypeError, ValueError):
    OWNER_ID = 0
DB_FILE = os.getenv("DB_FILE", "ultimate_smm.db")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "MHMWD2008")
REQUIRED_CHANNEL = "@mlojlkkkji"
REQUIRED_CHANNEL_URL = "https://t.me/mlojlkkkji"
PROGRAMMER_NAME = "محمود"
PROGRAMMER_TELEGRAM = "@mlojlkkkj"
OWNER_REGION_LABEL = "سوريا - محافظة دير الزور"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ULTIMATE_SMM")

# Reuse one HTTP connection pool instead of creating a new session for every API call.
_HTTP_SESSION = None
_HTTP_SESSION_LOCK = asyncio.Lock()

PLATFORMS = {
    "instagram": "📸 إنستغرام",
    "telegram": "✈️ تيليجرام",
    "whatsapp": "🟢 واتساب",
    "facebook": "🔵 فيسبوك",
    "tiktok": "🎵 تيك توك",
    "youtube": "▶️ يوتيوب",
    "x": "𝕏 إكس",
    "twitter": "𝕏 تويتر",
    "snapchat": "👻 سناب شات",
    "threads": "🧵 ثريدز",
    "twitch": "🟣 تويتش",
    "discord": "🎮 ديسكورد",
    "spotify": "🎧 سبوتيفاي",
    "website": "🌐 مواقع إلكترونية",
    "crypto": "🪙 العملات الرقمية",
    "free": "🎁 الخدمات المجانية",
}

# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")

        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            points INTEGER DEFAULT 0,
            joined TEXT,
            referral_by INTEGER DEFAULT 0,
            vip_until TEXT DEFAULT '',
            completed_orders INTEGER DEFAULT 0,
            last_daily TEXT DEFAULT '',
            last_spin TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS admins(
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS providers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            api_url TEXT NOT NULL,
            api_key TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            owner_id INTEGER DEFAULT 0,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS services(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id INTEGER NOT NULL,
            external_id TEXT NOT NULL,
            platform TEXT DEFAULT 'other',
            name TEXT DEFAULT '',
            category TEXT DEFAULT '',
            provider_rate REAL DEFAULT 0,
            price_usd REAL DEFAULT 0,
            price_points INTEGER DEFAULT 0,
            min_qty INTEGER DEFAULT 1,
            max_qty INTEGER DEFAULT 100000,
            enabled INTEGER DEFAULT 1,
            section_id INTEGER DEFAULT NULL,
            UNIQUE(provider_id, external_id),
            FOREIGN KEY(provider_id) REFERENCES providers(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS service_sections(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            name TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            UNIQUE(platform,name)
        );

        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            link TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            cost_points INTEGER NOT NULL,
            cost_usd REAL DEFAULT 0,
            provider_order_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created TEXT,
            FOREIGN KEY(service_id) REFERENCES services(id)
        );

        CREATE TABLE IF NOT EXISTS payments(
            charge_id TEXT PRIMARY KEY,
            user_id INTEGER,
            stars INTEGER,
            credited_points INTEGER,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS api_clients(
            user_id INTEGER PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            token_prefix TEXT DEFAULT '',
            balance INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created TEXT NOT NULL,
            updated TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS api_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            kind TEXT NOT NULL,
            reference TEXT NOT NULL UNIQUE,
            details TEXT DEFAULT '',
            created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_order_id TEXT NOT NULL,
            provider_order_id TEXT DEFAULT '',
            service_id INTEGER NOT NULL,
            cost INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created TEXT NOT NULL,
            UNIQUE(user_id, client_order_id)
        );

        CREATE TABLE IF NOT EXISTS paid_access(
            user_id INTEGER PRIMARY KEY,
            charge_id TEXT DEFAULT '',
            stars INTEGER DEFAULT 0,
            paid_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS manual_deposits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            amount_usd REAL NOT NULL,
            reference TEXT DEFAULT '',
            receipt_file_id TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created TEXT NOT NULL,
            reviewed_by INTEGER DEFAULT 0,
            reviewed_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS recharge_codes(
            code TEXT PRIMARY KEY,
            points INTEGER NOT NULL CHECK(points > 0),
            created_by INTEGER NOT NULL,
            created TEXT NOT NULL,
            redeemed_by INTEGER DEFAULT NULL,
            redeemed_at TEXT DEFAULT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_recharge_codes_redeemed
            ON recharge_codes(redeemed_by, created);

        CREATE TABLE IF NOT EXISTS referrals(
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER NOT NULL,
            reward INTEGER DEFAULT 0,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS point_transfers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender INTEGER,
            receiver INTEGER,
            amount INTEGER,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS channel_tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            reward INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS task_claims(
            user_id INTEGER,
            task_id INTEGER,
            created TEXT,
            PRIMARY KEY(user_id,task_id)
        );

        CREATE TABLE IF NOT EXISTS channel_funding_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            reward INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS channel_funding_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            channel_username TEXT DEFAULT '',
            title TEXT DEFAULT '',
            funding_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_member INTEGER NOT NULL,
            total_cost INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS funding_member_claims(
            order_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created TEXT NOT NULL,
            PRIMARY KEY(order_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS daily_claims(
            user_id INTEGER,
            claim_date TEXT,
            reward INTEGER,
            PRIMARY KEY(user_id,claim_date)
        );

        CREATE TABLE IF NOT EXISTS spins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reward INTEGER,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS forced_channels(
            chat_id TEXT PRIMARY KEY,
            title TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS user_bots(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bot_token TEXT,
            provider_id INTEGER,
            enabled INTEGER DEFAULT 1,
            created TEXT
        );

        CREATE TABLE IF NOT EXISTS access_auth(
            user_id INTEGER PRIMARY KEY,
            authorized_at TEXT NOT NULL
        );
        """)
        # Migrate provider columns for databases created by older versions.
        # CREATE TABLE IF NOT EXISTS does not add new columns to an existing table.
        provider_columns = {
            r["name"]
            for r in c.execute("PRAGMA table_info(providers)").fetchall()
        }
        # Complete provider migration (SQLite CREATE TABLE IF NOT EXISTS does not
        # update old tables). This also fixes older databases missing owner_id.
        provider_migrations = {
            "name": "TEXT NOT NULL DEFAULT ''",
            "api_url": "TEXT NOT NULL DEFAULT ''",
            "api_key": "TEXT NOT NULL DEFAULT ''",
            "enabled": "INTEGER DEFAULT 1",
            "owner_id": "INTEGER DEFAULT 0",
            "created": "TEXT DEFAULT ''",
            "profit_percent": "REAL DEFAULT -1",
        }
        for column, declaration in provider_migrations.items():
            if column not in provider_columns:
                c.execute(f"ALTER TABLE providers ADD COLUMN {column} {declaration}")

        # Keep old rows valid after migration; don't overwrite existing credentials.
        c.execute("UPDATE providers SET owner_id=0 WHERE owner_id IS NULL")
        c.execute("UPDATE providers SET enabled=1 WHERE enabled IS NULL")

        # Ensure the owner's required public channel is always included.
        c.execute(
            "INSERT OR IGNORE INTO forced_channels(chat_id,title,enabled) VALUES(?,?,1)",
            (REQUIRED_CHANNEL, "قناة محمود الرسمية")
        )

        # Migrate older databases before any query uses newer columns.
        # Migrate existing databases created by older bot versions.
        service_columns = {
            r["name"]
            for r in c.execute("PRAGMA table_info(services)").fetchall()
        }
        if "platform" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN platform TEXT DEFAULT 'other'")
        if "name" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN name TEXT DEFAULT ''")
        if "category" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN category TEXT DEFAULT ''")
        if "provider_rate" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN provider_rate REAL DEFAULT 0")
        if "price_usd" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN price_usd REAL DEFAULT 0")
        if "price_points" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN price_points INTEGER DEFAULT 0")
        if "min_qty" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN min_qty INTEGER DEFAULT 1")
        if "max_qty" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN max_qty INTEGER DEFAULT 100000")
        if "enabled" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN enabled INTEGER DEFAULT 1")
        if "delivery_mode" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN delivery_mode TEXT DEFAULT 'provider'")
        if "manual_instruction" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN manual_instruction TEXT DEFAULT ''")
        if "section_id" not in service_columns:
            c.execute("ALTER TABLE services ADD COLUMN section_id INTEGER DEFAULT NULL")

        # Migrate older order tables before any order/payment path uses new fields.
        order_columns = {r["name"] for r in c.execute("PRAGMA table_info(orders)").fetchall()}
        for column, declaration in {
            "cost_points": "INTEGER NOT NULL DEFAULT 0",
            "cost_usd": "REAL DEFAULT 0",
            "provider_order_id": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT 'pending'",
            "created": "TEXT DEFAULT ''",
        }.items():
            if column not in order_columns:
                c.execute(f"ALTER TABLE orders ADD COLUMN {column} {declaration}")

        admin_columns = {
            r["name"]
            for r in c.execute("PRAGMA table_info(admins)").fetchall()
        }
        if "created" not in admin_columns:
            c.execute("ALTER TABLE admins ADD COLUMN created TEXT DEFAULT ''")
        if "added_by" not in admin_columns:
            c.execute("ALTER TABLE admins ADD COLUMN added_by INTEGER DEFAULT 0")

        defaults = {
            "shop_name": "💎✨ 𝗠𝗔𝗛𝗠𝗢𝗨𝗗 | محمود ✨💎",
            "welcome": "✨ أهلاً بك في متجر محمود للخدمات الرقمية ✨",
            "support": "تواصل مع إدارة المتجر للحصول على الدعم.",
            "currency_mode": "points",
            "points_per_usd": "1000",
            "profit_percent": "20",
            "default_referral_reward": "25",
            "daily_reward": "10",
            "spin_min": "0",
            "spin_max": "100",
            "transfer_min": "10",
            "points_per_star": "10",
            "vip_price_stars": "100",
            "vip_days": "30",
            "maintenance": "0",
            "completion_message": "✅ تم تسجيل طلبك بنجاح.",
            "order_complete_sound": "0",
            "custom_notice": "",
            "force_subscription_enabled": "1",
            "force_subscription_text": "اشترك بالقناة أولاً ثم تحقق من اشتراكك.",
            "paid_gate_enabled": "0",
            "paid_gate_stars": "10",
            "completed_orders_channel": "",
            "orders_channel": "",
            "channel_join_reward": "10",
            "channel_member_price": "20",
            "api_stars_rate": "1",
            "api_stars_packages": "100,500,1000,5000,10000,50000,100000",
            "api_public_url": "",
        }

        for key, value in defaults.items():
            c.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                (key, value)
            )
        # Forced channel subscription is always enabled; paid access is a separate optional gate.
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('force_subscription_enabled','1')")
        c.execute("UPDATE forced_channels SET enabled=1")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('channel_member_price','15')")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('channel_funding_min_qty','20')")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('channel_funding_max_qty','100000')")

        c.execute(
            "INSERT OR IGNORE INTO admins(user_id,added_by,created) VALUES(?,?,?)",
            (OWNER_ID, OWNER_ID, datetime.now(timezone.utc).isoformat())
        )

        # Safe migrations for databases created by older versions.
        task_columns = {r["name"] for r in c.execute("PRAGMA table_info(channel_tasks)").fetchall()}
        if "owner_id" not in task_columns:
            c.execute("ALTER TABLE channel_tasks ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 0")
        if "member_price" not in task_columns:
            c.execute("ALTER TABLE channel_tasks ADD COLUMN member_price INTEGER NOT NULL DEFAULT 0")
        if "funding_order_id" not in task_columns:
            c.execute("ALTER TABLE channel_tasks ADD COLUMN funding_order_id INTEGER NOT NULL DEFAULT 0")
        if "target_quantity" not in task_columns:
            c.execute("ALTER TABLE channel_tasks ADD COLUMN target_quantity INTEGER NOT NULL DEFAULT 0")
        if "completed_count" not in task_columns:
            c.execute("ALTER TABLE channel_tasks ADD COLUMN completed_count INTEGER NOT NULL DEFAULT 0")
        funding_order_columns = {r["name"] for r in c.execute("PRAGMA table_info(channel_funding_orders)").fetchall()}
        if "completed_count" not in funding_order_columns:
            c.execute("ALTER TABLE channel_funding_orders ADD COLUMN completed_count INTEGER NOT NULL DEFAULT 0")
        columns = {
            r["name"]
            for r in c.execute("PRAGMA table_info(users)").fetchall()
        }
        for name, declaration in {
            "referral_by": "INTEGER DEFAULT 0",
            "vip_until": "TEXT DEFAULT ''",
            "completed_orders": "INTEGER DEFAULT 0",
            "last_daily": "TEXT DEFAULT ''",
            "last_spin": "TEXT DEFAULT ''",
        }.items():
            if name not in columns:
                c.execute(f"ALTER TABLE users ADD COLUMN {name} {declaration}")

        # Indexes keep common lookups and the order monitor responsive as data grows.
        c.execute("CREATE INDEX IF NOT EXISTS idx_orders_status_id ON orders(status, id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_services_provider_id ON services(provider_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_services_section_enabled ON services(section_id,enabled)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_services_platform_enabled ON services(platform,enabled)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_api_ledger_user_created ON api_ledger(user_id, created)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_api_orders_user_id ON api_orders(user_id)")


def get_setting(key, default=""):
    with db() as c:
        row = c.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with db() as c:
        c.execute("""
        INSERT INTO settings(key,value) VALUES(?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))


def is_admin(uid):
    with db() as c:
        return c.execute(
            "SELECT 1 FROM admins WHERE user_id=?", (uid,)
        ).fetchone() is not None


def register_user(user, referrer=0):
    with db() as c:
        c.execute("""
        INSERT OR IGNORE INTO users(user_id,username,points,joined,referral_by)
        VALUES(?,?,0,?,?)
        """, (
            user.id,
            user.username or "",
            datetime.now(timezone.utc).isoformat(),
            referrer if referrer != user.id else 0,
        ))
        c.execute(
            "UPDATE users SET username=? WHERE user_id=?",
            (user.username or "", user.id)
        )


def balance(uid):
    with db() as c:
        row = c.execute(
            "SELECT points FROM users WHERE user_id=?", (uid,)
        ).fetchone()
    return int(row["points"]) if row else 0


def credit_points(uid, amount):
    if amount <= 0:
        raise ValueError("المبلغ يجب أن يكون موجباً")

    with db() as c:
        cur = c.execute(
            "UPDATE users SET points=points+? WHERE user_id=?",
            (amount, uid)
        )
        if cur.rowcount != 1:
            raise ValueError("المستخدم غير موجود")


def debit_points(uid, amount):
    if amount <= 0:
        raise ValueError("المبلغ غير صالح")

    with db() as c:
        cur = c.execute("""
        UPDATE users SET points=points-?
        WHERE user_id=? AND points>=?
        """, (amount, uid, amount))
        if cur.rowcount != 1:
            raise ValueError("رصيد النقاط غير كافٍ")


def user_vip(uid):
    with db() as c:
        row = c.execute(
            "SELECT vip_until FROM users WHERE user_id=?", (uid,)
        ).fetchone()

    if not row or not row["vip_until"]:
        return False

    try:
        expiry = datetime.fromisoformat(row["vip_until"])
        # Normalize legacy naive timestamps and timezone-aware timestamps to UTC.
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry > datetime.now(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return False


# =========================================================
# PAYMENT METHODS
# =========================================================
MANUAL_PAYMENT_METHODS = {
    "bank": "🏦 حوالة بنكية",
    "exchange": "💵 شركة صرافة / حوالة محلية",
    "usdt": "🪙 USDT (يدوي)",
    "wallet": "📱 محفظة إلكترونية",
    "visa_manual": "💳 Visa / Mastercard (تحويل يدوي)",
    "paypal_manual": "🅿️ PayPal (يدوي)",
}


def payment_instructions(method):
    return get_setting(
        "payment_details_" + method,
        "لم يضبط المشرف بيانات هذه الطريقة بعد. تواصل مع الدعم قبل التحويل."
    )


# =========================================================
# UI
# =========================================================

def btn(text, data, style="primary"):
    """Create a colored Telegram button when supported by python-telegram-bot 22.7+.

    Telegram supports primary (blue), success (green), and danger (red) styles
    through Bot API 9.4+. Older installed libraries fall back to normal buttons.
    """
    # Color/style choices are stored in SQLite and survive restarts.
    style_setting = {"primary": "ui_color_main", "success": "ui_color_sections", "danger": "ui_color_alerts"}.get(style)
    if style_setting:
        configured = get_setting(style_setting, style)
        if configured in ("primary", "success", "danger"):
            style = configured
    try:
        return InlineKeyboardButton(text, callback_data=data, style=style)
    except (TypeError, ValueError):
        # Keep compatibility with older python-telegram-bot installations.
        return InlineKeyboardButton(text, callback_data=data)


def kb(rows):
    return InlineKeyboardMarkup(rows)


async def safe_edit(q, text, **kwargs):
    """Avoid silent callback failures when Telegram refuses an edit."""
    try:
        await q.edit_message_text(text, **kwargs)
    except BadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        log.warning("Callback message edit failed: %s", exc)
        try:
            await q.message.reply_text(text, **kwargs)
        except TelegramError:
            log.exception("Could not send callback fallback message")


def completed_orders_count():
    try:
        with db() as c:
            return int(c.execute("SELECT COUNT(*) n FROM orders WHERE status='completed'").fetchone()["n"])
    except Exception:
        return 0


# Editable interface labels and message templates (admin panel).
UI_LABELS = {
    "home_services": ("🛒 الخدمات", "اسم زر الخدمات"),
    "home_fund_channels": ("📣 تمويل قناتك", "اسم زر تمويل قناتك"),
    "home_earn": ("💎 تجميع نقاط", "اسم زر تجميع النقاط"),
    "home_transfer": ("🔁 تحويل النقاط", "اسم زر تحويل النقاط"),
    "home_recharge_code": ("🎟️ استخدام كود", "اسم زر استخدام كود"),
    "home_account": ("💳 الحساب", "اسم زر الحساب"),
    "home_check_order": ("🔎 فحص الطلب", "اسم زر فحص الطلب"),
    "home_myorders": ("📅 طلباتي", "اسم زر طلباتي"),
    "home_recharge": ("💰 شحن نقاط", "اسم زر شحن النقاط"),
    "home_complete_orders": ("📊 إكمال الطلبات", "اسم زر إكمال الطلبات"),
    "home_terms": ("⚠️ شروط الاستخدام", "اسم زر شروط الاستخدام"),
    "home_crypto": ("🪙 العملات الرقمية", "اسم زر العملات الرقمية"),
    "home_orders_channel": ("📣 قناة الطلبات", "اسم زر قناة الطلبات"),
    "home_support": ("🆘 الدعم الفني", "اسم زر الدعم الفني"),
    "home_admin": ("⚙️ لوحة التحكم", "اسم زر لوحة التحكم"),
}
UI_MESSAGES = {
    "welcome": ("- اهـلاً بك في بوت الجزراوي 💎\n • البوت مختص لرشق جميع البرامج 🚀\n • سارع بتجربة أسرع وافضل الخدمات ⚡\n🎁 | ايديك : {id}\n👤 | عدد نقاطك : {points} نقطة", "كليشة الترحيب"),
    "services_intro": ("🛍 اختر التطبيق لعرض خدماته:", "كليشة بداية قسم الخدمات"),
    "fund_channels_intro": ("📣 تمويل قناتك\n\nأرسل @username أو رابط قناتك العامة. بعد التحقق من أنك مالك/مشرف القناة ومن صلاحيات البوت، ستُضاف تلقائياً إلى (تجميع نقاط).\n🎁 مكافأة المشترك: {reward} نقطة\n💰 السعر على صاحب القناة لكل عضو: {price} نقطة\n\nأضف البوت مشرفاً في قناتك قبل المتابعة. اكتب إلغاء للتراجع.", "كليشة تمويل قناتك"),
    "fund_channels_success": ("🎉 تم تفعيل تمويل قناتك بنجاح!\n\n📣 القناة: {title}\n🎁 مكافأة المشترك: {reward} نقطة\n💰 التكلفة عليك لكل عضو جديد: {price} نقطة\n\n✅ أُضيفت القناة تلقائياً إلى (تجميع نقاط)، ولن تُضاف إلى الاشتراك الإجباري.\nملاحظة: يجب توفر رصيد كافٍ في حسابك ليستمر استقبال الأعضاء.", "كليشة نجاح تمويل القناة"),
    "order_service_info": ("💎| اسم الخدمة : {service_name}\n💎| السعر : لكل 1000⇐ {price} نقطة\n⚡| اقل طلب : {min_qty}\n🚀| اكبر طلب : {max_qty}\n🆔| ايدي الخدمة : {service_id}\n\n📮 ارسل العدد الذي تريد طلبه:", "كليشة تفاصيل الخدمة وطلب العدد"),
    "order_link_prompt": ("⌚| البدء: 0 - 10 دقيقة\n♻️| الضمان: مدى الحياة\n• #هــــام ⚠️\n📌| تأكد من الرابط قبل تقديم الطلب\n📌| لا تقدم طلباً آخر على نفس الرابط قبل اكتمال الطلب الأول\n📌| خلاف ذلك يعتبر طلبك مكتملاً ولا يتم استرجاع نقاطك ‼️\n• ارسل رابط #المنشور الان ✅:", "كليشة الضمان والتنبيه وطلب الرابط"),
    "order_pending": ("✅ تم قبول طلبك في الموقع بنجاح\n━━━━━━━━━━━━━━\n🆔 رقم الطلب: #{order_id}\n🛍 الخدمة: {service_name}\n📦 الكمية: {quantity}\n💰 التكلفة: {cost} نقطة\n💎 رصيدك الحالي: {points} نقطة\n📌 الحالة: مقبول وقيد التنفيذ\n\nسنرسل لك إشعاراً تلقائياً عند اكتماله أو رفضه.", "كليشة قبول الطلب من الموقع"),
    "order_submission_check": ("⏳ تم استلام طلبك وجارٍ التحقق من تسجيله في الموقع.\n━━━━━━━━━━━━━━\n🆔 رقم الطلب: #{order_id}\n🛍 الخدمة: {service_name}\n📦 الكمية: {quantity}\n💰 التكلفة: {cost} نقطة\n📌 الحالة: قيد التحقق، ولم يتم رفض الطلب.\nسنرسل لك تحديثاً عندما تتأكد حالة الطلب.", "كليشة التحقق من تسجيل الطلب بالموقع"),
    "order_manual_pending": ("✅| تم استلام طلبك : {order_id}\n💰| التكلفة: {cost} نقطة\n🆔| ايدي الطلب: {order_id}\n💎| نقاطك الحالية: {points} نقطة\n⏳| طلبك قيد مراجعة الإدارة للخدمات اليدوية.", "كليشة استلام الطلب اليدوي"),
    "order_complete": ("🎉 تم اكتمال طلبك بنجاح!\n━━━━━━━━━━━━━━\n🆔 رقم الطلب: #{order_id}\n🛍 الخدمة: {service_name}\n📦 الكمية المكتملة: {quantity}\n📌 الحالة: مكتمل ✅\nشكراً لثقتك بنا 💎", "كليشة إشعار اكتمال الطلب"),
    "order_rejected": ("❌ تم رفض طلبك يدوياً من إدارة الموقع\n━━━━━━━━━━━━━━\n🆔 رقم الطلب: #{order_id}\n🛍 الخدمة: {service_name}\n📦 الكمية: {quantity}\n📌 الحالة: مرفوض يدوياً ❌\n💎 لم تتم إعادة النقاط إلى رصيدك. رفض الموقع التلقائي أو تغيّر الحالة لا يعني استرجاع النقاط.", "كليشة إشعار رفض الطلب يدوياً من الموقع"),
    "terms_text": ("استخدم الخدمات بمسؤولية، وتأكد من صحة الرابط والكمية قبل تأكيد الطلب. الطلبات التي يبدأ تنفيذها لدى المزود قد لا يمكن إلغاؤها.", "كليشة شروط الاستخدام"),
}

def ui_label(key):
    default = UI_LABELS[key][0]
    return get_setting("ui_label_" + key, default)

def ui_message(key):
    default = UI_MESSAGES[key][0]
    return get_setting("ui_message_" + key, default)


def render_template(key, **values):
    """Render editable messages safely; unknown placeholders stay visible."""
    import re
    template = ui_message(key)
    aliases = {
        "id": values.get("user_id", values.get("order_id", "")),
        "user_id": values.get("user_id", ""),
        "username": values.get("username", ""),
        "first_name": values.get("first_name", ""),
        "points": values.get("points", ""),
        "order_id": values.get("order_id", ""),
        "service_name": values.get("service_name", ""),
        "quantity": values.get("quantity", ""),
        "link": values.get("link", ""),
        "cost": values.get("cost", ""),
        "count": values.get("count", ""),
        "price": values.get("price", ""),
        "min_qty": values.get("min_qty", ""),
        "max_qty": values.get("max_qty", ""),
        "service_id": values.get("service_id", ""),
        "reward": values.get("reward", ""),
    }
    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}",
                  lambda m: str(aliases[m.group(1)]) if m.group(1) in aliases else m.group(0), template)

def default_home_layout():
    return [
        ["home_services"], ["home_fund_channels"],
        ["home_earn", "home_transfer"],
        ["home_recharge_code", "home_account"],
        ["home_check_order", "home_myorders"],
        ["home_recharge", "home_complete_orders"],
        ["home_terms"], ["home_crypto"], ["home_orders_channel"],
        ["completed_count_button"], ["home_support"]
    ]


def get_home_layout():
    try:
        hidden = set(json.loads(get_setting("home_hidden_buttons", "[]")))
    except Exception:
        hidden = set()
    try:
        raw = json.loads(get_setting("home_button_layout", ""))
        valid = (set(UI_LABELS) | {"completed_count_button"}) - hidden
        rows = [[k for k in row if k in valid][:2] for row in raw if isinstance(row, list)]
        rows = [row for row in rows if row]
        seen = {k for row in rows for k in row}
        for row in default_home_layout():
            for key in row:
                if key in valid and key not in seen:
                    rows.append([key])
        return rows or [[k] for k in valid]
    except Exception:
        return [[k] for k in (set(UI_LABELS) | {"completed_count_button"}) - hidden]


def home_keyboard(uid):
    rows = []
    for row in get_home_layout():
        buttons = []
        for key in row:
            if key == "completed_count_button":
                label = get_setting("completed_count_button_name", "🛡️ عدد الطلبات المنجزة: {count}").replace("{count}", str(completed_orders_count()))
                buttons.append(btn(label, "completed_count_show", "primary"))
            else:
                callbacks = {
                    "home_services": "services", "home_fund_channels": "fund_channels",
                    "home_earn": "earn", "home_transfer": "transfer",
                    "home_recharge_code": "use_recharge_code", "home_account": "account",
                    "home_check_order": "check_order", "home_myorders": "myorders",
                    "home_recharge": "recharge", "home_complete_orders": "myorders",
                    "home_terms": "terms", "home_crypto": "platform:crypto",
                    "home_orders_channel": "orders_channel_open", "home_support": "support",
                    "home_admin": "admin"
                }
                if key in callbacks:
                    callback_data = get_setting("home_action_" + key, "") or callbacks[key]
                    buttons.append(btn(ui_label(key), callback_data, "primary"))
        if buttons:
            rows.append(buttons)
    if is_admin(uid):
        rows.append([btn(ui_label("home_admin"), "admin", "primary")])
    return kb(rows)


def api_stars_packages():
    """Configured Telegram Stars packages for API account top-ups."""
    raw = get_setting("api_stars_packages", "100,500,1000,5000,10000,50000,100000")
    values = []
    for item in raw.split(","):
        try:
            n = int(item.strip())
            if 100 <= n <= 100000 and n not in values:
                values.append(n)
        except (ValueError, TypeError):
            continue
    return sorted(values) or [100, 500, 1000, 5000, 10000, 50000, 100000]


def admin_keyboard():
    """لوحة إدارة مرتبة على نفس أقسام وتجربة لوحة الزبون."""
    return kb([
        # نظرة عامة على المتجر والعملاء
        [btn("📊 مركز المتجر والإحصائيات", "stats", "success")],
        [btn("👥 إدارة العملاء والأرصدة", "users", "primary"),
         btn("📋 طلبات العملاء", "allorders", "primary")],

        # الخدمات التي يراها الزبون عند الطلب
        [btn("🛍 إدارة الخدمات والأسعار", "manage_services", "success"),
         btn("🎁 جوائز ومكافآت", "rewards", "primary")],
        [btn("🗂 أقسام التطبيقات", "platforms", "primary"),
         btn("⚙️ وضع تنفيذ الطلبات", "order_mode_settings", "primary")],
        [btn("🌐 مزودو الخدمات", "providers", "primary"),
         btn("➕ إضافة مزود API", "provider_add", "primary")],
        [btn("🔄 مزامنة الخدمات", "sync_all", "primary"),
         btn("💳 أرصدة المزودين", "balances", "primary")],

        # رصيد الزبون وطرق الدفع
        [btn("💵 الأسعار والأرباح", "pricing", "success"),
         btn("💎 إعدادات النقاط", "point_settings", "primary")],
        [btn("🎟️ إنشاء كودات شحن", "recharge_codes_admin", "success")],
        [btn("💳 طرق الدفع والشحن", "payment_settings", "primary"),
         btn("🧾 طلبات الدفع اليدوي", "payment_requests", "primary")],
        [btn("🔗 سعر ربط API", "edit_api_link_price", "primary"),
         btn("👥 عملاء API", "api_clients_admin", "primary")],
        [btn("⭐ إعدادات شحن API بالنجوم", "api_stars_admin", "success")],
        [btn("💫 دخول مدفوع بالنجوم", "paid_gate_settings", "primary")],

        # ميزات التفاعل الموجودة في لوحة الزبون
        [btn("🎯 مهام تجميع النقاط", "tasks", "primary"),
         btn("📣 إعدادات تمويل القنوات", "channel_funding_settings", "primary")],
        [btn("📣 قناة الطلبات", "orders_channel", "primary"),
         btn("📣 طلبات التمويل القديمة", "funding_requests", "primary")],
        [btn("🎁 إعدادات الهدايا", "rewards", "primary"),
         btn("⭐ إعدادات VIP", "vip_settings", "primary")],
        [btn("🤖 بوتات VIP", "vip_bots", "primary"),
         btn("📣 قناة الطلبات المكتملة", "completed_channel", "primary")],

        # الاشتراك والاذاعة وإدارة الصلاحيات
        [btn("📢 الاشتراك الإجباري", "force_channels", "primary"),
         btn("📡 إذاعة للجميع والقنوات", "broadcast", "primary")],
        [btn("📝 التحكم بأسماء الواجهة والكلايش", "interface_text_settings", "success")],
        [btn("🧩 ترتيب ودمج أزرار الواجهة", "home_layout_settings", "success")],
        [btn("🎨 ألوان الواجهة والأقسام", "ui_colors", "success")],
        [btn("🛠 إدارة القوائم والأزرار", "menu_button_manager", "success")],
        [btn("✏️ اسم زر الطلبات المنجزة", "completed_count_label_edit", "primary")],
        [btn("👮 المشرفون", "admins", "primary"),
         btn("➕ إضافة مشرف", "admin_add", "primary")],
        [btn("🔧 وضع الصيانة", "maintenance", "danger")],
        [btn("👁 معاينة لوحة الزبون", "home", "success")],
    ])

# =========================================================
# PROVIDER API
# =========================================================

def get_provider(pid):
    with db() as c:
        return c.execute(
            "SELECT * FROM providers WHERE id=? AND enabled=1",
            (pid,)
        ).fetchone()


def all_providers():
    with db() as c:
        return c.execute(
            "SELECT * FROM providers ORDER BY id"
        ).fetchall()


async def get_http_session():
    """Return a reusable aiohttp session with bounded connections and timeouts."""
    global _HTTP_SESSION
    if _HTTP_SESSION is None or _HTTP_SESSION.closed:
        async with _HTTP_SESSION_LOCK:
            if _HTTP_SESSION is None or _HTTP_SESSION.closed:
                timeout = aiohttp.ClientTimeout(total=35, connect=10, sock_read=25)
                connector = aiohttp.TCPConnector(
                    limit=80,
                    limit_per_host=12,
                    ttl_dns_cache=300,
                    enable_cleanup_closed=True,
                )
                # Respect HTTP(S)_PROXY environment variables when the host uses
                # an outbound proxy (as some managed Python hosts do).
                _HTTP_SESSION = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    trust_env=True,
                    headers={"User-Agent": "UltimateSMMBot/2.1"},
                )
    return _HTTP_SESSION


async def api_call(provider, action, params=None):
    """Call a provider using a shared connection pool.

    Read-only actions can be retried after temporary network errors. Order creation
    ('add') is deliberately NOT retried because a timeout can happen after the
    provider accepted the order, and retrying could create a duplicate order.
    """
    if not provider:
        raise RuntimeError("مزود API غير متاح")

    api_url = str(provider["api_url"] or "").strip()
    api_key = str(provider["api_key"] or "").strip()
    if not api_url.startswith(("https://", "http://")):
        raise RuntimeError("رابط API غير صحيح. يجب أن يبدأ بـ http:// أو https://")
    if not api_key:
        raise RuntimeError("مفتاح API للمزود فارغ")

    payload = {"key": api_key, "action": action}
    if params:
        payload.update(params)

    # Never automatically repeat a potentially billable order submission.
    retryable = str(action).lower() in {"services", "status", "balance"}
    attempts = 3 if retryable else 1
    last_error = None
    session = await get_http_session()
    for attempt in range(attempts):
        try:
            async with session.post(api_url, data=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Provider HTTP {response.status}: {body[:180]}",
                        headers=response.headers,
                    )
                try:
                    result = json.loads(body)
                except (ValueError, TypeError) as exc:
                    raise RuntimeError(f"رد المزود ليس JSON صالحاً: {body[:250]}") from exc

            if isinstance(result, dict) and result.get("error"):
                raise RuntimeError(str(result["error"])[:250])
            return result
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(min(0.75 * (2 ** attempt), 3.0) + random.random() * 0.25)
        except RuntimeError:
            raise

    error_text = str(last_error or "خطأ اتصال غير معروف")
    lower_error = error_text.casefold()
    if "403 forbidden" in lower_error or "tunnel connection failed" in lower_error:
        raise RuntimeError(
            "الاستضافة رفضت الاتصال بعنوان المزود عبر وكيل الشبكة (HTTP 403). "
            "جرّب السماح بالنطاق من دعم الاستضافة أو تشغيل البوت على استضافة تسمح بالاتصال به. "
            f"التفاصيل: {error_text[:220]}"
        )
    if "connection refused" in lower_error or "network is unreachable" in lower_error:
        raise RuntimeError(
            "تعذّر فتح اتصال شبكي بخادم المزود من الاستضافة. قد يكون المنفذ 443 محجوباً "
            "أو الخادم لا يقبل الاتصال. تحقق من دعم المزود/الاستضافة. "
            f"التفاصيل: {error_text[:220]}"
        )
    raise RuntimeError(f"تعذر الاتصال بمزود الخدمة بعد {attempts} محاولة: {error_text[:250]}")


def detect_platform(item):
    """Classify provider services by name/category, including common abbreviations."""
    text = " ".join([
        str(item.get("name", "")),
        str(item.get("category", "")),
        str(item.get("type", "")),
    ]).casefold()
    compact = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", text)
    rules = [
        ("instagram", ("instagram", "insta", "ig followers", "ig likes", "انستغرام", "انستجرام", "انستا", "متابعين انستا", "لايكات انستا", "مشاهدات انستا", "حفظ انستا")),
        ("tiktok", ("tiktok", "tik tok", "tt followers", "تيك توك", "تيكتوك", "تيكطوك", "متابعين تيك", "لايكات تيك")),
        ("whatsapp", ("whatsapp", "wa channel", "واتساب", "واتس اب", "واتسآب")),
        ("telegram", ("telegram", "tg channel", "telegram channel", "تيليجرام", "تلغرام", "تيليغرام", "قناة تلغرام")),
        ("facebook", ("facebook", "fb followers", "fb likes", "فيسبوك", "فيس بوك", "متابعين فيسبوك", "لايكات فيسبوك")),
        ("youtube", ("youtube", "yt views", "يوتيوب", "مشاهدات يوتيوب", "مشتركين يوتيوب")),
        ("snapchat", ("snapchat", "snap", "سناب شات", "سناب")),
        ("twitter", ("twitter", "tweets", "تويتر", "اكس تويتر")),
        ("x", ("x.com", "twitter x", "منصة اكس", "إكس", "اكس")),
        ("threads", ("threads", "ثريدز")),
        ("twitch", ("twitch", "تويتش")),
        ("discord", ("discord", "ديسكورد")),
        ("spotify", ("spotify", "سبوتيفاي")),
        ("website", ("website", "seo", "backlink", "web traffic", "مواقع إلكترونية", "مواقع الكترونية", "زيارات موقع", "سيو")),
        ("crypto", ("crypto", "cryptocurrency", "bitcoin", "btc", "ethereum", "eth", "usdt", "binance", "coin", "token", "blockchain", "عملة رقمية", "العملات الرقمية", "بيتكوين", "بتكوين", "ايثيريوم", "إيثيريوم", "بينانس", "كريبتو", "كريبتو", "ترون", "tron")),
    ]
    for platform, keywords in rules:
        for keyword in keywords:
            if keyword.casefold() in text:
                return platform
    return "other"


def get_or_create_free_section(c, platform):
    """Create a dedicated free-services section for the detected platform."""
    name = "🎁 الخدمات المجانية"
    row = c.execute(
        "SELECT id FROM service_sections WHERE platform=? AND name=?",
        (platform, name),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = c.execute(
        "INSERT OR IGNORE INTO service_sections(platform,name,enabled) VALUES(?,?,1)",
        (platform, name),
    )
    row = c.execute(
        "SELECT id FROM service_sections WHERE platform=? AND name=?",
        (platform, name),
    ).fetchone()
    return int(row["id"])


def is_provider_free_service(item, rate):
    """Only treat an explicitly zero-rate provider service as truly free."""
    return float(rate) == 0.0


async def sync_provider(provider):
    items = await api_call(provider, "services")
    if not isinstance(items, list):
        raise RuntimeError("المزود لم يرجع قائمة خدمات")

    added = updated = 0
    provider_profit = provider["profit_percent"] if "profit_percent" in provider.keys() else -1
    profit = max(0.0, float(get_setting("profit_percent", "20")) if provider_profit is None or float(provider_profit) < 0 else float(provider_profit))
    points_per_usd = max(0.000001, float(get_setting("points_per_usd", "1000")))

    with db() as c:
        for item in items:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("service", "")).strip()
            name = str(item.get("name", "")).strip()[:200]
            if not external_id or not name:
                continue
            # Do not interpret a missing/invalid provider rate as zero: that can
            # accidentally turn a paid service into a free service.
            raw_rate = item.get("rate")
            if raw_rate is None or str(raw_rate).strip() == "":
                log.warning("Skipping provider service %s: missing rate", external_id)
                continue
            try:
                rate = float(raw_rate)
                minimum = int(item.get("min", 1))
                maximum = int(item.get("max", 100000))
            except (ValueError, TypeError, OverflowError):
                log.warning("Skipping provider service %s: invalid rate/min/max", external_id)
                continue
            if not math.isfinite(rate) or rate < 0 or minimum < 1 or maximum < minimum:
                log.warning("Skipping provider service %s: out-of-range rate/min/max", external_id)
                continue

            free_service = is_provider_free_service(item, rate)
            selling_price = 0.0 if free_service else rate * (1 + profit / 100)
            price_points = 0 if free_service else max(1, int(math.ceil(selling_price * points_per_usd)))
            # Replace the old "other services" menu entry with one global
            # free-services category, while keeping paid services in their platform.
            platform = "free" if free_service else detect_platform(item)
            category = str(item.get("category", ""))[:100]
            free_section_id = get_or_create_free_section(c, "free") if free_service else None

            existing = c.execute(
                "SELECT id FROM services WHERE provider_id=? AND external_id=?",
                (provider["id"], external_id),
            ).fetchone()
            if existing:
                if free_service:
                    c.execute("""
                        UPDATE services SET platform=?,name=?,category=?,provider_rate=?,
                            price_usd=?,price_points=?,min_qty=?,max_qty=?,section_id=?
                        WHERE id=?
                    """, (platform, name, category, rate, round(selling_price, 6),
                          price_points, minimum, maximum, free_section_id, existing["id"]))
                else:
                    c.execute("""
                        UPDATE services SET platform=?,name=?,category=?,provider_rate=?,
                            price_usd=?,price_points=?,min_qty=?,max_qty=?
                        WHERE id=?
                    """, (platform, name, category, rate, round(selling_price, 6),
                          price_points, minimum, maximum, existing["id"]))
                updated += 1
            else:
                c.execute("""
                    INSERT INTO services(
                        provider_id,external_id,platform,name,category,provider_rate,
                        price_usd,price_points,min_qty,max_qty,section_id
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """, (provider["id"], external_id, platform, name, category, rate,
                      round(selling_price, 6), price_points, minimum, maximum, free_section_id))
                added += 1
    return added, updated


# =========================================================
# OPTIONAL LEGACY AUTH HELPERS / PROGRAMMER BRANDING
# =========================================================

def is_authorized(uid):
    with db() as c:
        return c.execute("SELECT 1 FROM access_auth WHERE user_id=?", (uid,)).fetchone() is not None


def authorize_user(uid):
    with db() as c:
        c.execute(
            "INSERT OR IGNORE INTO access_auth(user_id,authorized_at) VALUES(?,?)",
            (uid, datetime.now(timezone.utc).isoformat())
        )


# =========================================================
# FORCED SUBSCRIPTION
# =========================================================

async def subscribed_to_required_channels(bot, uid):
    """تحقق موحّد من القنوات الإلزامية مع تسجيل سبب الفشل في السجل."""
    with db() as c:
        channels = c.execute("SELECT * FROM forced_channels WHERE enabled=1").fetchall()
        campaigns = c.execute("""SELECT * FROM channel_funding_orders
            WHERE funding_type='mandatory' AND status='active' ORDER BY id""").fetchall()

    async def is_member(chat_id):
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=uid)
            status = str(getattr(member, "status", "")).lower()
            # Restricted users count only when Telegram explicitly says they are still members.
            if status == "restricted":
                return bool(getattr(member, "is_member", False))
            return status in ("member", "administrator", "creator", "owner")
        except TelegramError as exc:
            # Usually caused by the bot not being an admin, wrong chat_id, or an inaccessible channel.
            log.warning("Forced-subscription check failed: uid=%s chat_id=%r error=%s", uid, chat_id, exc)
            return False
        except Exception:
            log.exception("Unexpected forced-subscription check error: uid=%s chat_id=%r", uid, chat_id)
            return False

    for channel in channels:
        if not await is_member(channel["chat_id"]):
            return False

    for campaign in campaigns:
        if not await is_member(campaign["chat_id"]):
            return False
        # لا نحتسب صاحب حملة التمويل ضمن الأعضاء الممولين.
        if int(campaign["user_id"]) != int(uid):
            with db() as c:
                c.execute("INSERT OR IGNORE INTO funding_member_claims(order_id,user_id,created) VALUES(?,?,?)",
                          (campaign["id"], uid, datetime.now(timezone.utc).isoformat()))
                count = c.execute("SELECT COUNT(*) AS n FROM funding_member_claims WHERE order_id=?", (campaign["id"],)).fetchone()["n"]
                c.execute("UPDATE channel_funding_orders SET completed_count=? WHERE id=? AND status='active'", (count, campaign["id"]))
                if int(count) >= int(campaign["quantity"]):
                    c.execute("UPDATE channel_funding_orders SET status='completed', completed_count=? WHERE id=? AND status='active'", (campaign["quantity"], campaign["id"]))

    return True


def has_paid_access(uid):
    with db() as c:
        return c.execute("SELECT 1 FROM paid_access WHERE user_id=?", (uid,)).fetchone() is not None


async def subscription_gate(update, context):
    user = update.effective_user

    channel_ok = await subscribed_to_required_channels(context.bot, user.id)
    paid_required = get_setting("paid_gate_enabled", "0") == "1"
    paid_ok = (not paid_required) or has_paid_access(user.id)
    if channel_ok and paid_ok:
        return True

    with db() as c:
        channels = c.execute("SELECT * FROM forced_channels WHERE enabled=1").fetchall()
        funded_channels = c.execute("""SELECT chat_id, channel_username, title FROM channel_funding_orders
            WHERE funding_type='mandatory' AND status='active' ORDER BY id""").fetchall()

    rows = []
    seen_targets = set()
    for channel in channels:
        target = str(channel["chat_id"] or "").strip()
        # Numeric private chat IDs (for example -100...) are not valid t.me usernames.
        if target.startswith(("https://", "http://")):
            url = target
        elif target.startswith("@") or (target and not target.lstrip("-").isdigit()):
            url = "https://t.me/" + target.lstrip("@")
        elif target == REQUIRED_CHANNEL or target == REQUIRED_CHANNEL.lstrip("@"):
            url = REQUIRED_CHANNEL_URL
        else:
            url = None
        if target not in seen_targets and url:
            rows.append([InlineKeyboardButton("📢 " + (channel["title"] or target), url=url)])
            seen_targets.add(target)
    for channel in funded_channels:
        target = (channel["channel_username"] or channel["chat_id"] or "").strip()
        if not target:
            continue
        url = target if target.startswith("https://") else ("https://t.me/" + target.lstrip("@"))
        if target not in seen_targets:
            rows.append([InlineKeyboardButton("📣 " + (channel["title"] or target), url=url)])
            seen_targets.add(target)

    if paid_required and not has_paid_access(user.id):
        price = max(1, int(get_setting("paid_gate_stars", "10")))
        rows.append([btn(f"⭐ فتح البوت مقابل {price} نجمة", "access_pay")])
    rows.append([btn("✅ تحقّق من الاشتراك", "check_subscription")])

    message = get_setting(
        "force_subscription_text",
        "🔒 يجب الاشتراك بالقنوات المطلوبة أولاً، ثم الضغط على «تحقّق من الاشتراك».\n\n"
        "إذا كنت مشتركاً وما زالت الرسالة تظهر، فقد يكون البوت غير مشرف في القناة أو أن معرّف القناة غير صحيح."
    )

    if update.callback_query:
        await update.callback_query.message.reply_text(
            message, reply_markup=kb(rows)
        )
    else:
        await update.effective_message.reply_text(
            message, reply_markup=kb(rows)
        )

    return False


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.effective_message:
        return
    referrer = 0

    if context.args:
        try:
            value = context.args[0]
            if value.startswith("ref_"):
                referrer = int(value[4:])
        except ValueError:
            referrer = 0

    with db() as c:
        user_was_new = c.execute(
            "SELECT 1 FROM users WHERE user_id=?", (user.id,)
        ).fetchone() is None
    register_user(user, referrer)

    # Separate notification for each genuinely new bot user.
    if user_was_new:
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=("👤 دخل مستخدم جديد إلى البوت\n"
                      f"الاسم: {user.full_name or 'بدون اسم'}\n"
                      f"المعرّف: {user.id}\n"
                      f"اسم المستخدم: @{user.username}" if user.username else
                      f"👤 دخل مستخدم جديد إلى البوت\nالاسم: {user.full_name or 'بدون اسم'}\nالمعرّف: {user.id}\nاسم المستخدم: غير محدد")
            )
        except TelegramError:
            log.exception("Could not notify owner about new user %s", user.id)

    # Credit an invite exactly once, only when a genuinely new account opens
    # the bot through a valid ref_<telegram_id> deep link.
    referral_credited = False
    with db() as c:
        if user_was_new and referrer and referrer != user.id:
            inviter_exists = c.execute(
                "SELECT 1 FROM users WHERE user_id=?", (referrer,)
            ).fetchone()
            if inviter_exists:
                try:
                    reward = max(0, int(get_setting("default_referral_reward", "25")))
                except (TypeError, ValueError):
                    reward = 25
                cur = c.execute("""
                    INSERT OR IGNORE INTO referrals(user_id,referrer_id,reward,created)
                    VALUES(?,?,?,?)
                """, (user.id, referrer, reward, datetime.now(timezone.utc).isoformat()))
                if cur.rowcount == 1:
                    c.execute("UPDATE users SET points=points+? WHERE user_id=?", (reward, referrer))
                    c.execute("UPDATE users SET points=points+? WHERE user_id=?", (reward, user.id))
                    referral_credited = True

    if referral_credited:
        try:
            await context.bot.send_message(
                chat_id=referrer,
                text=f"🎉 انضم شخص جديد عبر رابط دعوتك!\nتمت إضافة {reward} نقطة إلى رصيدك."
            )
        except TelegramError:
            log.info("Could not send referral reward notice to inviter %s", referrer)
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"🎁 أهلاً بك! حصلت على {reward} نقطة مكافأةً لانضمامك عبر رابط الدعوة."
            )
        except TelegramError:
            pass

    if not await subscription_gate(update, context):
        return

    if get_setting("maintenance", "0") == "1" and not is_admin(user.id):
        await update.effective_message.reply_text("🛠 المتجر تحت الصيانة.")
        return

    with db() as c:
        total = c.execute(
            "SELECT COUNT(*) n FROM orders WHERE status='completed'"
        ).fetchone()["n"]

    # Display the editable welcome card above the buttons; no legacy banner.
    # Replace a previously saved legacy welcome caption, while preserving any
    # genuinely customized caption entered by the admin.
    saved_welcome = ui_message("welcome")
    # Replace known old/default captions that may still be stored in the DB.
    # The database value takes precedence over the source default, so update
    # older captions here instead of letting them restore the previous welcome.
    if saved_welcome.strip() in {
        "أهلاً بك في متجر الخدمات الرقمية 🚀",
        "✨ أهلاً بك في متجر محمود للخدمات الرقمية ✨",
    } or "طلباتي" in saved_welcome or "TAlABATI" in saved_welcome:
        saved_welcome = UI_MESSAGES["welcome"][0]
    import re
    welcome_values = {
        "id": user.id,
        "user_id": user.id,
        "username": ("@" + user.username) if user.username else "غير محدد",
        "first_name": user.first_name or user.full_name or "صديقي",
        "points": balance(user.id),
        "count": total,
    }
    # Support both {id}/{points} and plain id/points in saved admin templates.
    welcome_text = re.sub(
        r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}",
        lambda match: str(welcome_values.get(match.group(1), match.group(0))),
        saved_welcome,
    )
    welcome_text = re.sub(
        r"(?i)(?<![\w@])id(?![\w])",
        str(welcome_values["id"]),
        welcome_text,
    )
    welcome_text = re.sub(
        r"(?i)(?<![\w@])points(?![\w])",
        str(welcome_values["points"]),
        welcome_text,
    )
    await update.effective_message.reply_text(
        welcome_text,
        reply_markup=home_keyboard(user.id)
    )


# =========================================================
# USER SERVICES / ORDERS
# =========================================================

async def show_platforms(q):
    rows = []
    items = list(PLATFORMS.items())

    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i:i + 2]:
            row.append(btn(get_setting("platform_label_" + key, label), f"platform:{key}"))
        rows.append(row)

    rows.append([btn("🔙 الرئيسية", "home")])
    await safe_edit(q, 
        ui_message("services_intro"),
        reply_markup=kb(rows)
    )


async def show_platform_services(q, platform, section_id=None):
    aliases = {
        "instagram": ("instagram", "insta", "انستغرام", "انستجرام", "انستا"),
        "whatsapp": ("whatsapp", "واتساب", "واتس اب", "واتسآب"),
        "tiktok": ("tiktok", "tik tok", "تيك توك", "تيكتوك", "تيكطوك"),
        "telegram": ("telegram", "تيليجرام", "تلغرام", "تيليغرام"),
        "facebook": ("facebook", "فيسبوك", "فيس بوك", "fb "),
        "youtube": ("youtube", "يوتيوب"),
        "snapchat": ("snapchat", "سناب شات", "سناب"),
        "twitter": ("twitter", "تويتر"),
        "x": ("x.com", "منصة اكس", "إكس", "اكس"),
        "threads": ("threads", "ثريدز"),
        "twitch": ("twitch", "تويتش"),
        "discord": ("discord", "ديسكورد"),
        "spotify": ("spotify", "سبوتيفاي"),
        "website": ("website", "seo", "backlink", "مواقع", "سيو"),
        "crypto": ("crypto", "cryptocurrency", "bitcoin", "btc", "ethereum", "eth", "usdt", "binance", "blockchain", "عملة رقمية", "العملات الرقمية", "بيتكوين", "بتكوين", "ايثيريوم", "إيثيريوم", "بينانس", "كريبتو", "ترون", "tron"),
    }
    with db() as c:
        if section_id is not None:
            all_services = c.execute("""
                SELECT id,name,category,platform,price_usd,price_points,min_qty,max_qty,section_id
                FROM services WHERE enabled=1 AND section_id=? ORDER BY name LIMIT 500
            """, (section_id,)).fetchall()
        else:
            if platform == "free":
                all_services = c.execute("""
                    SELECT id,name,category,platform,price_usd,price_points,min_qty,max_qty,section_id
                    FROM services WHERE enabled=1 AND platform='free'
                    ORDER BY name LIMIT 2000
                """).fetchall()
            else:
                all_services = c.execute("""
                    SELECT id,name,category,platform,price_usd,price_points,min_qty,max_qty,section_id
                    FROM services WHERE enabled=1 AND (platform=? OR platform='other')
                    ORDER BY name LIMIT 2000
                """, (platform,)).fetchall()

    services = []
    terms = aliases.get(platform, (platform.casefold(),))
    for service in all_services:
        if section_id is not None and service["section_id"] != section_id:
            continue
        name = str(service["name"] or "")
        category = str(service["category"] or "")
        detected = detect_platform({"name": name, "category": category})
        text = f"{name} {category}".casefold()
        matches_alias = any(term.casefold() in text for term in terms)
        if (platform == "free" and service["platform"] == "free") or (platform != "free" and (service["platform"] == platform or detected == platform or matches_alias)):
            services.append(service)
    # Keep button payloads small and display a manageable page.
    services = services[:80]
    rows = []
    mode = get_setting("currency_mode", "points")
    for service in services:
        price = (f"${service['price_usd']:.4f}/1000" if mode == "usd"
                 else f"{service['price_points']} نقطة/1000")
        rows.append([btn(f"{service['name'][:32]} | {price}", f"service:{service['id']}")])
    rows.append([btn("🔙 التطبيقات", "services")])
    if section_id is not None:
        with db() as c:
            sec = c.execute("SELECT name FROM service_sections WHERE id=? AND platform=?", (section_id, platform)).fetchone()
        section_label = sec["name"] if sec else "القسم"
        message = (f"{PLATFORMS.get(platform, platform)}\n📁 {section_label}\nاختر الخدمة:") if services else (
            f"📁 {section_label}\nلا توجد خدمات مضافة لهذا القسم بعد."
        )
        rows.append([btn("🔙 أقسام التطبيق", f"platform:{platform}")])
    else:
        message = (f"{PLATFORMS.get(platform, platform)}\nاختر الخدمة:") if services else (
            f"{PLATFORMS.get(platform, platform)}\nلا توجد خدمات مطابقة لهذا التطبيق حالياً. "
            "من لوحة التحكم أضف خدمات أو اختر خدمة من المزود."
        )
    await safe_edit(q, message, reply_markup=kb(rows))


def ensure_manual_provider():
    with db() as c:
        row = c.execute("SELECT id FROM providers WHERE api_url='manual://local' LIMIT 1").fetchone()
        if row:
            return int(row['id'])
        cur = c.execute("INSERT INTO providers(name,api_url,api_key,enabled,owner_id,created) VALUES(?,?,?,?,?,?)", ("الخدمات اليدوية", "manual://local", "", 1, OWNER_ID, datetime.now(timezone.utc).isoformat()))
        return int(cur.lastrowid)


async def publish_order_to_channel(context, order_id, uid, service_name, link, quantity, points_cost, status_text="قيد المراجعة"):
    """Publish customer-confirmed orders to the configured orders channel."""
    target = get_setting("orders_channel", "").strip()
    if not target:
        return
    try:
        await context.bot.send_message(
            chat_id=target,
            text=(
                "🧾 طلب جديد مؤكد\n\n"
                f"🆔 رقم الطلب: #{order_id}\n"
                f"🛍 الخدمة: {service_name}\n"
                f"📦 الكمية: {quantity}\n"
                f"🔗 الرابط: {link}\n"
                f"💎 التكلفة: {points_cost} نقطة\n"
                f"📌 الحالة: {status_text}\n"
                "✨ شكراً لثقتكم بمتجرنا."
            )
        )
    except TelegramError:
        log.exception("Could not publish order %s to orders channel", order_id)


async def create_order_request(update, context, service_id, link, quantity):
    uid = update.effective_user.id
    service = None

    with db() as c:
        service = c.execute("""
        SELECT s.*,p.api_url,p.api_key,p.enabled AS provider_enabled
        FROM services s JOIN providers p ON p.id=s.provider_id
        WHERE s.id=? AND s.enabled=1 AND (p.enabled=1 OR s.delivery_mode='manual')
        """, (service_id,)).fetchone()

    if not service:
        raise RuntimeError("الخدمة أو المزود غير متاح")

    if not service["min_qty"] <= quantity <= service["max_qty"]:
        raise RuntimeError(
            f"الكمية يجب أن تكون بين {service['min_qty']} و{service['max_qty']}"
        )

    cost_usd = round(quantity * float(service["price_usd"]) / 1000, 6)
    points_cost = int(math.ceil(
        quantity * int(service["price_points"]) / 1000
    ))

    # A zero-rate service imported from the provider is genuinely free.
    # Paid services must still have a valid positive price in both currencies.
    mode = get_setting("currency_mode", "points")
    free_service = (
        float(service["provider_rate"] or 0) == 0.0
        and float(service["price_usd"] or 0) == 0.0
        and int(service["price_points"] or 0) == 0
    )
    if not math.isfinite(cost_usd) or (cost_usd <= 0 and not free_service):
        raise RuntimeError(
            "سعر الخدمة غير مضبوط عند المزود. اطلب من المشرف جلب الخدمات وإعادة حساب الأسعار."
        )
    if mode == "usd" and not free_service:
        # USD is a display mode only; paid orders still deduct equivalent points.
        points_per_usd = max(0.000001, float(get_setting("points_per_usd", "1000")))
        points_cost = int(math.ceil(cost_usd * points_per_usd))
    if points_cost <= 0 and not free_service:
        raise RuntimeError(
            "سعر الخدمة بالنقاط يساوي صفراً. اطلب من المشرف إعادة حساب الأسعار."
        )

    with db() as c:
        if points_cost:
            cur = c.execute("""
            UPDATE users SET points=points-?
            WHERE user_id=? AND points>=?
            """, (points_cost, uid, points_cost))
            if cur.rowcount != 1:
                raise RuntimeError("رصيدك من النقاط غير كافٍ")

        cur = c.execute("""
        INSERT INTO orders(
            user_id,service_id,link,quantity,cost_points,cost_usd,status,created
        ) VALUES(?,?,?,?,?,?,'processing',?)
        """, (
            uid, service_id, link, quantity, points_cost, cost_usd,
            datetime.now(timezone.utc).isoformat()
        ))
        order_id = cur.lastrowid

    if service["delivery_mode"] == "manual" or str(service["api_url"] or "").startswith("manual://"):
        with db() as c:
            c.execute("UPDATE orders SET status='manual_pending' WHERE id=?", (order_id,))
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"🧾 طلب جديد يحتاج مراجعة الإدارة #{order_id}\n"
                    f"👤 المستخدم: {uid}\n🛍 الخدمة: {service['name']}\n"
                    f"🔗 الرابط: {link}\n📦 الكمية: {quantity}\n"
                    f"💎 التكلفة: {points_cost} نقطة | 💵 ${cost_usd:.6f}\n"
                    f"📝 التعليمات: {service['manual_instruction'] or 'نفّذ الطلب ثم اختر مكتمل، أو ألغِه لإعادة الرصيد.'}"
                ),
                reply_markup=kb([[btn("✅ وضع مكتمل", f"ordcomplete:{order_id}", "success"), btn("❌ إلغاء وإرجاع الرصيد", f"ordcancel:{order_id}", "danger")]])
            )
        except TelegramError:
            log.exception("Could not notify owner about manual order %s", order_id)
        await publish_order_to_channel(context, order_id, uid, service["name"], link, quantity, points_cost, "قيد مراجعة الإدارة")
        with db() as c:
            balance_row = c.execute("SELECT points FROM users WHERE user_id=?", (uid,)).fetchone()
        return render_template("order_manual_pending", order_id=order_id, cost=points_cost, points=int(balance_row["points"] or 0) if balance_row else 0, user_id=uid, username=update.effective_user.username or "", first_name=update.effective_user.first_name or "", service_name=service["name"], quantity=quantity, link=link)

    provider = get_provider(service["provider_id"])

    try:
        result = await api_call(provider, "add", {
            "service": service["external_id"],
            "link": link,
            "quantity": quantity,
        })

        if not isinstance(result, dict) or not result.get("order"):
            raise RuntimeError("المزود لم يؤكد الطلب")

        provider_order_id = str(result["order"])

        with db() as c:
            c.execute("""
            UPDATE orders SET status='submitted',provider_order_id=?
            WHERE id=?
            """, (provider_order_id, order_id))

        # Send a branded order receipt to the owner for every accepted provider order.
        admin_text = (
            "🧾━━━━━━━━ طلب جديد ━━━━━━━━🧾\n"
            "🟡 الحالة الإدارية: قيد المتابعة (قبله المزود مبدئياً)\n"
            f"🆔 رقم الطلب: #{order_id}\n"
            f"👤 المستخدم: {uid} (@{update.effective_user.username or 'بدون_معرّف'})\n"
            f"🛍 الخدمة: {service['name']}\n🔗 الرابط: {link}\n📦 الكمية: {quantity}\n"
            f"📨 رقم طلب المزود: {provider_order_id}\n"
            f"💎 التكلفة: {points_cost} نقطة | 💵 ${cost_usd:.6f}\n"
            "🧾━━━━━━━━━━━━━━━━━━━━🧾"
        )
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=admin_text)
        except TelegramError:
            log.exception("Failed to notify owner about order %s", order_id)

        await publish_order_to_channel(context, order_id, uid, service["name"], link, quantity, points_cost, "قيد التنفيذ لدى المزود")
        with db() as c:
            balance_row = c.execute("SELECT points FROM users WHERE user_id=?", (uid,)).fetchone()
        return render_template("order_pending", order_id=order_id, cost=points_cost, points=int(balance_row["points"] or 0) if balance_row else 0, user_id=uid, username=update.effective_user.username or "", first_name=update.effective_user.first_name or "", service_name=service["name"], quantity=quantity, link=link)

    except Exception as exc:
        log.exception("Order submission failed")

        # A timeout/API error is NOT proof that the website rejected the order.
        # Keep the order open and funds reserved until its real state is confirmed.
        with db() as c:
            c.execute("UPDATE orders SET status='submission_unknown' WHERE id=? AND status NOT IN ('rejected','completed','cancelled')", (order_id,))

        admin_text = (
            "⚠️━━━━━━━━ تعذّر تأكيد حالة الطلب ━━━━━━━━⚠️\n"
            "الحالة: غير مؤكدة — لم يتم رفض الطلب ولم تُرجع النقاط تلقائياً.\n"
            f"🆔 رقم الطلب: #{order_id}\n"
            f"👤 المستخدم: {uid}\n🛍 الخدمة: {service['name']}\n"
            f"🔗 الرابط: {link}\n📦 الكمية: {quantity}\n"
            f"⚠️ تفاصيل الاتصال (للإدارة فقط): {str(exc)[:500]}\n"
            "تحقق من الموقع قبل اتخاذ أي إجراء."
        )
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=admin_text)
        except TelegramError:
            log.exception("Failed to notify owner about rejected order %s", order_id)

        await publish_order_to_channel(context, order_id, uid, service["name"], link, quantity, points_cost, "قيد التحقق من الموقع")
        with db() as c:
            balance_row = c.execute("SELECT points FROM users WHERE user_id=?", (uid,)).fetchone()
        return render_template("order_submission_check", order_id=order_id, user_id=uid, service_name=service["name"], quantity=quantity, cost=points_cost, points=int(balance_row["points"] or 0) if balance_row else 0, link=link)


# =========================================================
# CALLBACK ROUTER
# =========================================================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    register_user(q.from_user)
    data = q.data or ""

    # Channel subscription is mandatory for every account, including admins.
    if data != "check_subscription" and not await subscription_gate(update, context):
        return

    if data == "home":
        context.user_data.clear()
        await safe_edit(q, 
            get_setting("shop_name"),
            reply_markup=home_keyboard(uid)
        )

    elif data == "check_subscription":
        if not await subscribed_to_required_channels(context.bot, uid):
            await safe_edit(q,
                "❌ لم يتم تأكيد اشتراكك في إحدى القنوات المطلوبة.\n\n"
                "1) افتح كل قناة من الأزرار واشترك بها.\n"
                "2) ارجع واضغط «تحقّق مرة أخرى».\n\n"
                "إذا كنت مشتركاً بالفعل، يجب أن يكون البوت مشرفاً في القناة وأن يكون معرّف القناة مضبوطاً بشكل صحيح.",
                reply_markup=kb([
                    [InlineKeyboardButton("📢 الاشتراك بقناة محمود", url=REQUIRED_CHANNEL_URL)],
                    [btn("✅ تحقّق مرة أخرى", "check_subscription")],
                    [btn("🔙 رجوع", "home")]
                ])
            )
        elif get_setting("paid_gate_enabled", "0") == "1" and not has_paid_access(uid):
            await subscription_gate(update, context)
        else:
            await safe_edit(q, 
                "✅ تم التحقق بنجاح.",
                reply_markup=home_keyboard(uid)
            )

    elif data == "services":
        if not await subscription_gate(update, context):
            return
        await show_platforms(q)

    elif data == "fund_channels":
        context.user_data.clear()
        fund_text = (
            "💰 تمويل قناتك - اختر الطريقة المناسبة\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ تمويل الاشتراك الإجباري:\n"
            "   • قناتك تظهر للمستخدمين كاشتراك إجباري\n"
            "   • نتائج فورية وسريعة جداً ⚡\n"
            "   • سعر العضو أعلى 💎\n\n"
            "🐢 تمويل بطيء (الانضمام للقنوات):\n"
            "   • قناتك تظهر في قائمة الانضمام للقنوات\n"
            "   • نتائج تدريجية ومستمرة 📈\n"
            "   • سعر العضو أقل 💰\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "اختر الخيار المناسب لك:"
        )
        await safe_edit(q, fund_text, reply_markup=kb([
            [btn("⚡ تمويل الاشتراك الإجباري", "fund_type:mandatory")],
            [btn("🐢 تمويل بطيء", "fund_type:slow")],
            [btn("📜 سجل التمويل", "fund_history")],
            [btn("🔙 رجوع", "home")]
        ]))

    elif data.startswith("fund_type:"):
        mode = data.split(":", 1)[1]
        if mode not in ("mandatory", "slow"):
            await safe_edit(q, "طريقة التمويل غير معروفة.", reply_markup=kb([[btn("🔙 رجوع", "fund_channels")]]))
            return
        context.user_data.clear()
        context.user_data["funding_type"] = mode
        mode_name = "تمويل الاشتراك الإجباري" if mode == "mandatory" else "تمويل بطيء (الانضمام للقنوات)"
        rules = (
            "🔔 قوانين تمويل قناتك\n\n"
            "• القناة/المجموعة عامة طوال التمويل (لديها @username).\n"
            "• يُمنع المحتوى المخالف (لا أخلاقي/إجرامي) أو الاحتيال.\n"
            "• لا تغيّر اسم المستخدم أثناء التمويل.\n"
            "• الانضمام مفتوح — بدون موافقة يدوية.\n"
            "• لا تُزل البوت من قائمة المدراء.\n\n"
            "⚠️ مخالفة القوانين = إلغاء التمويل مع استرجاع المتبقي فقط\n\n"
            f"طريقة التمويل المختارة: {mode_name}\n\nاختر:"
        )
        await safe_edit(q, rules, reply_markup=kb([
            [btn("➕ إضافة قناة", "fund_add")],
            [btn("📜 سجل التمويل", "fund_history")],
            [btn("🔙 رجوع", "fund_channels")]
        ]))

    elif data == "fund_add":
        if context.user_data.get("funding_type") not in ("mandatory", "slow"):
            await safe_edit(q, "اختر طريقة التمويل أولاً.", reply_markup=kb([[btn("🔙 رجوع", "fund_channels")]]))
            return
        context.user_data["state"] = "fund_quantity"
        context.user_data.pop("fund_chat_id", None)
        context.user_data.pop("fund_channel_title", None)
        await safe_edit(q,
            f"👥 كل 1 عضو 👤 مقابل {int(get_setting('channel_member_price', '15') or 15)} نقطة.\n"
            f"📣 الحد الأدنى للكمية: {int(get_setting('channel_funding_min_qty', '20') or 20)}\n\n"
            "👤 أرسل الكمية:",
            reply_markup=kb([[btn("❌ إلغاء", "fund_cancel")]])
        )

    elif data == "fund_cancel":
        context.user_data.clear()
        await safe_edit(q, "تم إلغاء طلب التمويل.", reply_markup=kb([[btn("🔙 رجوع", "fund_channels")]]))

    elif data == "fund_history":
        with db() as c:
            rows = c.execute("SELECT id,title,funding_type,quantity,total_cost,status,created FROM channel_funding_orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        if not rows:
            history_text = "📜 سجل التمويل\n\nلا توجد لديك طلبات تمويل حتى الآن."
        else:
            lines = ["📜 سجل التمويل — آخر 10 طلبات\n"]
            for row in rows:
                typ = "الاشتراك الإجباري" if row["funding_type"] == "mandatory" else "التمويل البطيء"
                lines.append(f"#{row['id']} | {typ}\n📣 {row['title']}\n👥 الكمية: {row['quantity']} | 💰 الإجمالي: {row['total_cost']} نقطة\nالحالة: {row['status']}\n")
            history_text = "\n".join(lines)
        await safe_edit(q, history_text, reply_markup=kb([[btn("➕ طلب تمويل جديد", "fund_channels")], [btn("🔙 رجوع", "fund_channels")]]))

    elif data == "fund_confirm":
        pending = context.user_data.get("funding_review")
        if not pending:
            await safe_edit(q, "انتهت بيانات الطلب. ابدأ طلب تمويل جديد.", reply_markup=kb([[btn("📣 تمويل قناتك", "fund_channels")]]))
            return
        total = int(pending["total_cost"])
        order_id = None
        with db() as c:
            cur = c.execute("UPDATE users SET points=points-? WHERE user_id=? AND points>=?", (total, uid, total))
            if cur.rowcount != 1:
                current = c.execute("SELECT points FROM users WHERE user_id=?", (uid,)).fetchone()
                available = int(current["points"]) if current else 0
                await safe_edit(q, f"❌ رصيدك غير كافٍ.\n💎 رصيدك الحالي: {available} نقطة\n💰 المطلوب: {total} نقطة", reply_markup=kb([[btn("❌ إلغاء", "fund_cancel")], [btn("🔙 رجوع", "fund_channels")]]))
                return
            cur = c.execute("INSERT INTO channel_funding_orders(user_id,chat_id,channel_username,title,funding_type,quantity,price_per_member,total_cost,status,created) VALUES(?,?,?,?,?,?,?,?, 'active', ?)", (
                uid, pending["chat_id"], pending.get("username", ""), pending["title"], pending["funding_type"], pending["quantity"], pending["price_per_member"], total, datetime.now(timezone.utc).isoformat()
            ))
            order_id = cur.lastrowid
            if pending["funding_type"] == "slow":
                reward = max(0, int(get_setting("channel_join_reward", "10") or 10))
                c.execute("""INSERT INTO channel_tasks(chat_id,title,reward,enabled,owner_id,member_price,funding_order_id,target_quantity,completed_count)
                    VALUES(?,?,?,1,?,?,?, ?,0)""", (
                    pending["chat_id"], pending["title"], reward, uid, pending["price_per_member"], order_id, pending["quantity"]
                ))
            new_balance_row = c.execute("SELECT points FROM users WHERE user_id=?", (uid,)).fetchone()
            new_balance = int(new_balance_row["points"]) if new_balance_row else 0
        mode_name = "الاشتراك الإجباري" if pending["funding_type"] == "mandatory" else "التمويل البطيء"
        success = (f"✅ تم إنشاء طلب التمويل #{order_id} بنجاح.\n"
                   f"📣 القناة: {pending.get('username') or pending['title']}\n"
                   f"👥 الكمية: {pending['quantity']}\n"
                   f"💰 السعر/عضو: {pending['price_per_member']}\n"
                   f"📦 الإجمالي: {total} نقطة\n"
                   f"💎 نقاطك المتبقية: {new_balance}\n"
                   f"⚡ الطريقة: {mode_name}\n"
                   f"📈 المنجز: 0/{pending['quantity']}\n\n"
                   "🚀 بدأ التمويل تلقائياً. سيتوقف عند اكتمال العدد المحدد.")
        context.user_data.clear()
        await safe_edit(q, success, reply_markup=kb([[btn("📜 سجل التمويل", "fund_history")], [btn("🏠 القائمة الرئيسية", "home")]]))
        orders_channel = get_setting("orders_channel", "").strip()
        if orders_channel:
            try:
                target = int(orders_channel) if orders_channel.lstrip("-").isdigit() else orders_channel
                await context.bot.send_message(chat_id=target, text=(
                    f"💰 طلب تمويل قناة جديد #{order_id}\n"
                    f"👤 صاحب الطلب: {uid} (@{q.from_user.username or 'بدون'})\n"
                    f"📣 القناة: {pending.get('username') or pending['title']}\n"
                    f"🆔 معرف القناة: {pending['chat_id']}\n"
                    f"⚙️ الطريقة: {mode_name}\n"
                    f"👥 الكمية: {pending['quantity']}\n"
                    f"💰 السعر/عضو: {pending['price_per_member']} نقطة\n"
                    f"📦 الإجمالي المدفوع: {total} نقطة\n"
                    f"📌 الحالة: بدأ التمويل تلقائياً\n📈 المنجز: 0/{pending['quantity']}"
                ))
            except TelegramError:
                log.exception("Failed to send channel funding order to orders channel")

    elif data == "api_info":
        await safe_edit(q,
            "✉️ أهلاً بك في قسم API + التحديثات\n\n"
            "موقع لوحة خدماتك: https://kkkksoa.smmpanel.cloud\n"
            "يمكن ربط الموقع كمزود بعد إدخال رابط API الرسمي ومفتاح API من إعدادات المزودين. رابط الموقع وحده لا يكفي لإرسال الطلبات؛ لا تشارك مفتاح API في المحادثات العامة.\n\n"
            "اختر أحد الخيارات بالأسفل:",
            reply_markup=kb([
                [btn("🔑 إنشاء مفتاح API", "api_key", "success"), btn("⭐ شحن رصيد API", "api_topup", "success")],
                [btn("⚙️ واجهة برمجة API", "api_docs", "success")],
                [btn("🔗 طلب مساعدة بالربط", "api_link_request", "primary")],
                [btn("🦾 تحديثات البوت", "bot_updates", "success")],
                [btn("🔙 رجوع", "home", "danger")],
            ])
        )

    elif data == "api_docs":
        await safe_edit(q, "📚 توثيق API\n\nالرابط: " + api_url_display() + "\nالمصادقة: Authorization: Bearer YOUR_API_KEY\n\nPOST إلى /api/v2 (أو /api/v1) مع action: services أو balance أو add أو status.\nمثال خدمات: {\"action\":\"services\"}\nمثال طلب: {\"action\":\"add\",\"service\":123,\"link\":\"https://example.com/user\",\"quantity\":100,\"client_order_id\":\"order-001\"}\nمثال حالة: {\"action\":\"status\",\"order\":1}\n\n⚠️ رابط API لا يعمل للزبائن من خارج الهاتف قبل ضبط API_PUBLIC_URL على رابط HTTPS عام حقيقي (نفق آمن). لا تستخدم localhost أو 127.0.0.1. يدعم الخادم طلبات JSON وطلبات SMM التقليدية بنموذج key/action.", reply_markup=kb([[btn("🔑 حساب API", "api_key")],[btn("⭐ شحن رصيد API", "api_topup")],[btn("🔙 رجوع", "api_info")]]))

    elif data == "api_key":
        with db() as c:
            row = c.execute("SELECT token_prefix,balance,active FROM api_clients WHERE user_id=?", (uid,)).fetchone()
        if row:
            await safe_edit(q, f"🔑 حساب API موجود\nالمفتاح: {row['token_prefix']}•••••• (المفتاح الكامل لا يُخزّن ولا يمكن عرضه مجدداً)\n💰 الرصيد: {row['balance']}\nالحالة: {'فعال' if row['active'] else 'موقوف'}\n\nإذا فقدت المفتاح اضغط إنشاء جديد.", reply_markup=kb([[btn("⭐ شحن الرصيد", "api_topup")],[btn("🔄 إنشاء/تجديد مفتاح API", "api_rotate")],[btn("🔙 رجوع", "api_info")]]))
        else:
            token = "smmp_" + secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc).isoformat()
            with db() as c:
                c.execute("INSERT INTO api_clients(user_id,token_hash,token_prefix,balance,active,created,updated) VALUES(?,?,?,?,1,?,?)", (uid, hashlib.sha256(token.encode()).hexdigest(), token[:12], 0, now, now))
                c.execute("INSERT OR IGNORE INTO api_ledger(user_id,amount,kind,reference,details,created) VALUES(?,0,'created',?,?,?)", (uid, f"api-create-{uid}", "API key created", now))
            await safe_edit(q, "✅ تم إنشاء مفتاح API. انسخه الآن واحفظه في مكان آمن؛ لن يظهر كاملاً مرة أخرى.\n\n<code>"+token+"</code>\n\n⚠️ لا تشاركه ولا تضعه في كود عام.\nرابط API: "+api_url_display(), reply_markup=kb([[btn("⭐ شحن رصيد API", "api_topup")],[btn("📚 التوثيق", "api_docs")],[btn("🔙 رجوع", "api_info")]]), parse_mode="HTML")
            try:
                await context.bot.send_message(OWNER_ID, f"🔔 عملية API جديدة\n\n🔑 تم إنشاء مفتاح API\n👤 المستخدم: {uid} (@{q.from_user.username or 'بدون'})\n🔎 بادئة المفتاح: {token[:12]}\n💰 الرصيد الابتدائي: 0\n⚠️ لم يتم إرسال المفتاح الكامل للإدارة حفاظاً على الأمان.")
            except TelegramError:
                log.warning("Could not notify owner about API key creation for user %s", uid)

    elif data == "api_rotate":
        token = "smmp_" + secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        with db() as c:
            row = c.execute("SELECT user_id FROM api_clients WHERE user_id=?", (uid,)).fetchone()
            if row:
                c.execute("UPDATE api_clients SET token_hash=?,token_prefix=?,active=1,updated=? WHERE user_id=?", (hashlib.sha256(token.encode()).hexdigest(), token[:12], now, uid))
            else:
                c.execute("INSERT INTO api_clients(user_id,token_hash,token_prefix,balance,active,created,updated) VALUES(?,?,?,0,1,?,?)", (uid, hashlib.sha256(token.encode()).hexdigest(), token[:12], now, now))
        with db() as c:
            c.execute("INSERT OR IGNORE INTO api_ledger(user_id,amount,kind,reference,details,created) VALUES(?,0,'rotated',?,?,?)", (uid, f"api-rotate-{uid}-{int(time.time())}", "API key rotated; previous key revoked", now))
        await safe_edit(q, "🔐 تم تدوير المفتاح؛ المفتاح القديم لم يعد صالحاً. احفظ المفتاح الجديد الآن:\n\n<code>"+token+"</code>\n\nرابط API: "+api_url_display(), reply_markup=kb([[btn("⭐ شحن رصيد API", "api_topup")],[btn("🔙 رجوع", "api_info")]]), parse_mode="HTML")
        try:
            await context.bot.send_message(OWNER_ID, f"🔔 عملية API جديدة\n\n🔄 تم تجديد مفتاح API وإبطال المفتاح السابق\n👤 المستخدم: {uid} (@{q.from_user.username or 'بدون'})\n🔎 بادئة المفتاح الجديد: {token[:12]}")
        except TelegramError:
            log.warning("Could not notify owner about API key rotation for user %s", uid)

    elif data == "api_topup":
        packages = api_stars_packages()
        rows = []
        for i in range(0, len(packages), 2):
            pair = packages[i:i+2]
            rows.append([btn(f"⭐ {n} نجمة" if n == 1 else f"⭐ {n} نجوم", f"api_pay:{n}") for n in pair])
        rows.append([btn("🔙 رجوع", "api_info")])
        await safe_edit(q, "⭐ اختر عدد نجوم تيليجرام لشحن رصيد API. يضاف الرصيد بعد تأكيد دفع Telegram فقط.", reply_markup=kb(rows))

    elif data == "api_stars_admin" and is_admin(uid):
        await safe_edit(q, f"⭐ إعدادات شحن API بالنجوم\n\nالباقات الحالية: {', '.join(map(str, api_stars_packages()))}\nكل نجمة = {get_setting('api_stars_rate', '1')} رصيد API.\n\nاختر ما تريد تعديله:", reply_markup=kb([[btn("🧮 تعديل الرصيد لكل نجمة", "api_stars_rate_edit")],[btn("📦 تعديل باقات النجوم", "api_stars_packages_edit")],[btn("🔙 لوحة الإدارة", "admin")]]))

    elif data == "api_stars_rate_edit" and is_admin(uid):
        context.user_data["state"] = "api_stars_rate_edit"
        await safe_edit(q, "أرسل عدد وحدات رصيد API التي تُضاف مقابل كل نجمة (عدد صحيح من 1 إلى 100000).\nمثال: 5\nأرسل إلغاء للرجوع.")

    elif data == "api_stars_packages_edit" and is_admin(uid):
        context.user_data["state"] = "api_stars_packages_edit"
        await safe_edit(q, "أرسل باقات النجوم مفصولة بفواصل، مثال:\n100,500,1000,5000,10000,50000,100000\nالمسموح أعداد صحيحة من 100 إلى 100000، حتى 20 باقة مختلفة. أرسل إلغاء للإلغاء.")

    elif data.startswith("api_pay:"):
        try:
            stars = int(data.split(":",1)[1])
        except ValueError:
            return
        if stars not in api_stars_packages(): return
        with db() as c:
            exists = c.execute("SELECT 1 FROM api_clients WHERE user_id=? AND active=1", (uid,)).fetchone()
        if not exists:
            await safe_edit(q, "أنشئ مفتاح API أولاً.", reply_markup=kb([[btn("🔑 إنشاء مفتاح API", "api_key")]])); return
        await context.bot.send_invoice(chat_id=uid, title=f"شحن رصيد API ({stars} نجوم)", description="إضافة رصيد إلى حساب API الخاص بك", payload=f"api:{uid}:{stars}", provider_token="", currency="XTR", prices=[LabeledPrice("رصيد API", stars)])

    elif data == "api_link_request":
        context.user_data["state"] = "api_link_request_details"
        await safe_edit(q,
            "🔗 طلب ربط موقع أو بوت عبر API\n\nأرسل الآن رابط موقعك أو @اسم البوت ووصفاً مختصراً لما تريد ربطه. سيظهر الطلب للإدارة للمراجعة، ولا ترسل توكن البوت أو كلمات المرور.\n\n"
            f"💳 السعر المحدد: {get_setting('api_link_price', '0')}",
            reply_markup=kb([[btn("❌ إلغاء", "api_info")]])
        )

    elif data == "bot_updates":
        updates_text = get_setting("bot_updates_text", "لا توجد تحديثات جديدة معلنة حالياً.")
        await safe_edit(q,
            "🦾 تحديثات البوت\n\n" + updates_text,
            reply_markup=kb([[btn("🔙 رجوع إلى API", "api_info", "danger")]])
        )

    elif data == "terms":
        terms = ui_message("terms_text")
        await safe_edit(q, "⚠️ شروط الاستخدام\n\n" + terms,
                        reply_markup=kb([[btn("🔙 رجوع", "home")]]))

    elif data == "funding_requests" and is_admin(uid):
        with db() as c:
            requests = c.execute("SELECT * FROM channel_funding_requests WHERE status='pending' ORDER BY id DESC LIMIT 30").fetchall()
        rows = [[btn(f"📣 #{r['id']} {r['title'][:25]} (+{r['reward']})", f"fundreq:{r['id']}")] for r in requests]
        rows.append([btn("🔙 لوحة التحكم", "admin")])
        await safe_edit(q, "📣 طلبات تمويل القنوات قيد المراجعة:", reply_markup=kb(rows))

    elif data.startswith("fundreq:") and is_admin(uid):
        rid = int(data.split(":", 1)[1])
        with db() as c:
            req = c.execute("SELECT * FROM channel_funding_requests WHERE id=? AND status='pending'", (rid,)).fetchone()
        if not req:
            await safe_edit(q, "الطلب غير موجود أو تمت معالجته.", reply_markup=kb([[btn("🔙 رجوع", "funding_requests")]]))
            return
        await safe_edit(q, f"📣 طلب تمويل قناة #{rid}\nالقناة: {req['title']}\nالمعرف: {req['chat_id']}\nصاحب الطلب: {req['user_id']}\nمكافأة تجميع النقاط: {req['reward']} نقطة\n\nعند الموافقة ستظهر القناة ضمن مهام تجميع النقاط فقط.", reply_markup=kb([[btn("✅ موافقة وإضافة لمهام النقاط", f"fundapprove:{rid}")], [btn("❌ رفض الطلب", f"fundreject:{rid}")], [btn("🔙 رجوع", "funding_requests")]]))

    elif data.startswith("fundapprove:") and is_admin(uid):
        rid = int(data.split(":", 1)[1])
        with db() as c:
            req = c.execute("SELECT * FROM channel_funding_requests WHERE id=? AND status='pending'", (rid,)).fetchone()
            if not req:
                await safe_edit(q, "الطلب غير موجود أو تمت معالجته.", reply_markup=kb([[btn("🔙 رجوع", "funding_requests")]]))
                return
            c.execute("INSERT INTO channel_tasks(chat_id,title,reward,enabled) VALUES(?,?,?,1)", (req['chat_id'], req['title'], req['reward']))
            c.execute("UPDATE channel_funding_requests SET status='approved' WHERE id=?", (rid,))
        try:
            await context.bot.send_message(req['user_id'], f"✅ تمت الموافقة على طلب تمويل قناتك ({req['title']}) وإضافتها إلى مهام تجميع النقاط.")
        except TelegramError:
            pass
        await safe_edit(q, "✅ تمت الموافقة وإضافة القناة إلى مهام تجميع النقاط، ولم تتم إضافتها إلى الاشتراك الإجباري.", reply_markup=kb([[btn("📣 طلبات التمويل", "funding_requests")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data.startswith("fundreject:") and is_admin(uid):
        rid = int(data.split(":", 1)[1])
        with db() as c:
            req = c.execute("SELECT * FROM channel_funding_requests WHERE id=? AND status='pending'", (rid,)).fetchone()
            if req:
                c.execute("UPDATE channel_funding_requests SET status='rejected' WHERE id=?", (rid,))
        if req:
            try:
                await context.bot.send_message(req['user_id'], f"❌ لم تتم الموافقة على طلب إضافة قناتك ({req['title']}) إلى مهام تجميع النقاط.")
            except TelegramError:
                pass
        await safe_edit(q, "تم رفض الطلب.", reply_markup=kb([[btn("📣 طلبات التمويل", "funding_requests")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "api_clients_admin" and is_admin(uid):
        with db() as c:
            rows=c.execute("SELECT user_id,token_prefix,balance,active,created FROM api_clients ORDER BY created DESC LIMIT 30").fetchall()
        lines=["👥 عملاء API (آخر 30):"]
        buttons=[]
        for r in rows:
            lines.append(f"\n• {r['user_id']} | {r['token_prefix']}… | الرصيد {r['balance']} | {'فعال' if r['active'] else 'موقوف'}")
            buttons.append([btn(f"{'⛔ إيقاف' if r['active'] else '✅ تفعيل'} API {r['user_id']}", f"api_toggle:{r['user_id']}")])
        buttons.append([btn("➕ إضافة رصيد API بالآيدي", "api_credit_start", "success")])
        buttons.append([btn("🔑 إنشاء/تجديد مفتاح لمستخدم", "api_admin_key_start", "primary")])
        buttons.append([btn("🔙 لوحة التحكم", "admin")])
        await safe_edit(q, "\n".join(lines) if rows else "لا يوجد عملاء API حتى الآن.", reply_markup=kb(buttons))

    elif data == "api_credit_start" and is_admin(uid):
        context.user_data["state"] = "api_credit_user_id"
        await safe_edit(q, "➕ إضافة رصيد API لزبون\nأرسل Telegram ID الخاص بالزبون.\n\nأرسل إلغاء للرجوع.", reply_markup=kb([[btn("🔙 إلغاء", "api_clients_admin")]]))

    elif data == "api_admin_key_start" and is_admin(uid):
        context.user_data["state"] = "api_admin_key_user_id"
        await safe_edit(q, "🔑 إنشاء أو تجديد مفتاح API لمستخدم\nأرسل Telegram ID الخاص بالمستخدم.\nسيتم إبطال المفتاح السابق وإرسال المفتاح الجديد إلى المستخدم برسالة خاصة.", reply_markup=kb([[btn("🔙 إلغاء", "api_clients_admin")]]))

    elif data.startswith("api_toggle:") and is_admin(uid):
        try: target=int(data.split(":",1)[1])
        except ValueError: return
        with db() as c:
            row=c.execute("SELECT active FROM api_clients WHERE user_id=?",(target,)).fetchone()
            if not row:
                await safe_edit(q,"حساب API غير موجود.",reply_markup=admin_keyboard()); return
            new_active=0 if row['active'] else 1
            c.execute("UPDATE api_clients SET active=?,updated=? WHERE user_id=?",(new_active,datetime.now(timezone.utc).isoformat(),target))
        try:
            await context.bot.send_message(target, "✅ تم تفعيل حساب API من الإدارة." if new_active else "⛔ تم إيقاف حساب API من الإدارة.")
        except TelegramError:
            pass
        try:
            await context.bot.send_message(OWNER_ID, f"🔔 إشعار إدارة API\n\n{'✅ تم تفعيل' if new_active else '⛔ تم إيقاف'} حساب API\n👤 حساب المستخدم: {target}\n🛡️ نفّذ العملية المشرف: {uid}")
        except TelegramError:
            pass
        await safe_edit(q,"تم تحديث حالة حساب API.",reply_markup=kb([[btn("👥 عملاء API", "api_clients_admin")],[btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "edit_api_link_price" and is_admin(uid):
        context.user_data["state"] = "api_link_price"
        await safe_edit(q, f"السعر الحالي لربط API: {get_setting('api_link_price', '0')}\nأرسل السعر الجديد كرقم موجب أو صفر. هذا إعداد سعري محفوظ، ولا يُخصم تلقائياً من المستخدمين.")

    elif data.startswith("provider_margin:") and is_admin(uid):
        pid = int(data.split(":", 1)[1])
        with db() as c:
            prov = c.execute("SELECT id,name,profit_percent FROM providers WHERE id=?", (pid,)).fetchone()
        if not prov:
            await safe_edit(q, "المزود غير موجود.", reply_markup=admin_keyboard())
            return
        current = "هامش الربح العام" if prov['profit_percent'] is None or float(prov['profit_percent']) < 0 else f"{float(prov['profit_percent']):g}%"
        context.user_data["state"] = "provider_margin"
        context.user_data["provider_margin_id"] = pid
        await safe_edit(q, f"هامش ربح المزود: {prov['name']}\nالقيمة الحالية: {current}\nأرسل نسبة الربح من 0 إلى 10000، أو اكتب عام لاستخدام الهامش العام ({get_setting('profit_percent', '20')}%).")

    elif data.startswith("platform:"):
        if not await subscription_gate(update, context):
            return
        platform = data.split(":", 1)[1]
        with db() as c:
            sections = c.execute("SELECT id,name FROM service_sections WHERE platform=? AND enabled=1 ORDER BY name", (platform,)).fetchall()
        if sections:
            rows = [[btn("📁 " + sec["name"][:35], f"publicsection:{platform}:{sec['id']}")] for sec in sections]
            rows += [[btn("🛍 كل الخدمات", f"platformall:{platform}")], [btn("🔙 التطبيقات", "services")]]
            await safe_edit(q, f"{PLATFORMS.get(platform, platform)}\nاختر القسم لعرض خدماته:", reply_markup=kb(rows))
        else:
            await show_platform_services(q, platform)

    elif data.startswith("publicsection:"):
        if not await subscription_gate(update, context):
            return
        parts = data.split(":", 2)
        if len(parts) != 3: return
        try: section_id = int(parts[2])
        except ValueError: return
        await show_platform_services(q, parts[1], section_id)

    elif data.startswith("platformall:"):
        if not await subscription_gate(update, context):
            return
        await show_platform_services(q, data.split(":", 1)[1])

    elif data.startswith("service:"):
        if not await subscription_gate(update, context):
            return
        try:
            sid = int(data.split(":")[1])
            with db() as c:
                s = c.execute(
                    "SELECT * FROM services WHERE id=? AND enabled=1",
                    (sid,)
                ).fetchone()
            if not s:
                raise ValueError()

            context.user_data.clear()
            context.user_data["service_id"] = sid
            context.user_data["state"] = "order_quantity"
            await safe_edit(q,
                ui_message("order_service_info").format(
                    service_name=s["name"],
                    price=int(s["price_points"] or 0),
                    min_qty=s["min_qty"],
                    max_qty=s["max_qty"],
                    service_id=s["external_id"] or s["id"],
                ),
                reply_markup=kb([[btn("❌ إلغاء", "home")]])
            )
        except (ValueError, TypeError):
            await safe_edit(q, "الخدمة غير متاحة.")

    elif data == "order_confirm":
        try:
            sid = int(context.user_data["service_id"])
            link = str(context.user_data["order_link"])
            quantity = int(context.user_data["order_quantity"])
        except (KeyError, ValueError, TypeError):
            context.user_data.clear()
            await safe_edit(q, "انتهت جلسة الطلب. اختر الخدمة من جديد.", reply_markup=home_keyboard(uid))
            return
        context.user_data.clear()
        try:
            result = await create_order_request(update, context, sid, link, quantity)
            await safe_edit(q, result, reply_markup=kb([[btn("🛍 طلب جديد", "services", "success")], [btn("📋 طلباتي", "myorders"), btn("🏠 الرئيسية", "home")]]))
        except Exception as exc:
            log.exception("Confirmed order submission failed")
            await safe_edit(q, f"❌ تعذر تنفيذ الطلب: {str(exc)[:250]}", reply_markup=home_keyboard(uid))

    elif data == "order_cancel":
        context.user_data.clear()
        await safe_edit(q, "تم إلغاء الطلب قبل إرساله.", reply_markup=home_keyboard(uid))

    elif data == "account":
        with db() as c:
            u = c.execute(
                "SELECT * FROM users WHERE user_id=?", (uid,)
            ).fetchone()
            completed = c.execute(
                "SELECT COUNT(*) n FROM orders WHERE user_id=? AND status='completed'",
                (uid,)
            ).fetchone()["n"]

        await safe_edit(q, 
            f"👤 حسابك\n🆔 {uid}\n💎 النقاط: {balance(uid)}\n"
            f"📦 الطلبات المكتملة: {completed}\n"
            f"⭐ VIP: {'مفعل' if user_vip(uid) else 'غير مفعل'}",
            reply_markup=kb([[btn("🔙 رجوع", "home")]])
        )

    elif data == "orders_channel_open":
        channel = get_setting("orders_channel", "").strip()
        if not channel:
            await safe_edit(q, "📣 قناة الطلبات لم يتم ربطها بعد. سيتم تفعيل الزر فور ضبطها من الإدارة.", reply_markup=kb([[btn("🔙 رجوع", "home")]]))
        else:
            target = channel if channel.startswith("https://") else ("https://t.me/" + channel.lstrip("@") if not channel.startswith("-") else "")
            if target:
                await safe_edit(q, "📣 اضغط الزر أدناه لفتح قناة الطلبات ومتابعة الطلبات المؤكدة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📣 فتح قناة الطلبات", url=target)], [btn("🔙 رجوع", "home")]]))
            else:
                await safe_edit(q, f"📣 قناة الطلبات مرتبطة بالمعرف: {channel}\nافتح القناة من تيليجرام.", reply_markup=kb([[btn("🔙 رجوع", "home")]]))

    elif data == "orders_channel" and is_admin(uid):
        context.user_data["state"] = "orders_channel"
        current = get_setting("orders_channel", "") or "غير محددة"
        await safe_edit(q, f"📣 إعداد قناة الطلبات\nالقناة الحالية: {current}\n\nأرسل أحد الخيارات التالية: @username أو رابط القناة https://t.me/username أو chat_id.\nأضف البوت مشرفاً مع صلاحية إرسال الرسائل. أرسل 0 لإلغاء الربط.", reply_markup=kb([[btn("🔙 رجوع", "admin")]]))

    elif data == "channel_funding_settings" and is_admin(uid):
        await safe_edit(q,
            "📣 إعدادات تمويل قناتك\n\n"
            f"🎁 مكافأة العضو: {get_setting('channel_join_reward', '10')} نقطة\n"
            f"💰 سعر العضو على صاحب القناة: {get_setting('channel_member_price', '15')} نقطة\n\n"
            "عند إرسال القناة، تُضاف تلقائياً إلى تجميع النقاط بعد التحقق من صلاحيات القناة. يُخصم سعر العضو من صاحب القناة عند احتساب كل عضو جديد، وتُمنح المكافأة للمشترك.",
            reply_markup=kb([[btn("🎁 تعديل مكافأة العضو", "edit_channel_reward")], [btn("💰 تعديل سعر العضو", "edit_channel_price")], [btn("🔙 لوحة التحكم", "admin")]])
        )

    elif data == "edit_channel_reward" and is_admin(uid):
        context.user_data["state"] = "edit_channel_reward"
        await safe_edit(q, "أرسل مكافأة العضو بالنقاط (من 1 إلى 1000000).")

    elif data == "edit_channel_price" and is_admin(uid):
        context.user_data["state"] = "edit_channel_price"
        await safe_edit(q, "أرسل سعر العضو الذي يُخصم من صاحب القناة بالنقاط (من 1 إلى 100000000).")

    elif data == "completed_channel_open":
        channel = get_setting("completed_orders_channel", "").strip()
        count = completed_orders_count()
        if channel:
            target = channel if channel.startswith("https://") else "https://t.me/" + channel.lstrip("@")
            await safe_edit(q, f"🛡️ عدد الطلبات المنجزة: {count}\nقناة اكتمال الطلبات: {target}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📣 فتح قناة الطلبات المكتملة", url=target)], [btn("🔙 رجوع", "home")]]))
        else:
            await safe_edit(q, f"🛡️ عدد الطلبات المنجزة: {count}\nلم تحدد الإدارة قناة اكتمال الطلبات بعد.", reply_markup=kb([[btn("🔙 رجوع", "home")]]))

    elif data == "completed_channel_url":
        target = context.user_data.get("completed_channel_target") or get_setting("completed_orders_channel", "").strip()
        if target:
            target = target if target.startswith("https://") else "https://t.me/" + target.lstrip("@")
            await safe_edit(q, f"📣 قناة اكتمال الطلبات:\n{target}", reply_markup=kb([[btn("🔙 رجوع", "home")]]))
        else:
            await safe_edit(q, "لم تحدد الإدارة قناة اكتمال الطلبات.", reply_markup=kb([[btn("🔙 رجوع", "home")]]))

    elif data == "myorders":
        with db() as c:
            rows = c.execute("""
            SELECT id,service_id,quantity,cost_points,status
            FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15
            """, (uid,)).fetchall()

        customer_statuses = {
            "processing": "قيد المراجعة",
            "submitted": "قيد المراجعة والمتابعة",
            "manual_pending": "قيد المراجعة من الإدارة",
            "failed": "مرفوض ❌",
            "rejected": "مرفوض ❌",
            "completed": "مكتمل ✅",
            "cancelled": "ملغى وتمت إعادة الرصيد",
        }
        message = "\n".join(
            f"#{r['id']} | الخدمة {r['service_id']} | "
            f"الكمية {r['quantity']} | {customer_statuses.get(r['status'], 'قيد المراجعة')}"
            for r in rows
        ) or "لا توجد طلبات."

        await safe_edit(q, 
            "📦 طلباتك:\n\n" + message,
            reply_markup=kb([[btn("🔙 رجوع", "home")]])
        )

    elif data == "check_order":
        context.user_data["state"] = "check_order"
        await safe_edit(q, "أرسل رقم الطلب.")

    elif data == "access_pay":
        if is_admin(uid):
            await safe_edit(q, "حساب المشرف لا يحتاج إلى دفع.", reply_markup=home_keyboard(uid))
            return
        stars = max(1, int(get_setting("paid_gate_stars", "10")))
        await context.bot.send_invoice(
            chat_id=uid,
            title="فتح الوصول إلى البوت",
            description="دفع لمرة واحدة لفتح استخدام البوت",
            payload=f"access:{uid}:{stars}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("فتح الوصول إلى البوت", stars)],
        )

    elif data == "use_recharge_code":
        context.user_data["state"] = "redeem_recharge_code"
        await safe_edit(q,
            "🎟️ استخدام كود الشحن\n\nأرسل كود الشحن الذي حصلت عليه. كل كود يُستخدم مرة واحدة فقط.",
            reply_markup=kb([[btn("❌ إلغاء", "home")]])
        )

    elif data == "recharge_codes_admin" and is_admin(uid):
        with db() as c:
            total = c.execute("SELECT COUNT(*) n FROM recharge_codes").fetchone()["n"]
            unused = c.execute("SELECT COUNT(*) n FROM recharge_codes WHERE redeemed_by IS NULL").fetchone()["n"]
            redeemed = c.execute("SELECT COUNT(*) n FROM recharge_codes WHERE redeemed_by IS NOT NULL").fetchone()["n"]
        await safe_edit(q,
            f"🎟️ إدارة كودات الشحن\n\nإجمالي الأكواد: {total}\nغير مستخدمة: {unused}\nمستخدمة: {redeemed}\n\nأنشئ دفعة أكواد وحدد نقاط كل كود وعدد الأكواد.",
            reply_markup=kb([
                [btn("➕ إنشاء كودات جديدة", "recharge_codes_create")],
                [btn("📋 عرض آخر الأكواد", "recharge_codes_recent")],
                [btn("🔙 لوحة الإدارة", "admin")]
            ])
        )

    elif data == "recharge_codes_create" and is_admin(uid):
        context.user_data["state"] = "recharge_code_points"
        await safe_edit(q, "أرسل عدد النقاط التي سيمنحها كل كود (من 1 إلى 1,000,000,000).\nاكتب إلغاء للتراجع.", reply_markup=kb([[btn("❌ إلغاء", "recharge_codes_admin")]]))

    elif data == "recharge_codes_recent" and is_admin(uid):
        with db() as c:
            rows = c.execute("SELECT code,points,redeemed_by,created FROM recharge_codes ORDER BY created DESC LIMIT 15").fetchall()
        if rows:
            lines = []
            for row in rows:
                status = f"مستخدم بواسطة {row['redeemed_by']}" if row["redeemed_by"] is not None else "غير مستخدم"
                lines.append(f"`{row['code']}` — {row['points']} نقطة — {status}")
            body = "🎟️ آخر 15 كود شحن:\n\n" + "\n".join(lines)
        else:
            body = "لا توجد أكواد شحن حتى الآن."
        await safe_edit(q, body, reply_markup=kb([[btn("🔙 إدارة كودات الشحن", "recharge_codes_admin")]]), parse_mode="Markdown")

    elif data == "recharge":
        manual_rows = [[btn(label, "manualpay:" + key)] for key, label in MANUAL_PAYMENT_METHODS.items()]
        await safe_edit(q,
            "💳 اختر طريقة شحن الرصيد:\n\n"
            "⭐ الدفع التلقائي المتاح حالياً: Telegram Stars.\n"
            "💵 بقية الطرق تُراجع يدوياً بعد إرسال الإيصال.\n"
            "ملاحظة: الدفع التلقائي بالبطاقات/PayPal/USDT يتطلب ربط بوابة دفع وحساب تاجر صالح.",
            reply_markup=kb([
                [btn("⭐ Telegram Stars — تلقائي", "stars_packages")],
                *manual_rows,
                [btn("🔙 رجوع", "home")]
            ])
        )

    elif data == "stars_packages":
        await safe_edit(q, "⭐ اختر باقة شحن النقاط:", reply_markup=kb([
            [btn("10 نجوم", "pay:10"), btn("25 نجمة", "pay:25")],
            [btn("50 نجمة", "pay:50"), btn("100 نجمة", "pay:100")],
            [btn("🔙 رجوع", "recharge")]
        ]))

    elif data.startswith("manualpay:"):
        method = data.split(":", 1)[1]
        if method not in MANUAL_PAYMENT_METHODS:
            await safe_edit(q, "طريقة الدفع غير متاحة.", reply_markup=home_keyboard(uid))
            return
        context.user_data.clear()
        context.user_data["state"] = "manual_amount"
        context.user_data["manual_method"] = method
        await safe_edit(q,
            f"طريقة الدفع: {MANUAL_PAYMENT_METHODS[method]}\n\n"
            f"بيانات التحويل:\n{payment_instructions(method)}\n\n"
            "أدخل مبلغ الشحن بالدولار (مثال: 5 أو 10.50). لا تحوّل قبل التأكد من بيانات الدفع.",
            reply_markup=kb([[btn("❌ إلغاء", "recharge")]])
        )

    elif data == "payment_settings" and is_admin(uid):
        rows = [[btn("⚙️ " + label, "paycfg:" + key)] for key, label in MANUAL_PAYMENT_METHODS.items()]
        rows.append([btn("🔙 رجوع", "admin")])
        await safe_edit(q, "اختر طريقة لتعديل بيانات التحويل التي تظهر للمستخدم:", reply_markup=kb(rows))

    elif data.startswith("paycfg:") and is_admin(uid):
        method = data.split(":", 1)[1]
        if method not in MANUAL_PAYMENT_METHODS:
            await safe_edit(q, "طريقة غير معروفة.", reply_markup=admin_keyboard())
            return
        context.user_data["state"] = "payment_details_text"
        context.user_data["payment_details_method"] = method
        await safe_edit(q, f"أرسل الآن بيانات الدفع/رقم الحساب/المحفظة وتعليمات التحويل لطريقة {MANUAL_PAYMENT_METHODS[method]}.\nأرسل نصاً واضحاً، أو اكتب إلغاء.")

    elif data == "payment_requests" and is_admin(uid):
        with db() as c:
            requests = c.execute("SELECT id,user_id,method,amount_usd,created FROM manual_deposits WHERE status='pending' ORDER BY id DESC LIMIT 20").fetchall()
        rows = [[btn(f"#{r['id']} | {r['amount_usd']:.2f}$ | {r['user_id']}", f"payreq:{r['id']}")] for r in requests]
        rows.append([btn("🔙 رجوع", "admin")])
        await safe_edit(q, "🧾 طلبات الدفع اليدوي المعلّقة:" if requests else "لا توجد طلبات دفع معلّقة.", reply_markup=kb(rows))

    elif data.startswith("payreq:") and is_admin(uid):
        try:
            rid = int(data.split(":", 1)[1])
        except ValueError:
            return
        with db() as c:
            req = c.execute("SELECT * FROM manual_deposits WHERE id=?", (rid,)).fetchone()
        if not req:
            await safe_edit(q, "الطلب غير موجود.", reply_markup=admin_keyboard())
            return
        detail = (f"طلب شحن يدوي #{rid}\nالمستخدم: {req['user_id']}\n"
                  f"الطريقة: {MANUAL_PAYMENT_METHODS.get(req['method'], req['method'])}\n"
                  f"المبلغ: ${req['amount_usd']:.2f}\nالمرجع: {req['reference'] or 'غير مرفق'}\n"
                  f"الحالة: {req['status']}\nالإيصال: {'مرفق' if req['receipt_file_id'] else 'غير مرفق'}")
        buttons = []
        if req['status'] == 'pending':
            buttons = [[btn("✅ قبول وإضافة الرصيد", f"payapprove:{rid}"), btn("❌ رفض", f"payreject:{rid}")]]
        buttons.append([btn("📋 الطلبات المعلقة", "payment_requests")])
        if req['receipt_file_id']:
            try:
                await context.bot.send_photo(chat_id=uid, photo=req['receipt_file_id'], caption=f"إيصال طلب الدفع #{rid}")
            except TelegramError:
                pass
        await safe_edit(q, detail, reply_markup=kb(buttons))

    elif data.startswith("payapprove:") and is_admin(uid):
        rid = int(data.split(":", 1)[1])
        with db() as c:
            req = c.execute("SELECT * FROM manual_deposits WHERE id=?", (rid,)).fetchone()
            if not req or req['status'] != 'pending':
                await safe_edit(q, "تمت معالجة هذا الطلب مسبقاً أو أنه غير موجود.", reply_markup=admin_keyboard())
                return
            ppu = max(1, int(float(get_setting("points_per_usd", "1000"))))
            points = int(math.floor(float(req['amount_usd']) * ppu))
            if points < 1:
                await safe_edit(q, "المبلغ صغير جداً ولا ينتج عنه نقاط. راجع إعدادات النقاط.", reply_markup=admin_keyboard())
                return
            cur = c.execute("UPDATE manual_deposits SET status='approved',reviewed_by=?,reviewed_at=? WHERE id=? AND status='pending'",
                            (uid, datetime.now(timezone.utc).isoformat(), rid))
            if cur.rowcount != 1:
                await safe_edit(q, "تمت معالجة الطلب مسبقاً.", reply_markup=admin_keyboard())
                return
            c.execute("UPDATE users SET points=points+? WHERE user_id=?", (points, req['user_id']))
        try:
            await context.bot.send_message(req['user_id'], f"✅ تم قبول طلب الشحن #{rid}.\nالمبلغ: ${req['amount_usd']:.2f}\nتمت إضافة {points} نقطة.\nرصيدك الحالي: {balance(req['user_id'])}")
        except TelegramError:
            pass
        await safe_edit(q, f"تم قبول الطلب #{rid} وإضافة {points} نقطة مرة واحدة.", reply_markup=kb([[btn("طلبات الدفع", "payment_requests")], [btn("لوحة الإدارة", "admin")]]))

    elif data.startswith("payreject:") and is_admin(uid):
        rid = int(data.split(":", 1)[1])
        with db() as c:
            req = c.execute("SELECT * FROM manual_deposits WHERE id=?", (rid,)).fetchone()
            if not req or req['status'] != 'pending':
                await safe_edit(q, "تمت معالجة هذا الطلب مسبقاً أو أنه غير موجود.", reply_markup=admin_keyboard())
                return
            c.execute("UPDATE manual_deposits SET status='rejected',reviewed_by=?,reviewed_at=? WHERE id=? AND status='pending'",
                      (uid, datetime.now(timezone.utc).isoformat(), rid))
        try:
            await context.bot.send_message(req['user_id'], f"❌ تم رفض طلب الشحن اليدوي #{rid}. تواصل مع الدعم إذا كنت تعتقد أن هناك خطأ.")
        except TelegramError:
            pass
        await safe_edit(q, f"تم رفض طلب الدفع #{rid}.", reply_markup=kb([[btn("طلبات الدفع", "payment_requests")], [btn("لوحة الإدارة", "admin")]]))

    elif data.startswith("pay:"):
        stars = int(data.split(":")[1])
        if stars not in (10, 25, 50, 100):
            return

        await context.bot.send_invoice(
            chat_id=uid,
            title=f"شحن {stars} نجمة",
            description="شحن نقاط المتجر",
            payload=f"points:{uid}:{stars}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("نجوم تيليجرام", stars)]
        )

    elif data == "earn":
        await safe_edit(q, 
            "🎁 تجميع النقاط\nاختر طريقة التجميع:",
            reply_markup=kb([
                [btn("📢 الانضمام للقنوات", "tasks")],
                [btn("🔗 رابط الإحالة ودعوة الأصدقاء", "referral")],
                [btn("🎁 الهدية اليومية", "daily")],
                [btn("🎡 عجلة الحظ", "spin")],
                [btn("🔙 رجوع", "home")]
            ])
        )

    elif data == "referral":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{uid}"
        await safe_edit(q, 
            f"👥 رابط دعوتك:\n{link}\n\n"
            f"🎁 مكافأة كل دعوة مؤهلة: {get_setting('default_referral_reward')} نقطة لك وللشخص الذي ينضم عبر رابطك.",
            reply_markup=kb([[btn("🔙 رجوع", "home")]])
        )

    elif data == "daily":
        today = date.today().isoformat()
        with db() as c:
            claimed = c.execute("""
            SELECT 1 FROM daily_claims WHERE user_id=? AND claim_date=?
            """, (uid, today)).fetchone()

            if claimed:
                await safe_edit(q, 
                    "لقد حصلت على هديتك اليومية اليوم.",
                    reply_markup=kb([[btn("🔙 رجوع", "home")]])
                )
                return

            reward = max(0, int(get_setting("daily_reward", "10")))
            c.execute("""
            INSERT INTO daily_claims(user_id,claim_date,reward)
            VALUES(?,?,?)
            """, (uid, today, reward))
            c.execute(
                "UPDATE users SET points=points+? WHERE user_id=?",
                (reward, uid)
            )

        await safe_edit(q, 
            f"🎁 حصلت على {reward} نقطة!",
            reply_markup=kb([[btn("🔙 رجوع", "home")]])
        )

    elif data == "spin":
        today = date.today().isoformat()
        with db() as c:
            u = c.execute(
                "SELECT last_spin FROM users WHERE user_id=?", (uid,)
            ).fetchone()

            if u and u["last_spin"] == today:
                await safe_edit(q, 
                    "يمكنك استخدام عجلة الحظ مرة واحدة يومياً.",
                    reply_markup=kb([[btn("🔙 رجوع", "home")]])
                )
                return

            low = max(0, int(get_setting("spin_min", "0")))
            high = max(low, int(get_setting("spin_max", "100")))
            reward = random.randint(low, high)

            c.execute(
                "UPDATE users SET last_spin=? WHERE user_id=?",
                (today, uid)
            )
            c.execute(
                "UPDATE users SET points=points+? WHERE user_id=?",
                (reward, uid)
            )
            c.execute(
                "INSERT INTO spins(user_id,reward,created) VALUES(?,?,?)",
                (uid, reward, datetime.now(timezone.utc).isoformat())
            )

        await safe_edit(q, 
            f"🎡 مبروك! حصلت على {reward} نقطة.\n"
            f"💎 رصيدك: {balance(uid)}",
            reply_markup=kb([[btn("🔙 رجوع", "home")]])
        )

    elif data == "transfer":
        context.user_data["state"] = "transfer_id"
        await safe_edit(q, "أرسل رقم Telegram ID للمستلم.")

    elif data == "vip":
        price = int(get_setting("vip_price_stars", "100"))
        days = int(get_setting("vip_days", "30"))
        await safe_edit(q, 
            f"⭐ VIP\nالمدة: {days} يوم\nالسعر: {price} نجمة",
            reply_markup=kb([
                [btn("⭐ شراء VIP", "buyvip")],
                [btn("🔙 رجوع", "home")]
            ])
        )

    elif data == "buyvip":
        stars = int(get_setting("vip_price_stars", "100"))
        if stars < 1:
            return

        await context.bot.send_invoice(
            chat_id=uid,
            title="اشتراك VIP",
            description="اشتراك VIP للمتجر",
            payload=f"vip:{uid}:{stars}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("اشتراك VIP", stars)]
        )

    elif data == "support":
        context.user_data["state"] = "support_message"
        await safe_edit(q,
            (get_setting("support") or "🆘 الدعم الفني") + "\n\nاكتب رسالتك هنا وسيتم إرسالها للإدارة.",
            reply_markup=kb([[btn("🔙 رجوع", "home")]])
        )

    # ---------------- ADMIN PANEL ----------------

    elif data == "admin" and is_admin(uid):
        await safe_edit(q, 
            "╔══════════════════════╗\n"
            "   💠 ULTIMATE CONTROL\n"
            "   لوحة التحكم المتطورة\n"
            "╚══════════════════════╝",
            reply_markup=admin_keyboard()
        )

    elif data == "users" and is_admin(uid):
        with db() as c:
            rows = c.execute("SELECT user_id,username,points,joined FROM users ORDER BY joined DESC LIMIT 25").fetchall()
            total = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        lines = [f"👥 إدارة العملاء — الإجمالي: {total}", "آخر 25 مستخدماً:"]
        for r in rows:
            uname = ("@" + r["username"]) if r["username"] else "بدون اسم مستخدم"
            lines.append(f"• {r['user_id']} | {uname} | 💎 {r['points']} نقطة")
        await safe_edit(q, "\n".join(lines), reply_markup=kb([[btn("🔄 تحديث القائمة", "users")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "allorders" and is_admin(uid):
        with db() as c:
            rows = c.execute("SELECT id,user_id,service_id,quantity,cost_points,status,created FROM orders ORDER BY id DESC LIMIT 25").fetchall()
            total = c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"]
        lines = [f"📋 طلبات العملاء — الإجمالي: {total}", "آخر 25 طلباً:"]
        order_buttons = []
        for r in rows:
            lines.append(f"• #{r['id']} | مستخدم {r['user_id']} | خدمة {r['service_id']} | كمية {r['quantity']} | {r['cost_points']} نقطة | {r['status']}")
            if r['status'] not in ("completed", "cancelled", "rejected", "failed"):
                order_buttons.append([
                    btn(f"✅ إكمال #{r['id']}", f"ordcomplete:{r['id']}", "success"),
                    btn(f"❌ إلغاء #{r['id']}", f"ordcancel:{r['id']}", "danger"),
                ])
        order_buttons.extend([
            [btn("🔄 تحديث الطلبات", "allorders")],
            [btn("🔙 لوحة التحكم", "admin")],
        ])
        await safe_edit(q, "\n".join(lines) if rows else "لا توجد طلبات حتى الآن.", reply_markup=kb(order_buttons))

    elif data.startswith("ordcomplete:") and is_admin(uid):
        try:
            order_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await safe_edit(q, "رقم الطلب غير صحيح.", reply_markup=admin_keyboard())
            return
        with db() as c:
            order = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if order and order["status"] not in ("completed", "cancelled"):
                c.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
                changed = True
            else:
                changed = False
        if not order:
            await safe_edit(q, "لم يتم العثور على الطلب.", reply_markup=admin_keyboard())
        elif not changed:
            await safe_edit(q, f"الطلب #{order_id} مغلق مسبقاً وحالته: {order['status']}.", reply_markup=admin_keyboard())
        else:
            try:
                await context.bot.send_message(order["user_id"], render_template("order_complete", order_id=order_id, user_id=order["user_id"]))
            except TelegramError:
                log.exception("Could not notify customer about completed order %s", order_id)

            # The configured completed-orders channel must receive only completed orders,
            # never orders that are merely submitted or still under review.
            orders_channel = get_setting("completed_orders_channel", "").strip()
            if orders_channel:
                try:
                    with db() as c:
                        service_row = c.execute("SELECT name FROM services WHERE id=?", (order["service_id"],)).fetchone()
                    service_name = service_row["name"] if service_row else f"الخدمة #{order['service_id']}"
                    await context.bot.send_message(
                        chat_id=orders_channel,
                        text=(f"🎉 تم إكمال طلب بنجاح\n🆔 رقم الطلب: #{order_id}\n"
                              f"🛍 الخدمة: {service_name}\n📦 الكمية: {order['quantity']}")
                    )
                except TelegramError:
                    log.exception("Could not publish completed order %s to configured channel", order_id)

            await safe_edit(q, f"✅ تم وضع الطلب #{order_id} كمكتمل وإبلاغ العميل.", reply_markup=admin_keyboard())

    elif data.startswith("ordcancel:") and is_admin(uid):
        try:
            order_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await safe_edit(q, "رقم الطلب غير صحيح.", reply_markup=admin_keyboard())
            return
        with db() as c:
            order = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if order and order["status"] not in ("completed", "cancelled"):
                c.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
                c.execute("UPDATE users SET points=points+? WHERE user_id=?", (int(order["cost_points"] or 0), order["user_id"]))
                changed = True
            else:
                changed = False
        if not order:
            await safe_edit(q, "لم يتم العثور على الطلب.", reply_markup=admin_keyboard())
        elif not changed:
            await safe_edit(q, f"الطلب #{order_id} مغلق مسبقاً وحالته: {order['status']}.", reply_markup=admin_keyboard())
        else:
            try:
                await context.bot.send_message(order["user_id"], f"ℹ️ تم إلغاء طلبك #{order_id} من قبل الإدارة، وتمت إعادة {int(order['cost_points'] or 0)} نقطة إلى رصيدك.")
            except TelegramError:
                log.exception("Could not notify customer about cancelled order %s", order_id)
            await safe_edit(q, f"❌ تم إلغاء الطلب #{order_id} وإعادة الرصيد للعميل.", reply_markup=admin_keyboard())

    elif data == "rewards" and is_admin(uid):
        await safe_edit(q, "🎁 إعدادات الجوائز والمكافآت\nاختر الإعداد الذي تريد تغييره:", reply_markup=kb([
            [btn("🎯 إعدادات النقاط والهدايا", "point_settings")],
            [btn("⭐ إعدادات اشتراك VIP", "vip_settings")],
            [btn("🎯 مهام تجميع النقاط", "tasks")],
            [btn("🔙 لوحة التحكم", "admin")]
        ]))

    elif data == "vip_settings" and is_admin(uid):
        await safe_edit(q, f"⭐ إعدادات VIP\nالسعر الحالي: {get_setting('vip_price_stars', '100')} نجمة\nمدة الاشتراك تُدار من معالج الدفع الحالي.\nأرسل السعر الجديد من الزر التالي.", reply_markup=kb([
            [btn("✏️ تعديل سعر VIP", "vip_price_edit")],
            [btn("🔙 لوحة التحكم", "admin")]
        ]))

    elif data == "vip_price_edit" and is_admin(uid):
        context.user_data["state"] = "vip_price_stars"
        await safe_edit(q, "أرسل سعر اشتراك VIP بالنجوم كعدد صحيح من 1 إلى 1000000. اكتب إلغاء للتراجع.")

    elif data == "vip_bots" and is_admin(uid):
        with db() as c:
            rows = c.execute("SELECT id,user_id,provider_id,enabled,created FROM user_bots ORDER BY id DESC LIMIT 30").fetchall()
            total = c.execute("SELECT COUNT(*) n FROM user_bots").fetchone()["n"]
        lines = [f"🤖 بوتات VIP المسجلة: {total}"]
        for r in rows:
            lines.append(f"• #{r['id']} | المستخدم {r['user_id']} | المزود {r['provider_id'] or 'غير محدد'} | {'فعال' if r['enabled'] else 'موقوف'}")
        await safe_edit(q, "\n".join(lines) if rows else "لا توجد بوتات مسجلة في جدول بوتات المستخدمين حالياً.", reply_markup=kb([[btn("🔄 تحديث", "vip_bots")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "broadcast" and is_admin(uid):
        context.user_data["state"] = "broadcast_message"
        await safe_edit(q,
            "📡 إذاعة عامة\n\nأرسل الآن نص الرسالة التي تريد إرسالها إلى مستخدمي البوت، وكذلك القنوات المسجلة التي أضافها أصحابها إلى مهام تجميع النقاط.\n\nاكتب إلغاء للتراجع.\nملاحظة: لا يستطيع تيليجرام كشف كل القنوات التي يكون المستخدم مشرفاً فيها تلقائياً؛ يجب أن تكون القناة معروفة للبوت وأن يكون البوت مشرفاً فيها.",
            reply_markup=kb([[btn("🔙 لوحة التحكم", "admin")]])
        )

    elif data == "completed_count_show":
        label = get_setting("completed_count_button_name", "🛡️ عدد الطلبات المنجزة: {count}")
        label = label.replace("{count}", str(completed_orders_count()))
        await safe_edit(q, f"{label}\n\nإجمالي الطلبات التي اكتملت بنجاح: {completed_orders_count()}", reply_markup=kb([[btn("🔙 رجوع", "home")]]))

    elif data == "menu_button_manager" and is_admin(uid):
        rows = []
        layout = get_home_layout()
        for row in layout:
            for key in row:
                label = ui_label(key) if key in UI_LABELS else get_setting("completed_count_button_name", "🛡️ عدد الطلبات المنجزة: {count}").replace("{count}", "{count}")
                rows.append([btn("🔘 " + label[:45], "menu_manage:" + key)])
        rows.append([btn("➕ إظهار زر محذوف", "menu_restore_list")])
        rows.append([btn("🔙 لوحة التحكم", "admin")])
        await safe_edit(q, "🛠 إدارة القوائم والأزرار\nاختر الزر لتعديل اسمه أو مكانه أو القسم الذي يفتحه، أو حذفه من واجهة المستخدم.", reply_markup=kb(rows))

    elif data == "menu_restore_list" and is_admin(uid):
        try:
            hidden = set(json.loads(get_setting("home_hidden_buttons", "[]")))
        except Exception:
            hidden = set()
        rows = []
        for key in sorted(hidden):
            label = UI_LABELS[key][0] if key in UI_LABELS else "🛡️ عدد الطلبات المنجزة"
            rows.append([btn("♻️ إظهار " + label[:40], "menu_restore:" + key)])
        rows.append([btn("🔙 إدارة القوائم والأزرار", "menu_button_manager")])
        await safe_edit(q, "اختر الزر الذي تريد إظهاره من جديد:", reply_markup=kb(rows))

    elif data.startswith("menu_restore:") and is_admin(uid):
        key = data.split(":", 1)[1]
        try:
            hidden = set(json.loads(get_setting("home_hidden_buttons", "[]")))
        except Exception:
            hidden = set()
        hidden.discard(key)
        set_setting("home_hidden_buttons", json.dumps(sorted(hidden), ensure_ascii=False))
        layout = get_home_layout()
        if not any(key in row for row in layout): layout.append([key])
        set_setting("home_button_layout", json.dumps(layout, ensure_ascii=False))
        await safe_edit(q, "✅ تمت إعادة إظهار الزر.", reply_markup=kb([[btn("🛠 إدارة القوائم والأزرار", "menu_button_manager")], [btn("👁 عرض الواجهة", "home")]]))

    elif data.startswith("menu_manage:") and is_admin(uid):
        key = data.split(":", 1)[1]
        if key not in set(UI_LABELS) | {"completed_count_button"}:
            await safe_edit(q, "الزر غير معروف.", reply_markup=kb([[btn("🔙 رجوع", "menu_button_manager")]])); return
        context.user_data["menu_manage_key"] = key
        label = ui_label(key) if key in UI_LABELS else get_setting("completed_count_button_name", "🛡️ عدد الطلبات المنجزة: {count}")
        rows = []
        if key in UI_LABELS:
            rows.append([btn("✏️ تعديل اسم الزر", "menu_rename:" + key)])
            rows.append([btn("🧭 تعديل القسم الذي يفتحه", "menu_action_list:" + key)])
        rows.append([btn("↕️ تغيير مكان الزر", "layout_choose:" + key)])
        rows.append([btn("🗑 حذف الزر من الواجهة", "menu_delete:" + key)])
        rows.append([btn("🔙 رجوع", "menu_button_manager")])
        await safe_edit(q, f"إدارة الزر: {label}\nاختر التعديل المطلوب:", reply_markup=kb(rows))

    elif data.startswith("menu_rename:") and is_admin(uid):
        key = data.split(":", 1)[1]
        if key not in UI_LABELS:
            await safe_edit(q, "هذا الزر لا يدعم تعديل الاسم من هنا.", reply_markup=kb([[btn("🔙 رجوع", "menu_button_manager")]])); return
        context.user_data["state"] = "menu_button_rename"
        context.user_data["menu_rename_key"] = key
        await safe_edit(q, f"أرسل الاسم الجديد للزر «{ui_label(key)}».\nاكتب إلغاء للتراجع.", reply_markup=kb([[btn("🔙 رجوع", "menu_button_manager")]]))

    elif data.startswith("menu_action_list:") and is_admin(uid):
        key = data.split(":", 1)[1]
        actions = {
            "services": "🛒 الخدمات والتطبيقات", "fund_channels": "📣 تمويل القنوات",
            "earn": "💎 تجميع النقاط", "transfer": "🔁 تحويل النقاط", "recharge": "🎟️ استخدام كود الشحن",
            "account": "💳 الحساب", "check_order": "🔎 فحص الطلب", "myorders": "📋 طلباتي",
            "terms": "⚠️ شروط الاستخدام", "platform:crypto": "🪙 العملات الرقمية",
            "orders_channel_open": "📣 قناة الطلبات", "support": "🆘 الدعم الفني", "admin": "⚙️ لوحة التحكم"
        }
        rows = [[btn(label, "menu_action_set:" + key + ":" + action)] for action, label in actions.items()]
        rows.append([btn("🔙 رجوع", "menu_manage:" + key)])
        await safe_edit(q, "اختر القسم/الوظيفة التي تريد أن يفتحها هذا الزر:", reply_markup=kb(rows))

    elif data.startswith("menu_action_set:") and is_admin(uid):
        parts = data.split(":", 2)
        if len(parts) != 3 or parts[1] not in UI_LABELS:
            await safe_edit(q, "تعذر ضبط وظيفة الزر.", reply_markup=kb([[btn("🔙 رجوع", "menu_button_manager")]])); return
        set_setting("home_action_" + parts[1], parts[2])
        await safe_edit(q, "✅ تم تغيير القسم الذي يفتحه الزر.", reply_markup=kb([[btn("🛠 متابعة إدارة القوائم والأزرار", "menu_button_manager")], [btn("👁 عرض الواجهة", "home")]]))

    elif data.startswith("menu_delete:") and is_admin(uid):
        key = data.split(":", 1)[1]
        if key not in set(UI_LABELS) | {"completed_count_button"}:
            await safe_edit(q, "الزر غير معروف.", reply_markup=kb([[btn("🔙 رجوع", "menu_button_manager")]])); return
        try:
            hidden = set(json.loads(get_setting("home_hidden_buttons", "[]")))
        except Exception:
            hidden = set()
        hidden.add(key)
        set_setting("home_hidden_buttons", json.dumps(sorted(hidden), ensure_ascii=False))
        layout = [[item for item in row if item != key] for row in get_home_layout()]
        layout = [row for row in layout if row]
        set_setting("home_button_layout", json.dumps(layout, ensure_ascii=False))
        await safe_edit(q, "🗑 تم حذف الزر من واجهة المستخدم. يمكنك إعادته من «إظهار زر محذوف».", reply_markup=kb([[btn("🛠 إدارة القوائم والأزرار", "menu_button_manager")], [btn("👁 عرض الواجهة", "home")]]))

    elif data == "home_layout_settings" and is_admin(uid):
        rows = [[btn("🔘 " + UI_LABELS[k][0], "layout_choose:" + k)] for k in UI_LABELS if k != "home_admin"]
        rows.append([btn("🛡️ عدد الطلبات المنجزة", "layout_choose:completed_count_button")])
        rows.append([btn("♻️ إعادة ترتيب الأزرار للوضع الافتراضي", "layout_reset")])
        rows.append([btn("🔙 لوحة التحكم", "admin")])
        await safe_edit(q, "🧩 التحكم بترتيب ودمج الأزرار\n\nاختر الزر الذي تريد نقله، ثم اختر رقم السطر. إذا اخترت سطراً فيه زر واحد فسيُدمج معه، والحد الأقصى زران في السطر.", reply_markup=kb(rows))

    elif data.startswith("layout_choose:") and is_admin(uid):
        key = data.split(":", 1)[1]
        valid = set(UI_LABELS) | {"completed_count_button"}
        if key not in valid or key == "home_admin":
            await safe_edit(q, "الزر غير صالح.", reply_markup=kb([[btn("🔙 رجوع", "home_layout_settings")]]))
            return
        context.user_data["layout_selected_key"] = key
        layout = get_home_layout()
        rows = []
        for idx, row in enumerate(layout, 1):
            names = [UI_LABELS[k][0] if k in UI_LABELS else "🛡️ عدد الطلبات المنجزة" for k in row]
            rows.append([btn(f"السطر {idx}: " + " + ".join(names), f"layout_move:{idx}")])
        rows.append([btn("⬆️ نقل لأعلى", "layout_action:up"), btn("⬇️ نقل لأسفل", "layout_action:down")])
        rows.append([btn("🧩 دمج فوق", "layout_action:mergeup"), btn("🧩 دمج تحت", "layout_action:mergedown")])
        rows.append([btn("➕ سطر جديد", "layout_move:new")])
        rows.append([btn("🔙 رجوع", "home_layout_settings")])
        label = UI_LABELS[key][0] if key in UI_LABELS else "🛡️ عدد الطلبات المنجزة"
        await safe_edit(q, f"اختر مكان الزر: {label}\n\nاختيار سطر يحتوي زرّاً واحداً يدمجهما في السطر نفسه.", reply_markup=kb(rows))

    elif data.startswith("layout_action:") and is_admin(uid):
        key = context.user_data.get("layout_selected_key")
        action = data.split(":", 1)[1]
        layout = get_home_layout()
        if not key or action not in {"up", "down", "mergeup", "mergedown"}:
            await safe_edit(q, "اختر الزر أولاً.", reply_markup=kb([[btn("🔙 رجوع", "home_layout_settings")]])); return
        src = next((i for i, row in enumerate(layout) if key in row), None)
        if src is None:
            layout.append([key]); src = len(layout)-1
        row = layout[src]
        row.remove(key)
        if not row: layout.pop(src)
        # Re-find source after removal; merge means place alongside a button in adjacent row.
        if action in ("up", "mergeup"):
            target = max(0, src-1)
        else:
            target = min(len(layout), src)
        if action.startswith("merge") and layout:
            target = max(0, min(len(layout)-1, target))
            if len(layout[target]) < 2:
                layout[target].append(key)
            else:
                layout.insert(target if action == "mergeup" else target+1, [key])
        else:
            layout.insert(target, [key])
        normalized=[]
        for r in layout:
            for i in range(0, len(r), 2): normalized.append(r[i:i+2])
        set_setting("home_button_layout", json.dumps(normalized, ensure_ascii=False))
        context.user_data.pop("layout_selected_key", None)
        await safe_edit(q, "✅ تم حفظ ترتيب الأزرار.", reply_markup=kb([[btn("🧩 متابعة الترتيب", "home_layout_settings")],[btn("👁 عرض الواجهة", "home")],[btn("🔙 لوحة التحكم", "admin")]]))

    elif data.startswith("layout_move:") and is_admin(uid):
        key = context.user_data.get("layout_selected_key")
        if not key:
            await safe_edit(q, "اختر الزر أولاً.", reply_markup=kb([[btn("🔙 رجوع", "home_layout_settings")]]))
            return
        layout = get_home_layout()
        target = data.split(":", 1)[1]
        if target == "new":
            layout.append([key])
        else:
            try:
                idx = int(target) - 1
                if idx < 0 or idx >= len(layout): raise ValueError
                # Remove selected button from its old row and discard empty rows.
                layout = [[k for k in row if k != key] for row in layout]
                layout = [row for row in layout if row]
                idx = min(idx, len(layout))
                if idx < len(layout) and len(layout[idx]) < 2:
                    layout[idx].append(key)
                else:
                    layout.insert(idx, [key])
            except (ValueError, IndexError):
                await safe_edit(q, "السطر المحدد غير صالح.", reply_markup=kb([[btn("🔙 رجوع", "home_layout_settings")]]))
                return
        # Normalize: max two buttons per row and ensure all known buttons remain.
        normalized = []
        for row in layout:
            for i in range(0, len(row), 2): normalized.append(row[i:i+2])
        set_setting("home_button_layout", json.dumps(normalized, ensure_ascii=False))
        context.user_data.pop("layout_selected_key", None)
        await safe_edit(q, "✅ تم نقل الزر وحفظ ترتيب الواجهة. افتح الواجهة الرئيسية لمشاهدة التغيير.", reply_markup=kb([[btn("🧩 متابعة الترتيب", "home_layout_settings")], [btn("👁 عرض الواجهة", "home")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "layout_reset" and is_admin(uid):
        set_setting("home_hidden_buttons", "[]")
        for k in UI_LABELS:
            set_setting("home_action_" + k, "")
        set_setting("home_button_layout", json.dumps(default_home_layout(), ensure_ascii=False))
        context.user_data.pop("layout_selected_key", None)
        await safe_edit(q, "✅ تمت إعادة ترتيب الأزرار للوضع الافتراضي.", reply_markup=kb([[btn("👁 عرض الواجهة", "home")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "interface_text_settings" and is_admin(uid):
        rows = []
        for key, (_, title) in UI_LABELS.items():
            rows.append([btn("🔘 " + title, "ui_edit:label:" + key)])
        for key, (_, title) in UI_MESSAGES.items():
            rows.append([btn("💬 " + title, "ui_edit:message:" + key)])
        rows += [[btn("📱 أسماء التطبيقات والأقسام", "platforms")], [btn("🔙 لوحة التحكم", "admin")]]
        await safe_edit(q, "📝 التحكم بأسماء الواجهة والكلايش\n\nاختر الاسم أو الكليشة التي تريد تعديلها. التغييرات تُحفظ في قاعدة البيانات وتبقى بعد إعادة تشغيل البوت.", reply_markup=kb(rows))

    elif data.startswith("ui_edit:") and is_admin(uid):
        parts = data.split(":", 2)
        if len(parts) != 3 or parts[1] not in ("label", "message"):
            await safe_edit(q, "خيار غير صالح.", reply_markup=admin_keyboard())
            return
        kind, key = parts[1], parts[2]
        catalog = UI_LABELS if kind == "label" else UI_MESSAGES
        if key not in catalog:
            await safe_edit(q, "العنصر غير موجود.", reply_markup=admin_keyboard())
            return
        setting_key = ("ui_label_" if kind == "label" else "ui_message_") + key
        current = get_setting(setting_key, catalog[key][0])
        context.user_data["state"] = "ui_text_edit"
        context.user_data["ui_text_setting_key"] = setting_key
        context.user_data["ui_text_kind"] = kind
        context.user_data["ui_text_title"] = catalog[key][1]
        await safe_edit(q, f"✏️ تعديل {catalog[key][1]}\n\nالنص الحالي:\n{current}\n\nأرسل النص الجديد. يمكن إرسال كليشة متعددة الأسطر. اكتب إلغاء للتراجع.\n\nالمتغيرات المتاحة حسب الرسالة: {{user_id}} أو {{id}} للمعرّف، {{username}} لاسم المستخدم، {{first_name}} للاسم، {{points}} للنقاط، {{order_id}} لرقم الطلب، {{service_name}} للخدمة، {{quantity}} للكمية، {{link}} للرابط، {{cost}} للتكلفة، {{count}} للعدد.", reply_markup=kb([[btn("🔙 إلغاء والعودة", "interface_text_settings")]]))

    elif data == "completed_count_label_edit" and is_admin(uid):
        context.user_data["state"] = "completed_count_button_name"
        current = get_setting("completed_count_button_name", "🛡️ عدد الطلبات المنجزة: {count}")
        await safe_edit(q, f"✏️ اسم زر الطلبات المنجزة\nالاسم الحالي: {current}\n\nأرسل الاسم الجديد. استخدم {{count}} مكان العدد الذي يتغير تلقائياً. مثال: 🏆 المنجزة {{count}}\nاكتب إلغاء للتراجع.", reply_markup=kb([[btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "maintenance" and is_admin(uid):
        enabled = "0" if get_setting("maintenance", "0") == "1" else "1"
        set_setting("maintenance", enabled)
        await safe_edit(q, f"🔧 تم {'تفعيل' if enabled == '1' else 'إيقاف'} وضع الصيانة.", reply_markup=kb([[btn("🔄 تبديل وضع الصيانة", "maintenance")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "order_mode_settings" and is_admin(uid):
        mode = get_setting("order_mode", "manual")
        await safe_edit(q, f"⚙️ وضع تنفيذ الطلبات\nالوضع الحالي: {'تلقائي عبر المزود' if mode == 'auto' else 'يدوي بموافقة الإدارة'}\n\nاختر الوضع:", reply_markup=kb([[btn("📝 يدوي بموافقتي", "order_mode:manual")], [btn("🤖 تلقائي عبر API المزود", "order_mode:auto")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data.startswith("order_mode:") and is_admin(uid):
        mode = data.split(":", 1)[1]
        if mode not in ("manual", "auto"):
            await safe_edit(q, "وضع غير صالح.", reply_markup=admin_keyboard())
            return
        set_setting("order_mode", mode)
        await safe_edit(q, f"✅ تم ضبط وضع الطلبات إلى: {'تلقائي عبر API المزود' if mode == 'auto' else 'يدوي بموافقة الإدارة'}", reply_markup=admin_keyboard())

    elif data == "stats" and is_admin(uid):
        with db() as c:
            users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
            orders = c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"]
            complete = c.execute(
                "SELECT COUNT(*) n FROM orders WHERE status='completed'"
            ).fetchone()["n"]
            providers = c.execute(
                "SELECT COUNT(*) n FROM providers"
            ).fetchone()["n"]
            services = c.execute(
                "SELECT COUNT(*) n FROM services"
            ).fetchone()["n"]

        await safe_edit(q, 
            f"📊 الإحصائيات\n👥 المستخدمون: {users}\n"
            f"📦 جميع الطلبات: {orders}\n"
            f"✅ المكتملة: {complete}\n"
            f"🌐 المزودون: {providers}\n"
            f"🛍 الخدمات: {services}",
            reply_markup=admin_keyboard()
        )

    elif data == "providers" and is_admin(uid):
        rows = [
            [btn(f"{p['name']} | {'🟢' if p['enabled'] else '🔴'}",
                 f"provider:{p['id']}")]
            for p in all_providers()
        ]
        rows += [
            [btn("➕ إضافة مزود", "provider_add")],
            [btn("🔙 لوحة التحكم", "admin")]
        ]
        await safe_edit(q, "🌐 مزودو API:", reply_markup=kb(rows))

    elif data == "provider_add" and is_admin(uid):
        context.user_data.clear()
        context.user_data["state"] = "provider_name"
        await safe_edit(q, "أرسل اسم المزود الجديد. بعد ذلك ستدخل رابط API الخاص به بنفسك.\n\nمثال: مزود الرشق الجديد\nاكتب إلغاء للتراجع.")

    elif data.startswith("provider:") and is_admin(uid):
        pid = int(data.split(":")[1])
        with db() as c:
            p = c.execute(
                "SELECT * FROM providers WHERE id=?", (pid,)
            ).fetchone()

        if not p:
            await safe_edit(q, "المزود غير موجود.")
            return

        await safe_edit(q, 
            f"🌐 {p['name']}\n"
            f"الرابط: {p['api_url']}\n"
            f"الحالة: {'مفعل' if p['enabled'] else 'معطل'}",
            reply_markup=kb([
                [btn("🧪 اختبار API", f"ptest:{pid}")],
                [btn("🔄 جلب خدمات المزود", f"psync:{pid}")],
                [btn("💳 فحص الرصيد", f"pbalance:{pid}")],
                [btn("✏️ تغيير اسم المزود", f"provider_edit_name:{pid}")],
                [btn("🔗 تغيير رابط API", f"provider_edit_url:{pid}")],
                [btn("🔑 تغيير مفتاح API", f"provider_edit_key:{pid}")],
                [btn("💵 تحديد هامش ربح هذا المزود", f"provider_margin:{pid}")],
                [btn("🔀 تفعيل/تعطيل", f"ptoggle:{pid}")],
                [btn("🗑 حذف المزود", f"pdelete:{pid}")],
                [btn("🔙 رجوع", "providers")]
            ])
        )

    elif data.startswith(("provider_edit_name:", "provider_edit_url:", "provider_edit_key:")) and is_admin(uid):
        action, raw_pid = data.split(":", 1)
        try:
            pid = int(raw_pid)
        except ValueError:
            await safe_edit(q, "رقم المزود غير صحيح.", reply_markup=kb([[btn("🔙 المزودون", "providers")]])); return
        with db() as c:
            p = c.execute("SELECT id,name,api_url FROM providers WHERE id=?", (pid,)).fetchone()
        if not p:
            await safe_edit(q, "المزود غير موجود.", reply_markup=kb([[btn("🔙 المزودون", "providers")]])); return
        field = {"provider_edit_name": "name", "provider_edit_url": "url", "provider_edit_key": "key"}[action]
        context.user_data["state"] = "provider_edit_" + field
        context.user_data["provider_edit_id"] = pid
        prompt = {
            "name": f"✏️ أرسل الاسم الجديد للمزود #{pid}.",
            "url": f"🔗 أرسل رابط API الجديد للمزود #{pid}.\nمثال: https://example.com/api/v2",
            "key": f"🔑 أرسل مفتاح API الجديد للمزود #{pid}. لن يتم عرض المفتاح الحالي حفاظاً على سريته."
        }[field]
        await safe_edit(q, prompt + "\nاكتب إلغاء للتراجع.", reply_markup=kb([[btn("🔙 إلغاء", f"provider:{pid}")]]))

    elif data == "ui_colors" and is_admin(uid):
        names = {"primary": "أزرق/أساسي", "success": "أخضر/أقسام", "danger": "أحمر/تنبيهات"}
        rows = []
        for key, title in (("ui_color_main", "لون الواجهة الرئيسية والأزرار الأساسية"), ("ui_color_sections", "لون الأقسام والأزرار الثانوية"), ("ui_color_alerts", "لون أزرار التنبيه/الحذف")):
            current = get_setting(key, {"ui_color_main":"primary", "ui_color_sections":"success", "ui_color_alerts":"danger"}[key])
            rows.append([btn(f"🎨 {title}: {names.get(current, current)}", "ui_color_pick:" + key)])
        rows += [[btn("👁 معاينة الواجهة", "home")], [btn("🔙 لوحة التحكم", "admin")]]
        await safe_edit(q, "🎨 تخصيص ألوان الأزرار\n\nاختر اللون لكل نوع. ملاحظة: تيليجرام يدعم ألوان الأزرار فقط في إصدارات Bot API والعملاء المتوافقة؛ قد تظهر الأزرار عادية في بعض الإصدارات.", reply_markup=kb(rows))

    elif data.startswith("ui_color_pick:") and is_admin(uid):
        key = data.split(":", 1)[1]
        if key not in ("ui_color_main", "ui_color_sections", "ui_color_alerts"):
            await safe_edit(q, "خيار لون غير صالح.", reply_markup=kb([[btn("🔙 رجوع", "ui_colors")]])); return
        rows = [[btn("🔵 أزرق / أساسي", f"ui_color_set:{key}:primary", "primary")], [btn("🟢 أخضر / نجاح", f"ui_color_set:{key}:success", "success")], [btn("🔴 أحمر / تنبيه", f"ui_color_set:{key}:danger", "danger")], [btn("🔙 رجوع", "ui_colors")]]
        await safe_edit(q, "اختر اللون الذي تريد تطبيقه:", reply_markup=kb(rows))

    elif data.startswith("ui_color_set:") and is_admin(uid):
        parts = data.split(":")
        if len(parts) != 3 or parts[1] not in ("ui_color_main", "ui_color_sections", "ui_color_alerts") or parts[2] not in ("primary", "success", "danger"):
            await safe_edit(q, "إعداد اللون غير صالح.", reply_markup=kb([[btn("🔙 رجوع", "ui_colors")]])); return
        set_setting(parts[1], parts[2])
        await safe_edit(q, "✅ تم حفظ اللون. افتح الواجهة مجدداً لمعاينة الأزرار.", reply_markup=kb([[btn("🎨 متابعة الألوان", "ui_colors")], [btn("👁 الواجهة الرئيسية", "home")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data.startswith("ptest:") and is_admin(uid):
        pid = int(data.split(":")[1])
        try:
            p = get_provider(pid)
            result = await api_call(p, "services")
            await safe_edit(q, 
                f"✅ اتصال ناجح.\nالخدمات: "
                f"{len(result) if isinstance(result, list) else 'غير معروف'}",
                reply_markup=admin_keyboard()
            )
        except Exception as exc:
            await safe_edit(q, 
                f"❌ فشل الاختبار: {str(exc)[:200]}",
                reply_markup=admin_keyboard()
            )

    elif data.startswith("psync:") and is_admin(uid):
        pid = int(data.split(":")[1])
        try:
            added, updated = await sync_provider(get_provider(pid))
            await safe_edit(q, 
                f"✅ انتهت المزامنة\nجديدة: {added}\nمحدثة: {updated}",
                reply_markup=admin_keyboard()
            )
        except Exception as exc:
            await safe_edit(q, 
                f"فشلت المزامنة: {str(exc)[:200]}",
                reply_markup=admin_keyboard()
            )

    elif data == "sync_all" and is_admin(uid):
        added = updated = 0
        errors = []

        for p in all_providers():
            if not p["enabled"]:
                continue
            try:
                a, u = await sync_provider(p)
                added += a
                updated += u
            except Exception as exc:
                errors.append(f"{p['name']}: {str(exc)[:80]}")

        message = f"🔄 المزامنة انتهت\nخدمات جديدة: {added}\nمحدثة: {updated}"
        if errors:
            message += "\n\n⚠️ أخطاء:\n" + "\n".join(errors[:5])

        await safe_edit(q, message, reply_markup=admin_keyboard())

    elif data.startswith("pbalance:") and is_admin(uid):
        pid = int(data.split(":")[1])
        try:
            result = await api_call(get_provider(pid), "balance")
            await safe_edit(q, 
                json.dumps(result, ensure_ascii=False)[:3000],
                reply_markup=admin_keyboard()
            )
        except Exception as exc:
            await safe_edit(q, 
                f"تعذر فحص الرصيد: {str(exc)[:200]}",
                reply_markup=admin_keyboard()
            )

    elif data == "balances" and is_admin(uid):
        results = []
        for p in all_providers():
            if not p["enabled"]:
                continue
            try:
                r = await api_call(p, "balance")
                results.append(f"🌐 {p['name']}: {json.dumps(r, ensure_ascii=False)[:250]}")
            except Exception as exc:
                results.append(f"❌ {p['name']}: {str(exc)[:100]}")

        await safe_edit(q, 
            "\n".join(results) or "لا يوجد مزودون مفعلون.",
            reply_markup=admin_keyboard()
        )

    elif data.startswith("ptoggle:") and is_admin(uid):
        pid = int(data.split(":")[1])
        with db() as c:
            c.execute(
                "UPDATE providers SET enabled=1-enabled WHERE id=?", (pid,)
            )
        await safe_edit(q, "تم تغيير حالة المزود.", reply_markup=admin_keyboard())

    elif data.startswith("pdelete:") and is_admin(uid):
        pid = int(data.split(":")[1])
        with db() as c:
            c.execute("DELETE FROM services WHERE provider_id=?", (pid,))
            c.execute("DELETE FROM providers WHERE id=?", (pid,))
        await safe_edit(q, "تم حذف المزود وخدماته.", reply_markup=admin_keyboard())

    elif data == "platforms" and is_admin(uid):
        rows = [[btn(label, f"platstat:{key}", "success")] for key, label in PLATFORMS.items()]
        rows.append([btn("🔙 رجوع", "admin")])
        await safe_edit(q, "🗂 اختر التطبيق الذي تريد إدارة خدماته وأقسامه:", reply_markup=kb(rows))

    elif data.startswith("platstat:") and is_admin(uid):
        platform = data.split(":", 1)[1]
        if platform not in PLATFORMS:
            await safe_edit(q, "التطبيق غير معروف.", reply_markup=admin_keyboard()); return
        with db() as c:
            rows = c.execute("SELECT id,name,category,price_usd,price_points,enabled,delivery_mode FROM services WHERE platform=? ORDER BY id DESC LIMIT 35", (platform,)).fetchall()
            sections = c.execute("SELECT id,name FROM service_sections WHERE platform=? AND enabled=1 ORDER BY name", (platform,)).fetchall()
        buttons = [
            [btn(f"{'🟢' if r['enabled'] else '🔴'} #{r['id']} {r['name'][:24]}", f"svcadmin:{r['id']}")]
            for r in rows
        ]
        buttons.extend([[btn("📁 قسم: " + sec['name'][:30], f"sectionview:{sec['id']}")] for sec in sections])
        buttons += [
            [btn("➕ إضافة قسم", f"sectionadd:{platform}"), btn("➕ خدمة يدوية", f"manualadd:{platform}")],
            [btn("✏️ تعديل اسم زر التطبيق", f"platformrename:{platform}")],
            [btn("📥 اختيار خدمة من المزود", f"providerpick:{platform}")],
            [btn("🔙 التطبيقات", "platforms")]
        ]
        await safe_edit(q, f"{PLATFORMS[platform]} — إدارة الخدمات\nاختر خدمة لتعديل الاسم والسعر والكمية والحالة، أو أضف خدمة/قسماً:", reply_markup=kb(buttons))

    elif data.startswith("platformrename:") and is_admin(uid):
        platform = data.split(":", 1)[1]
        if platform not in PLATFORMS: return
        context.user_data.clear(); context.user_data.update(state="platform_label", platform_label_key=platform)
        await safe_edit(q, f"أرسل الاسم الجديد لزر {PLATFORMS[platform]}.\nاكتب إلغاء للإلغاء.")

    elif data.startswith("sectionadd:") and is_admin(uid):
        platform = data.split(":", 1)[1]
        if platform not in PLATFORMS: return
        context.user_data.clear(); context.user_data.update(state="section_name", section_platform=platform)
        await safe_edit(q, f"أرسل اسم القسم الجديد داخل {PLATFORMS[platform]}.")

    elif data.startswith("manualadd:") and is_admin(uid):
        platform = data.split(":", 1)[1]
        if platform not in PLATFORMS: return
        context.user_data.clear(); context.user_data.update(state="manual_service_name", manual_platform=platform)
        await safe_edit(q, f"إضافة خدمة يدوية إلى {PLATFORMS[platform]}.\nأرسل اسم الخدمة.")

    elif data.startswith("providerpick:") and is_admin(uid):
        platform = data.split(":", 1)[1]
        providers = [p for p in all_providers() if p["enabled"] and not str(p["api_url"]).startswith("manual://")]
        buttons = [[btn("🌐 " + p["name"][:35], f"providerchoose:{platform}:{p['id']}")] for p in providers]
        buttons.append([btn("🔙 رجوع", f"platstat:{platform}")])
        await safe_edit(q, "اختر المزود الذي تريد استعراض خدماته ثم أضف الخدمة المطلوبة فقط:", reply_markup=kb(buttons))

    elif data.startswith("providerchoose:") and is_admin(uid):
        parts = data.split(":", 2)
        if len(parts) != 3: return
        platform = parts[1]
        try: pid = int(parts[2])
        except ValueError: return
        try:
            provider = get_provider(pid)
            catalog = await api_call(provider, "services")
            if not isinstance(catalog, list):
                detail = catalog.get("error") if isinstance(catalog, dict) else None
                raise RuntimeError(str(detail or "صيغة قائمة الخدمات غير معروفة")[:180])
            filtered = []
            valid_catalog = []
            for item in catalog:
                if not isinstance(item, dict): continue
                name = str(item.get("name", "")).strip()
                ext = str(item.get("service", "")).strip()
                if not name or not ext: continue
                valid_catalog.append(item)
                detected = detect_platform(item)
                if detected == platform or (platform == "other" and detected == "other"):
                    filtered.append(item)
            fallback_all = not filtered and bool(valid_catalog)
            if fallback_all:
                filtered = valid_catalog
            context.user_data[f"provider_catalog_{pid}_{platform}"] = filtered[:60]
            buttons = []
            for i, item in enumerate(filtered[:60]):
                try: rate = float(item.get("rate", 0) or 0)
                except (ValueError, TypeError): rate = 0
                buttons.append([btn(f"{str(item.get('name',''))[:28]} | تكلفة {rate:g}/1000", f"providerimport:{platform}:{pid}:{i}")])
            buttons.append([btn("🔙 المزودون", f"providerpick:{platform}")])
            notice = ("لم أستطع تحديد خدمات هذا التطبيق من الأسماء؛ أعرض أول الخدمات المتاحة لتختار منها يدوياً.\n" if fallback_all else "")
            await safe_edit(q, f"{notice}خدمات {provider['name']} لـ {PLATFORMS.get(platform, platform)}: {len(filtered[:60])}\nاختر خدمة لإضافتها للمتجر.", reply_markup=kb(buttons))
        except Exception as exc:
            await safe_edit(q, f"تعذر جلب خدمات المزود: {str(exc)[:180]}", reply_markup=kb([[btn("🔙 رجوع", f"providerpick:{platform}")]]))

    elif data.startswith("providerimport:") and is_admin(uid):
        parts = data.split(":", 3)
        if len(parts) != 4: return
        platform = parts[1]
        try: pid, index = int(parts[2]), int(parts[3])
        except ValueError: return
        catalog = context.user_data.get(f"provider_catalog_{pid}_{platform}", [])
        if index < 0 or index >= len(catalog):
            await safe_edit(q, "انتهت جلسة قائمة المزود. افتحها مجدداً.", reply_markup=kb([[btn("🔙 رجوع", f"providerpick:{platform}")]])); return
        item = catalog[index]
        try:
            external_id = str(item.get("service", "")).strip()
            name = str(item.get("name", "")).strip()[:200]
            rate = float(item.get("rate", 0) or 0)
            minimum = max(1, int(item.get("min", 1) or 1))
            maximum = max(minimum, int(item.get("max", 100000) or 100000))
            if not external_id or not name or not math.isfinite(rate) or rate < 0:
                raise ValueError("بيانات الخدمة غير صالحة")
            if rate == 0:
                with db() as c:
                    free_section_id = get_or_create_free_section(c, "free")
                    existing = c.execute("SELECT id FROM services WHERE provider_id=? AND external_id=?", (pid, external_id)).fetchone()
                    if existing:
                        sid = int(existing["id"])
                        c.execute("""UPDATE services SET platform='free',name=?,category=?,provider_rate=0,
                                     price_usd=0,price_points=0,min_qty=?,max_qty=?,section_id=?,delivery_mode='provider'
                                     WHERE id=?""", (name, str(item.get("category", ""))[:100], minimum, maximum, free_section_id, sid))
                    else:
                        cur = c.execute("""INSERT INTO services(provider_id,external_id,platform,name,category,provider_rate,
                                     price_usd,price_points,min_qty,max_qty,enabled,delivery_mode,section_id)
                                     VALUES(?,?,'free',?,?,0,0,0,?,?,1,'provider',?)""",
                                        (pid, external_id, name, str(item.get("category", ""))[:100], minimum, maximum, free_section_id))
                        sid = int(cur.lastrowid)
                await safe_edit(q, f"🎁 تمت إضافة الخدمة المجانية #{sid} إلى قسم الخدمات المجانية.\nالاسم: {name}\nالتكلفة: 0 نقطة.",
                                reply_markup=kb([[btn("🎁 عرض الخدمات المجانية", "platform:free")], [btn("🔙 رجوع", f"providerpick:{platform}")]]))
                return
            with db() as c:
                sections = c.execute("SELECT id,name FROM service_sections WHERE platform=? AND enabled=1 ORDER BY name", (platform,)).fetchall()
            buttons = [[btn("📁 " + sec["name"][:35], f"providersection:{platform}:{pid}:{index}:{sec['id']}")] for sec in sections]
            buttons.append([btn("بدون قسم", f"providersection:{platform}:{pid}:{index}:0")])
            buttons.append([btn("❌ إلغاء", f"providerpick:{platform}")])
            await safe_edit(q,
                f"اخترت الخدمة: {name}\nالتطبيق: {PLATFORMS.get(platform, platform)}\n"
                f"تكلفة المزود لكل 1000: ${rate:g}\nالكمية: {minimum} - {maximum}\n\n"
                "اختر القسم الذي تريد وضع الخدمة داخله:", reply_markup=kb(buttons))
        except Exception as exc:
            await safe_edit(q, f"تعذر تجهيز الخدمة: {str(exc)[:180]}", reply_markup=kb([[btn("🔙 رجوع", f"providerpick:{platform}")]]))

    elif data.startswith("providersection:") and is_admin(uid):
        parts = data.split(":", 4)
        if len(parts) != 5: return
        platform = parts[1]
        try:
            pid, index, section_id = int(parts[2]), int(parts[3]), int(parts[4])
        except ValueError:
            await safe_edit(q, "بيانات القسم غير صحيحة.", reply_markup=kb([[btn("🔙 رجوع", f"providerpick:{platform}")]])); return
        catalog = context.user_data.get(f"provider_catalog_{pid}_{platform}", [])
        if index < 0 or index >= len(catalog):
            await safe_edit(q, "انتهت جلسة قائمة المزود. افتحها مجدداً.", reply_markup=kb([[btn("🔙 رجوع", f"providerpick:{platform}")]])); return
        item = catalog[index]
        try:
            external_id = str(item.get("service", "")).strip()
            name = str(item.get("name", "")).strip()[:200]
            rate = float(item.get("rate", 0) or 0)
            minimum = max(1, int(item.get("min", 1) or 1))
            maximum = max(minimum, int(item.get("max", 100000) or 100000))
            if not external_id or not name or not math.isfinite(rate) or rate <= 0:
                raise ValueError("بيانات الخدمة المدفوعة غير صالحة؛ الخدمة المجانية تُضاف من خلال زر اختيار الخدمة")
            if section_id:
                with db() as c:
                    sec = c.execute("SELECT id FROM service_sections WHERE id=? AND platform=? AND enabled=1", (section_id, platform)).fetchone()
                if not sec: raise ValueError("القسم غير موجود ضمن هذا التطبيق")
            context.user_data.update({
                "state": "provider_service_price", "pending_provider_id": pid,
                "pending_platform": platform, "pending_external_id": external_id,
                "pending_service_name": name, "pending_provider_rate": rate,
                "pending_min": minimum, "pending_max": maximum,
                "pending_category": str(item.get("category", ""))[:100],
                "pending_section_id": section_id or None
            })
            await safe_edit(q,
                f"اخترت الخدمة: {name}\nالتطبيق: {PLATFORMS.get(platform, platform)}\n"
                f"تكلفة المزود لكل 1000: ${rate:g}\nالكمية: {minimum} - {maximum}\n\n"
                "أرسل سعر البيع الذي تريده لكل 1000 بالدولار (مثال: 1.50).\n"
                "اكتب إلغاء لإلغاء الإضافة.",
                reply_markup=kb([[btn("❌ إلغاء", f"providerpick:{platform}")]]))
        except Exception as exc:
            await safe_edit(q, f"تعذر تجهيز الخدمة: {str(exc)[:180]}", reply_markup=kb([[btn("🔙 رجوع", f"providerpick:{platform}")]]))

    elif data.startswith("sectionview:") and is_admin(uid):
        try: secid = int(data.split(":", 1)[1])
        except ValueError: return
        with db() as c:
            sec = c.execute("SELECT * FROM service_sections WHERE id=?", (secid,)).fetchone()
            linked = c.execute("SELECT id,name FROM services WHERE section_id=? ORDER BY id DESC LIMIT 20", (secid,)).fetchall()
        if not sec: await safe_edit(q, "القسم غير موجود.", reply_markup=admin_keyboard()); return
        rows = [[btn(f"🛠 #{r['id']} {r['name'][:28]}", f"svcadmin:{r['id']}")] for r in linked]
        rows += [
            [btn("📥 إضافة خدمة من المزود لهذا التطبيق", f"providerpick:{sec['platform']}")],
            [btn("✏️ تعديل اسم القسم", f"sectionrename:{secid}"), btn("🗑 حذف القسم", f"sectiondel:{secid}")],
            [btn("🔙 رجوع", f"platstat:{sec['platform']}")]
        ]
        await safe_edit(q, f"📁 القسم: {sec['name']}\nالتطبيق: {PLATFORMS.get(sec['platform'], sec['platform'])}\nالخدمات المرتبطة: {len(linked)}", reply_markup=kb(rows))

    elif data.startswith("sectionrename:") and is_admin(uid):
        try: secid = int(data.split(":", 1)[1])
        except ValueError: return
        context.user_data.clear(); context.user_data.update(state="section_rename", section_id=secid)
        await safe_edit(q, "أرسل الاسم الجديد للقسم.")

    elif data.startswith("sectiondel:") and is_admin(uid):
        try: secid = int(data.split(":", 1)[1])
        except ValueError: return
        with db() as c:
            sec = c.execute("SELECT platform FROM service_sections WHERE id=?", (secid,)).fetchone()
            c.execute("UPDATE services SET section_id=NULL WHERE section_id=?", (secid,))
            c.execute("DELETE FROM service_sections WHERE id=?", (secid,))
        await safe_edit(q, "تم حذف القسم.", reply_markup=kb([[btn("🔙 رجوع", f"platstat:{sec['platform']}")]] if sec else [[btn("لوحة التحكم", "admin")]]))

    elif data.startswith("svcadmin:") and is_admin(uid):
        try: sid = int(data.split(":", 1)[1])
        except ValueError: return
        with db() as c: svc = c.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()
        if not svc: await safe_edit(q, "الخدمة غير موجودة.", reply_markup=admin_keyboard()); return
        mode = "يدوية" if svc['delivery_mode'] == 'manual' else "عن طريق المزود"
        await safe_edit(q, f"🛠 إدارة الخدمة #{sid}\nالاسم: {svc['name']}\nالتطبيق: {PLATFORMS.get(svc['platform'], svc['platform'])}\nالقسم/الوصف: {svc['category'] or 'غير محدد'}\nسعر البيع/1000: ${float(svc['price_usd'] or 0):.6f}\nالنقاط/1000: {svc['price_points']}\nالكمية: {svc['min_qty']} - {svc['max_qty']}\nطريقة التنفيذ: {mode}\nالحالة: {'مفعلة' if svc['enabled'] else 'معطلة'}", reply_markup=kb([
            [btn("✏️ تعديل الاسم", f"svcedit:{sid}:name"), btn("✏️ تعديل الوصف/القسم", f"svcedit:{sid}:category")],
            [btn("💵 تعديل سعر الدولار/1000", f"svcedit:{sid}:price_usd"), btn("💎 تعديل النقاط/1000", f"svcedit:{sid}:price_points")],
            [btn("📉 تعديل أقل كمية", f"svcedit:{sid}:min_qty"), btn("📈 تعديل أكبر كمية", f"svcedit:{sid}:max_qty")],
            [btn("🔀 يدوي / مزود", f"svctogglemode:{sid}"), btn("🟢/🔴 تفعيل/تعطيل", f"stoggle:{sid}")],
            [btn("🔙 رجوع للتطبيق", f"platstat:{svc['platform']}")]
        ]))

    elif data.startswith("svcedit:") and is_admin(uid):
        parts = data.split(":", 2)
        if len(parts) != 3: return
        try: sid = int(parts[1])
        except ValueError: return
        field = parts[2]
        allowed = {"name", "category", "price_usd", "price_points", "min_qty", "max_qty"}
        if field not in allowed: return
        context.user_data.clear(); context.user_data.update(state="service_edit", edit_service_id=sid, edit_service_field=field)
        prompts = {"name":"أرسل الاسم الجديد للخدمة.", "category":"أرسل اسم القسم أو وصف الخدمة.", "price_usd":"أرسل سعر البيع بالدولار لكل 1000 وحدة (رقم أكبر من صفر).", "price_points":"أرسل عدد النقاط لكل 1000 وحدة (عدد صحيح أكبر من صفر).", "min_qty":"أرسل أقل كمية مسموحة (عدد صحيح).", "max_qty":"أرسل أكبر كمية مسموحة (عدد صحيح)."}
        await safe_edit(q, prompts[field] + "\nاكتب إلغاء للرجوع.")

    elif data.startswith("svctogglemode:") and is_admin(uid):
        try: sid = int(data.split(":", 1)[1])
        except ValueError: return
        with db() as c:
            svc = c.execute("""
                SELECT s.delivery_mode,s.platform,s.provider_id,p.api_url,p.enabled AS provider_enabled
                FROM services s JOIN providers p ON p.id=s.provider_id WHERE s.id=?
            """, (sid,)).fetchone()
        if svc:
            new_mode = "manual" if svc['delivery_mode'] != "manual" else "provider"
            if new_mode == "provider" and (str(svc['api_url'] or '').startswith('manual://') or not svc['provider_enabled']):
                await safe_edit(q, "لا يمكن تفعيل التنفيذ عبر المزود لهذه الخدمة: اربطها بمزود API حقيقي ومفعّل أولاً.", reply_markup=kb([[btn("🔙 إدارة الخدمة", f"svcadmin:{sid}")]]))
                return
            with db() as c:
                c.execute("UPDATE services SET delivery_mode=? WHERE id=?", (new_mode, sid))
            await safe_edit(q, "تم تغيير طريقة التنفيذ إلى " + ("يدوي" if new_mode == "manual" else "المزود") + ".", reply_markup=kb([[btn("🔙 إدارة الخدمة", f"svcadmin:{sid}")]]))

    elif data == "manage_services" and is_admin(uid):
        with db() as c:
            rows = c.execute("SELECT id,name,platform,enabled FROM services ORDER BY id DESC LIMIT 40").fetchall()
        buttons = [[btn(f"{'🟢' if r['enabled'] else '🔴'} #{r['id']} {r['name'][:28]}", f"svcadmin:{r['id']}")] for r in rows]
        buttons.append([btn("🔙 رجوع", "admin")])
        await safe_edit(q, "إدارة الخدمات: اضغط على أي خدمة لتعديل الاسم والسعر والكمية وطريقة التنفيذ.", reply_markup=kb(buttons))

    elif data.startswith("stoggle:") and is_admin(uid):
        sid = int(data.split(":", 1)[1])
        with db() as c:
            c.execute("UPDATE services SET enabled=1-enabled WHERE id=?", (sid,))
        await safe_edit(q, "تم تحديث حالة الخدمة.", reply_markup=kb([[btn("🔙 إدارة الخدمة", f"svcadmin:{sid}")], [btn("🔙 لوحة التحكم", "admin")]]))

    elif data == "pricing" and is_admin(uid):
        await safe_edit(q, 
            f"💵 إعدادات الأسعار\n"
            f"الربح: {get_setting('profit_percent')}%\n"
            f"النقاط لكل دولار: {get_setting('points_per_usd')}\n"
            f"وضع السعر: {get_setting('currency_mode')}",
            reply_markup=kb([
                [btn("✏️ نسبة الربح", "edit_profit")],
                [btn("✏️ النقاط لكل دولار", "edit_points_usd")],
                [btn("💎 التسعير بالنقاط", "mode:points")],
                [btn("💵 عرض الدولار", "mode:usd")],
                [btn("🔄 إعادة حساب الأسعار", "reprice")],
                [btn("🔙 رجوع", "admin")]
            ])
        )

    elif data == "edit_profit" and is_admin(uid):
        context.user_data["state"] = "profit"
        await safe_edit(q, "أرسل نسبة الربح المئوية، مثال: 25")

    elif data == "edit_points_usd" and is_admin(uid):
        context.user_data["state"] = "points_usd"
        await safe_edit(q, "أرسل عدد النقاط مقابل دولار واحد.")

    elif data.startswith("mode:") and is_admin(uid):
        mode = data.split(":")[1]
        if mode in ("points", "usd"):
            set_setting("currency_mode", mode)
        notice = ("تم تفعيل عرض الأسعار بالدولار. تنبيه: لا يوجد رصيد دولار مستقل حالياً؛ سيُخصم من المستخدم ما يعادل السعر بالنقاط." if mode == "usd" else "تم تفعيل التسعير بالنقاط.")
        await safe_edit(q, notice, reply_markup=admin_keyboard())

    elif data == "reprice" and is_admin(uid):
        profit = max(0, float(get_setting("profit_percent", "20")))
        ppu = max(0.000001, float(get_setting("points_per_usd", "1000")))

        with db() as c:
            rows = c.execute("SELECT s.id,s.provider_rate,p.profit_percent FROM services s JOIN providers p ON p.id=s.provider_id").fetchall()
            for r in rows:
                provider_profit = r["profit_percent"]
                effective_profit = profit if provider_profit is None or float(provider_profit) < 0 else max(0.0, float(provider_profit))
                price = r["provider_rate"] * (1 + effective_profit / 100)
                c.execute("""
                UPDATE services SET price_usd=?,price_points=?
                WHERE id=?
                """, (
                    round(price, 6),
                    max(0, int(math.ceil(price * ppu))),
                    r["id"]
                ))

        await safe_edit(q, "تمت إعادة حساب أسعار الخدمات.", reply_markup=admin_keyboard())

    elif data == "point_settings" and is_admin(uid):
        await safe_edit(q, 
            "💎 إعدادات النقاط:",
            reply_markup=kb([
                [btn("✏️ مكافأة الدعوة", "edit_ref_reward")],
                [btn("✏️ الهدية اليومية", "edit_daily")],
                [btn("✏️ أقل تحويل", "edit_transfer_min")],
                [btn("✏️ النقاط لكل نجمة", "edit_star_rate")],
                [btn("🔙 رجوع", "admin")]
            ])
        )

    elif data in (
        "edit_ref_reward", "edit_daily", "edit_transfer_min", "edit_star_rate"
    ) and is_admin(uid):
        context.user_data["state"] = data
        await safe_edit(q, "أرسل القيمة الرقمية الجديدة.")

    elif data == "admins" and is_admin(uid):
        with db() as c:
            rows = c.execute("SELECT user_id FROM admins").fetchall()

        buttons = [
            [btn(f"👮 {r['user_id']} — إزالة", f"admin_remove:{r['user_id']}")]
            for r in rows if r["user_id"] != OWNER_ID
        ]
        buttons += [
            [btn("➕ إضافة مشرف", "admin_add")],
            [btn("🔙 رجوع", "admin")]
        ]
        await safe_edit(q, "👮 إدارة المشرفين:", reply_markup=kb(buttons))

    elif data == "admin_add" and is_admin(uid):
        context.user_data["state"] = "add_admin"
        await safe_edit(q, "أرسل Telegram ID للمشرف الجديد.")

    elif data.startswith("admin_remove:") and is_admin(uid):
        target = int(data.split(":")[1])
        if target == OWNER_ID:
            await q.answer("لا يمكن إزالة المالك.", show_alert=True)
            return
        with db() as c:
            c.execute("DELETE FROM admins WHERE user_id=?", (target,))
        await safe_edit(q, "تمت إزالة المشرف.", reply_markup=admin_keyboard())

    elif data == "paid_gate_settings" and is_admin(uid):
        enabled = get_setting("paid_gate_enabled", "0") == "1"
        price = get_setting("paid_gate_stars", "10")
        await safe_edit(q, 
            f"💫 الدخول المدفوع: {'مفعل' if enabled else 'معطل'}\nسعر الدخول: {price} نجمة\n\nاختر إجراءً:",
            reply_markup=kb([
                [btn("🔀 تفعيل/تعطيل الدفع", "paid_gate_toggle")],
                [btn("💫 تحديد سعر الدخول", "paid_gate_price")],
                [btn("🔙 رجوع", "admin")],
            ])
        )

    elif data == "paid_gate_toggle" and is_admin(uid):
        value = "0" if get_setting("paid_gate_enabled", "0") == "1" else "1"
        set_setting("paid_gate_enabled", value)
        await safe_edit(q, 
            f"تم {'تفعيل' if value == '1' else 'تعطيل'} الدخول المدفوع.",
            reply_markup=admin_keyboard()
        )

    elif data == "paid_gate_price" and is_admin(uid):
        context.user_data["state"] = "paid_gate_price"
        await safe_edit(q, "أرسل سعر الدخول بعدد نجوم Telegram (عدد صحيح أكبر من صفر).")

    elif data == "completed_channel" and is_admin(uid):
        context.user_data["state"] = "completed_channel"
        current = get_setting("completed_orders_channel", "") or "غير محددة"
        await safe_edit(q, 
            f"قناة الطلبات المكتملة الحالية: {current}\nأرسل @username أو chat_id للقناة. يجب إضافة البوت إليها والسماح له بإرسال الرسائل. أرسل 0 لإلغاء الإعداد."
        )

    elif data == "force_channels" and is_admin(uid):
        with db() as c:
            channels = c.execute(
                "SELECT * FROM forced_channels ORDER BY chat_id"
            ).fetchall()

        buttons = [
            [btn(f"🗑 {ch['title'] or ch['chat_id']}", f"fc_remove:{ch['chat_id']}")]
            for ch in channels
        ]
        buttons += [
            [btn("➕ إضافة قناة", "fc_add")],
            [btn("🔒 الاشتراك الإجباري دائم التفعيل", "fc_info")],
            [btn("🔙 رجوع", "admin")]
        ]
        await safe_edit(q, "📢 إعدادات الاشتراك الإجباري:", reply_markup=kb(buttons))

    elif data == "fc_add" and is_admin(uid):
        context.user_data["state"] = "fc_chat"
        await safe_edit(q, 
            "أرسل @username أو chat_id للقناة. "
            "يجب أن يكون البوت مشرفاً فيها حتى يتحقق من الاشتراك."
        )

    elif data.startswith("fc_remove:") and is_admin(uid):
        target = data.split(":", 1)[1]
        with db() as c:
            c.execute("DELETE FROM forced_channels WHERE chat_id=?", (target,))
        await safe_edit(q, "تم حذف القناة.", reply_markup=admin_keyboard())

    elif data in ("fc_toggle", "fc_info") and is_admin(uid):
        set_setting("force_subscription_enabled", "1")
        await safe_edit(q,
            "🔒 الاشتراك الإجباري دائم التفعيل ولا يتأثر بإعدادات الدفع بالنجوم. أضف القناة المطلوبة من هذه القائمة.",
            reply_markup=admin_keyboard()
        )

    elif data == "tasks" and is_admin(uid):
        with db() as c:
            rows = c.execute(
                "SELECT * FROM channel_tasks ORDER BY id DESC"
            ).fetchall()

        buttons = [
            [btn(
                f"{'🟢' if t['enabled'] else '🔴'} {t['title'][:25]}",
                f"task_toggle:{t['id']}"
            )]
            for t in rows
        ]
        buttons += [
            [btn("➕ إضافة مهمة قناة", "task_add")],
            [btn("🔙 رجوع", "admin")]
        ]
        await safe_edit(q, "🎯 إدارة مهام تجميع النقاط:", reply_markup=kb(buttons))

    elif data == "tasks":
        with db() as c:
            tasks = c.execute(
                "SELECT * FROM channel_tasks WHERE enabled=1"
            ).fetchall()

        buttons = [
            [btn(
                (f"📢 {t['title']} (+{t['reward']})" + (f" [{int(t['completed_count'] or 0)}/{int(t['target_quantity'])}]" if "target_quantity" in t.keys() and int(t['target_quantity'] or 0) > 0 else ""))[:60],
                f"task_claim:{t['id']}"
            )]
            for t in tasks
        ]
        buttons.append([btn("🔙 رجوع", "earn")])
        await safe_edit(q, "اختر مهمة:", reply_markup=kb(buttons))

    elif data == "task_add" and is_admin(uid):
        context.user_data["state"] = "task_chat"
        await safe_edit(q, "أرسل معرف القناة أو رابطها.")

    elif data.startswith("task_toggle:") and is_admin(uid):
        tid = int(data.split(":")[1])
        with db() as c:
            c.execute(
                "UPDATE channel_tasks SET enabled=1-enabled WHERE id=?", (tid,)
            )
        await safe_edit(q, "تم تحديث المهمة.", reply_markup=admin_keyboard())

    elif data.startswith("task_claim:"):
        tid = int(data.split(":")[1])
        with db() as c:
            task = c.execute(
                "SELECT * FROM channel_tasks WHERE id=? AND enabled=1", (tid,)
            ).fetchone()
            claimed = c.execute(
                "SELECT 1 FROM task_claims WHERE user_id=? AND task_id=?",
                (uid, tid)
            ).fetchone()

        if not task:
            await safe_edit(q, "المهمة غير متاحة.")
            return
        if claimed:
            await safe_edit(q, "لقد حصلت على مكافأة هذه المهمة مسبقاً.")
            return
        if "owner_id" in task.keys() and int(task["owner_id"] or 0) == uid:
            await safe_edit(q, "لا يمكنك جمع نقاط من حملة قناتك الخاصة.", reply_markup=kb([[btn("🔙 رجوع", "earn")]]))
            return

        try:
            member = await context.bot.get_chat_member(
                task["chat_id"], uid
            )
            if member.status in ("left", "kicked", "banned"):
                await safe_edit(q, 
                    "❌ اشترك بالقناة أولاً ثم حاول مجدداً.",
                    reply_markup=kb([[btn("🔙 رجوع", "earn")]])
                )
                return

            with db() as c:
                # Re-check inside the transaction to prevent exceeding the funded quota.
                live_task = c.execute("SELECT * FROM channel_tasks WHERE id=? AND enabled=1", (tid,)).fetchone()
                if not live_task:
                    await safe_edit(q, "⏹️ اكتمل تمويل هذه القناة ولم تعد المهمة متاحة.", reply_markup=kb([[btn("🔙 رجوع", "earn")]]))
                    return
                funded_order_id = int(live_task["funding_order_id"] or 0) if "funding_order_id" in live_task.keys() else 0
                if funded_order_id:
                    order = c.execute("SELECT * FROM channel_funding_orders WHERE id=? AND status='active'", (funded_order_id,)).fetchone()
                    if not order or int(live_task["completed_count"] or 0) >= int(live_task["target_quantity"] or 0):
                        c.execute("UPDATE channel_tasks SET enabled=0 WHERE id=?", (tid,))
                        await safe_edit(q, "⏹️ اكتمل تمويل هذه القناة ولم تعد المهمة متاحة.", reply_markup=kb([[btn("🔙 رجوع", "earn")]]))
                        return
                # Old non-funded tasks retain their legacy per-member charging.
                owner_id = int(live_task["owner_id"] or 0) if "owner_id" in live_task.keys() else 0
                member_price = int(live_task["member_price"] or 0) if "member_price" in live_task.keys() else 0
                if owner_id > 0 and owner_id != uid and member_price > 0 and not funded_order_id:
                    charged = c.execute("UPDATE users SET points=points-? WHERE user_id=? AND points>=?", (member_price, owner_id, member_price))
                    if charged.rowcount != 1:
                        c.execute("UPDATE channel_tasks SET enabled=0 WHERE id=?", (tid,))
                        await safe_edit(q, "⏸️ توقفت هذه الحملة مؤقتاً لنفاد رصيد صاحب القناة. يرجى اختيار مهمة أخرى.", reply_markup=kb([[btn("🔙 رجوع", "earn")]]))
                        return
                try:
                    c.execute("INSERT INTO task_claims(user_id,task_id,created) VALUES(?,?,?)", (uid, tid, datetime.now(timezone.utc).isoformat()))
                except sqlite3.IntegrityError:
                    await safe_edit(q, "لقد حصلت على مكافأة هذه المهمة مسبقاً.", reply_markup=kb([[btn("🔙 رجوع", "earn")]]))
                    return
                if funded_order_id:
                    # Atomic conditional increment ensures the campaign never exceeds its target.
                    changed = c.execute("""UPDATE channel_tasks SET completed_count=completed_count+1
                        WHERE id=? AND enabled=1 AND completed_count < target_quantity""", (tid,))
                    if changed.rowcount != 1:
                        c.execute("DELETE FROM task_claims WHERE user_id=? AND task_id=?", (uid, tid))
                        await safe_edit(q, "⏹️ اكتمل تمويل هذه القناة ولم تعد المهمة متاحة.", reply_markup=kb([[btn("🔙 رجوع", "earn")]]))
                        return
                    new_count = int(c.execute("SELECT completed_count FROM channel_tasks WHERE id=?", (tid,)).fetchone()["completed_count"])
                    target_count = int(live_task["target_quantity"] or 0)
                    c.execute("UPDATE channel_funding_orders SET completed_count=? WHERE id=? AND status='active'", (new_count, funded_order_id))
                    if new_count >= target_count:
                        c.execute("UPDATE channel_tasks SET enabled=0,completed_count=? WHERE id=?", (target_count, tid))
                        c.execute("UPDATE channel_funding_orders SET status='completed',completed_count=? WHERE id=? AND status='active'", (target_count, funded_order_id))
                c.execute("UPDATE users SET points=points+? WHERE user_id=?", (int(live_task["reward"]), uid))

            await safe_edit(q, 
                f"✅ تم التحقق من اشتراكك!\n🎁 حصلت على {live_task['reward']} نقطة.",
                reply_markup=kb([[btn("🔙 رجوع", "earn")]])
            )
        except TelegramError:
            await safe_edit(q, 
                "تعذر التحقق من الاشتراك. تأكد أن البوت يستطيع الوصول إلى القناة.",
                reply_markup=kb([[btn("🔙 رجوع", "earn")]])
            )

    elif data.startswith("check_order"):
        context.user_data["state"] = "check_order"
        await safe_edit(q, "أرسل رقم الطلب للتحقق من حالته.")

    else:
        # Keep unsupported callback identifiers visible in logs so a missing
        # handler can be diagnosed instead of silently masking the real cause.
        log.warning("Unhandled callback_data=%r from user_id=%s", data, uid)
        await safe_edit(q,
            "⚠️ هذا الزر لا يملك إجراءً مفعّلاً في هذه النسخة. تم تسجيل معرّف الزر للتشخيص.\n"
            f"معرّف الزر: {data[:80]}",
            reply_markup=(admin_keyboard() if is_admin(uid) else home_keyboard(uid))
        )


# =========================================================
# TEXT INPUT HANDLER
# =========================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.effective_message:
        return
    uid = user.id
    register_user(user)
    state = context.user_data.get("state")
    if state == "support_message":
        message_text = (update.effective_message.text or "").strip()
        if message_text.lower() in ("إلغاء", "الغاء", "/cancel"):
            context.user_data.pop("state", None)
            await update.effective_message.reply_text("تم إلغاء الرسالة.", reply_markup=home_keyboard(uid))
            return
        context.user_data.pop("state", None)
        try:
            await context.bot.send_message(OWNER_ID, f"🆘 رسالة دعم فني\nالمستخدم: {uid} (@{update.effective_user.username or 'بدون'})\n\n{message_text}", reply_markup=kb([[btn("👤 إدارة العملاء", "users")], [btn("⚙️ لوحة التحكم", "admin")]]))
            await update.effective_message.reply_text("✅ وصلت رسالتك إلى الإدارة.", reply_markup=home_keyboard(uid))
        except TelegramError:
            await update.effective_message.reply_text("⚠️ تعذر إرسال الرسالة حالياً. حاول لاحقاً.", reply_markup=home_keyboard(uid))
        return

    if state == "api_link_request_details":
        details = (update.effective_message.text or "").strip()
        if details.lower() in ("إلغاء", "الغاء", "/cancel"):
            context.user_data.pop("state", None)
            await update.effective_message.reply_text("تم إلغاء طلب الربط.", reply_markup=home_keyboard(uid))
            return
        context.user_data.pop("state", None)
        if OWNER_ID > 0:
            try:
                await context.bot.send_message(OWNER_ID, f"🔗 طلب ربط API جديد\nالمستخدم: {uid} (@{update.effective_user.username or 'بدون'})\nالتفاصيل: {details}", reply_markup=kb([[btn("👤 فتح إدارة العملاء", "users")], [btn("⚙️ لوحة التحكم", "admin")]]))
            except TelegramError:
                log.exception("Failed to notify owner about API link request")
        await update.effective_message.reply_text("✅ تم إرسال طلب الربط للإدارة وهو الآن قيد المراجعة.", reply_markup=home_keyboard(uid))
        return
    text = (update.effective_message.text or "").strip()

    if not await subscription_gate(update, context):
        return

    # Recharge-code administration and redemption are handled before other states.
    if state in ("recharge_code_points", "recharge_code_count") and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel", "/cancel"):
            context.user_data.pop("state", None)
            context.user_data.pop("recharge_code_points", None)
            await update.effective_message.reply_text("تم إلغاء إنشاء الأكواد.", reply_markup=admin_keyboard())
            return
        if state == "recharge_code_points":
            try:
                points = int(text.replace(",", "").replace(" ", ""))
                if not 1 <= points <= 1_000_000_000:
                    raise ValueError
            except ValueError:
                await update.effective_message.reply_text("أرسل عدد نقاط صحيحاً من 1 إلى 1,000,000,000 أو اكتب إلغاء.")
                return
            context.user_data["recharge_code_points"] = points
            context.user_data["state"] = "recharge_code_count"
            await update.effective_message.reply_text(f"كل كود سيمنح {points} نقطة. كم كوداً تريد إنشاءه؟ أرسل عدداً من 1 إلى 100.")
            return
        if state == "recharge_code_count":
            try:
                count = int(text)
                if not 1 <= count <= 100:
                    raise ValueError
            except ValueError:
                await update.effective_message.reply_text("أرسل عدداً صحيحاً من 1 إلى 100.")
                return
            points = int(context.user_data.get("recharge_code_points", 0))
            if points <= 0:
                context.user_data.pop("state", None)
                await update.effective_message.reply_text("انتهت جلسة الإنشاء. ابدأ من جديد.", reply_markup=admin_keyboard())
                return
            codes = []
            now = datetime.now(timezone.utc).isoformat()
            try:
                with db() as c:
                    c.execute("BEGIN IMMEDIATE")
                    for _ in range(count):
                        # Generate high-entropy, readable, uppercase one-time codes.
                        code = secrets.token_hex(6).upper()
                        while c.execute("SELECT 1 FROM recharge_codes WHERE code=?", (code,)).fetchone():
                            code = secrets.token_hex(6).upper()
                        c.execute("INSERT INTO recharge_codes(code,points,created_by,created) VALUES(?,?,?,?)", (code, points, uid, now))
                        codes.append(code)
            except Exception:
                log.exception("Failed to create recharge codes")
                await update.effective_message.reply_text("❌ تعذر إنشاء الأكواد بسبب خطأ في قاعدة البيانات. لم يتم تأكيد الإنشاء؛ حاول مجدداً.", reply_markup=admin_keyboard())
                context.user_data.pop("state", None)
                context.user_data.pop("recharge_code_points", None)
                return
            context.user_data.pop("state", None)
            context.user_data.pop("recharge_code_points", None)
            code_lines = "\n".join(f"`{code}`" for code in codes)
            await update.effective_message.reply_text(
                f"✅ تم إنشاء {len(codes)} كود شحن بنجاح.\nقيمة كل كود: {points} نقطة\n\n{code_lines}\n\nكل كود صالح للاستخدام مرة واحدة فقط.",
                parse_mode="Markdown",
                reply_markup=kb([[btn("🎟️ إدارة كودات الشحن", "recharge_codes_admin")], [btn("🔙 لوحة الإدارة", "admin")]])
            )
            return

    if state == "redeem_recharge_code":
        code = re.sub(r"\s+", "", text).upper()
        if text.casefold() in ("إلغاء", "الغاء", "cancel", "/cancel"):
            context.user_data.pop("state", None)
            await update.effective_message.reply_text("تم إلغاء استخدام كود الشحن.", reply_markup=home_keyboard(uid))
            return
        if not re.fullmatch(r"[A-F0-9]{24}", code):
            await update.effective_message.reply_text("❌ صيغة الكود غير صحيحة. أرسل كود الشحن كما استلمته أو اكتب إلغاء.")
            return
        try:
            with db() as c:
                c.execute("BEGIN IMMEDIATE")
                row = c.execute("SELECT points,redeemed_by FROM recharge_codes WHERE code=?", (code,)).fetchone()
                if not row:
                    c.rollback()
                    await update.effective_message.reply_text("❌ كود الشحن غير صحيح.", reply_markup=home_keyboard(uid))
                    context.user_data.pop("state", None)
                    return
                if row["redeemed_by"] is not None:
                    c.rollback()
                    await update.effective_message.reply_text("⚠️ هذا الكود مستخدم مسبقاً ولا يمكن استخدامه مرة ثانية.", reply_markup=home_keyboard(uid))
                    context.user_data.pop("state", None)
                    return
                points = int(row["points"])
                cur = c.execute("UPDATE recharge_codes SET redeemed_by=?,redeemed_at=? WHERE code=? AND redeemed_by IS NULL", (uid, datetime.now(timezone.utc).isoformat(), code))
                if cur.rowcount != 1:
                    c.rollback()
                    await update.effective_message.reply_text("⚠️ تم استخدام هذا الكود بالفعل. لا يمكن استخدامه مرة أخرى.", reply_markup=home_keyboard(uid))
                    context.user_data.pop("state", None)
                    return
                cur = c.execute("UPDATE users SET points=points+? WHERE user_id=?", (points, uid))
                if cur.rowcount != 1:
                    c.rollback()
                    await update.effective_message.reply_text("❌ لم يتم العثور على حسابك. أرسل /start ثم حاول مجدداً.", reply_markup=home_keyboard(uid))
                    context.user_data.pop("state", None)
                    return
            context.user_data.pop("state", None)
            await update.effective_message.reply_text(f"🎉 تم تفعيل كود الشحن بنجاح!\n💎 أُضيف إلى رصيدك: {points} نقطة\n💰 رصيدك الحالي: {balance(uid)} نقطة", reply_markup=home_keyboard(uid))
        except Exception:
            log.exception("Recharge code redemption failed for user %s", uid)
            context.user_data.pop("state", None)
            await update.effective_message.reply_text("❌ حدث خطأ مؤقت ولم يتم تأكيد استخدام الكود. تحقق من رصيدك قبل إعادة المحاولة.", reply_markup=home_keyboard(uid))
        return

    if not state:
        await update.effective_message.reply_text(
            "استخدم الأزرار الموجودة في القائمة.",
            reply_markup=home_keyboard(uid)
        )
        return

    if state == "payment_details_text" and is_admin(uid):
        method = context.user_data.get("payment_details_method")
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        if method not in MANUAL_PAYMENT_METHODS or not text:
            await update.effective_message.reply_text("أرسل تعليمات دفع صحيحة أو اكتب إلغاء.")
            return
        set_setting("payment_details_" + method, text[:3500])
        context.user_data.clear()
        await update.effective_message.reply_text("✅ تم حفظ بيانات طريقة الدفع.", reply_markup=admin_keyboard())
        return

    if state == "api_stars_rate_edit" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        try:
            rate = int(text)
            if not 1 <= rate <= 100000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل عدداً صحيحاً من 1 إلى 100000.")
            return
        set_setting("api_stars_rate", str(rate))
        context.user_data.clear()
        await update.effective_message.reply_text(f"✅ تم الحفظ: كل نجمة = {rate} رصيد API.", reply_markup=kb([[btn("⭐ إعدادات شحن API", "api_stars_admin")],[btn("🔙 لوحة الإدارة", "admin")]]))
        return

    if state == "api_stars_packages_edit" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        try:
            vals = [int(x.strip()) for x in text.split(",")]
            if not vals or len(vals) > 20 or any(n < 100 or n > 100000 for n in vals) or len(set(vals)) != len(vals):
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("صيغة غير صحيحة. الحد الأدنى 100 نجمة والحد الأقصى 100000 نجمة، وحتى 20 باقة مختلفة. مثال: 100,500,1000,5000,10000,50000,100000.")
            return
        set_setting("api_stars_packages", ",".join(map(str, sorted(vals))))
        context.user_data.clear()
        await update.effective_message.reply_text("✅ تم حفظ الباقات: " + ", ".join(map(str, sorted(vals))), reply_markup=kb([[btn("⭐ إعدادات شحن API", "api_stars_admin")],[btn("🔙 لوحة الإدارة", "admin")]]))
        return

    if state == "manual_amount":
        try:
            amount = float(text.replace(",", ".").replace("$", "").strip())
            if not math.isfinite(amount) or amount <= 0 or amount > 100000:
                raise ValueError
        except (ValueError, TypeError):
            await update.effective_message.reply_text("أدخل مبلغاً صحيحاً بالدولار، مثل 5 أو 10.50.")
            return
        method = context.user_data.get("manual_method")
        if method not in MANUAL_PAYMENT_METHODS:
            context.user_data.clear()
            await update.effective_message.reply_text("طريقة الدفع غير صالحة. ابدأ من جديد.", reply_markup=home_keyboard(uid))
            return
        context.user_data["manual_amount_usd"] = round(amount, 2)
        context.user_data["state"] = "manual_reference"
        await update.effective_message.reply_text(
            f"المبلغ: ${amount:.2f}\nطريقة الدفع: {MANUAL_PAYMENT_METHODS[method]}\n\n"
            "حوّل المبلغ إلى البيانات أعلاه، ثم أرسل رقم العملية/مرجع التحويل. لا ترسل بيانات بطاقتك السرية."
        )
        return

    if state == "manual_reference":
        if len(text) < 2 or len(text) > 300:
            await update.effective_message.reply_text("أرسل رقم العملية أو مرجع التحويل (حتى 300 حرف).")
            return
        context.user_data["manual_reference"] = text
        context.user_data["state"] = "manual_receipt"
        await update.effective_message.reply_text("الآن أرسل صورة إيصال التحويل كصورة هنا. لن يُضاف الرصيد حتى يراجع المشرف الطلب ويقبله.")
        return

    if state == "manual_receipt":
        await update.effective_message.reply_text("أرسل صورة الإيصال كصورة (Photo) حتى يصل طلب الدفع للمشرف للمراجعة.")
        return

    if state == "platform_label" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear(); await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard()); return
        key = context.user_data.get("platform_label_key")
        if key not in PLATFORMS or not text or len(text) > 50:
            await update.effective_message.reply_text("الاسم غير صحيح. أرسل اسماً حتى 50 حرفاً."); return
        set_setting("platform_label_" + key, text)
        context.user_data.clear()
        await update.effective_message.reply_text("✅ تم تعديل اسم زر التطبيق.", reply_markup=kb([[btn("🔙 إدارة التطبيق", f"platstat:{key}")], [btn("🔙 التطبيقات", "platforms")]]))
        return

    if state in ("section_name", "section_rename") and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear(); await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard()); return
        if not text or len(text) > 80:
            await update.effective_message.reply_text("أرسل اسماً من 1 إلى 80 حرفاً."); return
        if state == "section_name":
            platform = context.user_data.get("section_platform")
            try:
                with db() as c: c.execute("INSERT OR IGNORE INTO service_sections(platform,name) VALUES(?,?)", (platform, text))
                context.user_data.clear(); await update.effective_message.reply_text("✅ تمت إضافة القسم.", reply_markup=kb([[btn("🔙 إدارة التطبيق", f"platstat:{platform}")]]))
            except Exception as exc:
                await update.effective_message.reply_text(f"تعذر إضافة القسم: {str(exc)[:120]}")
        else:
            secid = context.user_data.get("section_id")
            with db() as c: sec = c.execute("SELECT platform FROM service_sections WHERE id=?", (secid,)).fetchone(); c.execute("UPDATE service_sections SET name=? WHERE id=?", (text, secid))
            context.user_data.clear(); await update.effective_message.reply_text("✅ تم تعديل اسم القسم.", reply_markup=kb([[btn("🔙 إدارة التطبيق", f"platstat:{sec['platform']}")]] if sec else [[btn("لوحة التحكم", "admin")]]))
        return

    if state == "manual_service_name" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear(); await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard()); return
        if not text or len(text) > 180:
            await update.effective_message.reply_text("أرسل اسم خدمة من 1 إلى 180 حرفاً."); return
        context.user_data["manual_name"] = text; context.user_data["state"] = "manual_service_category"
        await update.effective_message.reply_text("أرسل اسم القسم/الوصف لهذه الخدمة (أو اكتب - إذا لا يوجد).")
        return

    if state == "manual_service_category" and is_admin(uid):
        context.user_data["manual_category"] = "" if text == "-" else text[:100]; context.user_data["state"] = "manual_service_price"
        await update.effective_message.reply_text("أرسل سعر البيع بالدولار لكل 1000 وحدة، رقم أكبر من صفر.")
        return

    if state == "manual_service_price" and is_admin(uid):
        try:
            price = float(text.replace(",", ".").replace("$", ""))
            if not math.isfinite(price) or price <= 0 or price > 1000000: raise ValueError
        except ValueError:
            await update.effective_message.reply_text("السعر غير صحيح. أرسل رقماً أكبر من صفر."); return
        context.user_data["manual_price"] = price; context.user_data["state"] = "manual_service_points"
        await update.effective_message.reply_text("أرسل النقاط لكل 1000 وحدة (عدد صحيح أكبر من صفر).")
        return

    if state == "manual_service_points" and is_admin(uid):
        try:
            points = int(text)
            if points <= 0: raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل عدد نقاط صحيحاً أكبر من صفر."); return
        context.user_data["manual_points"] = points; context.user_data["state"] = "manual_service_min"
        await update.effective_message.reply_text("أرسل أقل كمية مسموحة (عدد صحيح).")
        return

    if state == "manual_service_min" and is_admin(uid):
        try:
            qty = int(text)
            if qty < 1: raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل كمية صحيحة أكبر من صفر."); return
        context.user_data["manual_min"] = qty; context.user_data["state"] = "manual_service_max"
        await update.effective_message.reply_text("أرسل أكبر كمية مسموحة (عدد صحيح لا يقل عن أقل كمية).")
        return

    if state == "manual_service_max" and is_admin(uid):
        try:
            qty = int(text); minimum = int(context.user_data["manual_min"])
            if qty < minimum: raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أكبر كمية يجب أن تكون مساوية أو أكبر من أقل كمية."); return
        data = dict(context.user_data); platform = data.get("manual_platform", "other")
        try:
            pid = ensure_manual_provider()
            external_id = "manual-" + str(int(time.time() * 1000))
            with db() as c:
                cur = c.execute("INSERT INTO services(provider_id,external_id,platform,name,category,provider_rate,price_usd,price_points,min_qty,max_qty,enabled,delivery_mode,manual_instruction) VALUES(?,?,?,?,?,?,?,?,?,?,1,'manual','')", (pid, external_id, platform, data.get("manual_name", "خدمة يدوية"), data.get("manual_category", ""), 0, float(data["manual_price"]), int(data["manual_points"]), int(data["manual_min"]), qty))
                sid = cur.lastrowid
            context.user_data.clear(); await update.effective_message.reply_text(f"✅ تمت إضافة الخدمة اليدوية #{sid}. الطلبات ستصل للإدارة ولن تُرسل لمزود API.", reply_markup=kb([[btn("🛠 إدارة الخدمة", f"svcadmin:{sid}")], [btn("🔙 التطبيق", f"platstat:{platform}")]]))
        except Exception as exc:
            await update.effective_message.reply_text(f"تعذر إضافة الخدمة: {str(exc)[:180]}")
        return

    if state == "service_edit" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear(); await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard()); return
        sid = context.user_data.get("edit_service_id"); field = context.user_data.get("edit_service_field")
        allowed = {"name", "category", "price_usd", "price_points", "min_qty", "max_qty"}
        if field not in allowed or not sid:
            context.user_data.clear(); await update.effective_message.reply_text("انتهت جلسة التعديل.", reply_markup=admin_keyboard()); return
        try:
            if field in ("name", "category"):
                value = text[:180 if field == "name" else 100]
                if field == "name" and not value: raise ValueError
            elif field == "price_usd":
                value = float(text.replace(",", ".").replace("$", ""))
                if not math.isfinite(value) or value <= 0: raise ValueError
            else:
                value = int(text)
                if value <= 0: raise ValueError
            with db() as c:
                svc = c.execute("SELECT min_qty,max_qty,platform FROM services WHERE id=?", (sid,)).fetchone()
                if not svc: raise ValueError
                if field == "min_qty" and value > svc["max_qty"]: raise ValueError
                if field == "max_qty" and value < svc["min_qty"]: raise ValueError
                c.execute(f"UPDATE services SET {field}=? WHERE id=?", (value, sid))
                if field == "price_usd":
                    points = max(1, int(math.ceil(value * max(0.000001, float(get_setting("points_per_usd", "1000"))))))
                    c.execute("UPDATE services SET price_points=? WHERE id=?", (points, sid))
                elif field == "price_points":
                    c.execute("UPDATE services SET price_points=? WHERE id=?", (value, sid))
                platform = svc["platform"]
            context.user_data.clear(); await update.effective_message.reply_text("✅ تم حفظ التعديل.", reply_markup=kb([[btn("🛠 إدارة الخدمة", f"svcadmin:{sid}")], [btn("🔙 التطبيق", f"platstat:{platform}")]]))
        except (ValueError, TypeError):
            await update.effective_message.reply_text("القيمة غير صحيحة أو تخالف حدود الكمية. حاول مجدداً أو اكتب إلغاء.")
        return

    if state in ("provider_name", "provider_url", "provider_key") and not is_admin(uid):
        context.user_data.clear()
        await update.effective_message.reply_text("غير مصرح لك بتنفيذ هذا الإجراء.")
        return

    if state == "order_quantity":
        try:
            quantity = int(text)
            if quantity < 1:
                raise ValueError
            sid = int(context.user_data["service_id"])
        except (ValueError, KeyError, TypeError):
            await update.effective_message.reply_text("📮 أرسل العدد الذي تريد طلبه بالأرقام فقط.")
            return
        with db() as c:
            service = c.execute(
                "SELECT name,category,external_id,price_usd,price_points,min_qty,max_qty,delivery_mode FROM services WHERE id=? AND enabled=1",
                (sid,)
            ).fetchone()
        if not service:
            context.user_data.clear()
            await update.effective_message.reply_text("الخدمة لم تعد متاحة. اختر خدمة أخرى.", reply_markup=home_keyboard(uid))
            return
        if not service["min_qty"] <= quantity <= service["max_qty"]:
            await update.effective_message.reply_text(
                f"الكمية المسموحة لهذه الخدمة بين {service['min_qty']} و{service['max_qty']}. أرسل كمية ضمن هذا النطاق."
            )
            return
        context.user_data["order_quantity"] = quantity
        context.user_data["state"] = "order_link"
        await update.effective_message.reply_text(ui_message("order_link_prompt"))
        return

    if state == "order_link":
        target = text.strip()
        parsed = urlparse(target if "://" in target else "https://" + target)
        # Accept full URLs, @usernames, and common platform identifiers/short links.
        if (not target or len(target) > 2000 or any(ch.isspace() for ch in target)
                or not (parsed.netloc or target.startswith("@") or target.startswith("/"))):
            await update.effective_message.reply_text(
                "📌 أرسل رابط المنشور/الحساب أو اسم المستخدم مثل @username.\n"
                "لا يشترط أن يبدأ الرابط بـ https://؛ تأكد فقط أن المزود يقبل هذا النوع من الروابط."
            )
            return
        text = target
        try:
            sid = int(context.user_data["service_id"])
            quantity = int(context.user_data["order_quantity"])
        except (KeyError, ValueError, TypeError):
            context.user_data.clear()
            await update.effective_message.reply_text("انتهت جلسة الطلب. اختر الخدمة من جديد.", reply_markup=home_keyboard(uid))
            return
        with db() as c:
            service = c.execute(
                "SELECT name,category,price_usd,price_points,provider_rate,min_qty,max_qty,delivery_mode,external_id FROM services WHERE id=? AND enabled=1",
                (sid,)
            ).fetchone()
            user = c.execute("SELECT points FROM users WHERE user_id=?", (uid,)).fetchone()
        if not service:
            context.user_data.clear()
            await update.effective_message.reply_text("الخدمة لم تعد متاحة. اختر خدمة أخرى.", reply_markup=home_keyboard(uid))
            return
        mode = get_setting("currency_mode", "points")
        cost_usd = quantity * float(service["price_usd"] or 0) / 1000
        points_cost = int(math.ceil(quantity * int(service["price_points"] or 0) / 1000))
        if mode == "usd" and math.isfinite(cost_usd) and cost_usd > 0:
            points_cost = int(math.ceil(cost_usd * max(0.000001, float(get_setting("points_per_usd", "1000")))))
        is_free_service = (
            float(service["provider_rate"] or 0) == 0.0
            and float(service["price_usd"] or 0) == 0.0
            and int(service["price_points"] or 0) == 0
        )
        if (not math.isfinite(cost_usd) or cost_usd < 0 or points_cost < 0
                or ((cost_usd == 0 or points_cost == 0) and not is_free_service)):
            await update.effective_message.reply_text("❌ سعر هذه الخدمة غير مضبوط حالياً. أبلغ المشرف.")
            return
        context.user_data["order_link"] = text
        context.user_data["state"] = "order_confirmation"
        price_text = ("🎁 التكلفة: مجانية — لن يتم خصم نقاط" if is_free_service else
                      (f"💰 التكلفة: {points_cost} نقطة" if mode != "usd" else f"💰 التكلفة: {points_cost} نقطة (ما يعادل ${cost_usd:.6f})"))
        is_manual = service["delivery_mode"] == "manual"
        delivery_note = ("⏳ هذا الطلب يحتاج مراجعة الإدارة لأنه طلب يدوي." if is_manual else "🚀 بعد التأكيد سيُرسل الطلب مباشرة إلى المزود ولا يحتاج موافقة الإدارة.")
        await update.effective_message.reply_text(
            "🧾 مراجعة الطلب قبل التأكيد\n\n"
            f"💎| اسم الخدمة: {service['name']}\n"
            f"🔗| الرابط: {text}\n"
            f"📦| العدد: {quantity}\n"
            f"{price_text}\n"
            f"💎| نقاطك الحالية: {int(user['points'] or 0) if user else 0} نقطة\n\n"
            f"{delivery_note}\n\nهل تؤكد إرسال الطلب؟",
            reply_markup=kb([
                [btn("✅ تأكيد الطلب", "order_confirm")],
                [btn("❌ إلغاء الطلب", "order_cancel")]
            ])
        )
        return

    if state == "check_order":
        try:
            order_id = int(text)
        except ValueError:
            await update.effective_message.reply_text("أرسل رقم الطلب بالأرقام فقط.")
            return
        with db() as c:
            order = c.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, uid)).fetchone()
        context.user_data.clear()
        if not order:
            await update.effective_message.reply_text("لم يتم العثور على طلب بهذا الرقم ضمن حسابك.", reply_markup=home_keyboard(uid))
        else:
            customer_status = {
                "processing": "قيد المراجعة", "submitted": "قيد المراجعة والمتابعة",
                "manual_pending": "قيد المراجعة من الإدارة", "failed": "مرفوض ❌", "rejected": "مرفوض ❌",
                "completed": "مكتمل ✅", "cancelled": "ملغى وتمت إعادة الرصيد"
            }.get(order["status"], "قيد المراجعة")
            await update.effective_message.reply_text(
                f"📦 الطلب #{order['id']}\nالحالة: {customer_status}\nالكمية: {order['quantity']}\nالتكلفة: {order['cost_points']} نقطة\nالسعر: ${order['cost_usd']:.6f}",
                reply_markup=home_keyboard(uid)
            )
        return

    if state == "transfer_id":
        try:
            receiver = int(text)
            if receiver == uid or receiver < 1:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل Telegram ID صحيحاً لمستخدم آخر.")
            return
        with db() as c:
            exists = c.execute("SELECT 1 FROM users WHERE user_id=?", (receiver,)).fetchone()
        if not exists:
            await update.effective_message.reply_text("المستخدم غير مسجل في المتجر. اطلب منه تشغيل /start أولاً.")
            return
        context.user_data["transfer_receiver"] = receiver
        context.user_data["state"] = "transfer_amount"
        await update.effective_message.reply_text("أرسل عدد النقاط التي تريد تحويلها.")
        return

    if state == "transfer_amount":
        try:
            amount = int(text)
            minimum = max(1, int(get_setting("transfer_min", "10")))
            receiver = int(context.user_data["transfer_receiver"])
            if amount < minimum:
                await update.effective_message.reply_text(f"أقل تحويل هو {minimum} نقطة.")
                return
        except (ValueError, KeyError, TypeError):
            await update.effective_message.reply_text("أرسل عدداً صحيحاً من النقاط.")
            return
        try:
            with db() as c:
                c.execute("BEGIN IMMEDIATE")
                cur = c.execute("UPDATE users SET points=points-? WHERE user_id=? AND points>=?", (amount, uid, amount))
                if cur.rowcount != 1:
                    raise ValueError("رصيدك غير كافٍ.")
                c.execute("UPDATE users SET points=points+? WHERE user_id=?", (amount, receiver))
                c.execute("INSERT INTO point_transfers(sender,receiver,amount,created) VALUES(?,?,?,?)", (uid, receiver, amount, datetime.now(timezone.utc).isoformat()))
            context.user_data.clear()
            await update.effective_message.reply_text(f"✅ تم تحويل {amount} نقطة إلى {receiver}.", reply_markup=home_keyboard(uid))
            try:
                await context.bot.send_message(receiver, f"🎁 وصلتك {amount} نقطة من المستخدم {uid}.")
            except TelegramError:
                pass
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
        return

    if state == "provider_service_price" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            platform = context.user_data.get("pending_platform", "instagram")
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء إضافة الخدمة.", reply_markup=kb([[btn("🔙 إدارة التطبيق", f"platstat:{platform}")]]))
            return
        try:
            selling = float(text.replace(",", ".").replace("$", "").strip())
            rate = float(context.user_data["pending_provider_rate"])
            if not math.isfinite(selling) or selling <= 0 or selling > 1000000:
                raise ValueError
            if selling < rate:
                await update.effective_message.reply_text(
                    f"⚠️ سعر البيع (${selling:g}) أقل من تكلفة المزود (${rate:g}) لكل 1000. أرسل سعراً لا يقل عن تكلفة المزود أو اكتب إلغاء."
                )
                return
            pid = int(context.user_data["pending_provider_id"])
            platform = context.user_data["pending_platform"]
            external_id = context.user_data["pending_external_id"]
            name = context.user_data["pending_service_name"]
            minimum = int(context.user_data["pending_min"])
            maximum = int(context.user_data["pending_max"])
            category = context.user_data.get("pending_category", "")
            section_id = context.user_data.get("pending_section_id")
            points = max(1, int(math.ceil(selling * max(0.000001, float(get_setting("points_per_usd", "1000"))))))
            with db() as c:
                existing = c.execute("SELECT id FROM services WHERE provider_id=? AND external_id=?", (pid, external_id)).fetchone()
                if existing:
                    c.execute("UPDATE services SET platform=?,name=?,category=?,provider_rate=?,price_usd=?,price_points=?,min_qty=?,max_qty=?,enabled=1,delivery_mode='provider',section_id=? WHERE id=?",
                              (platform, name, category, rate, round(selling, 6), points, minimum, maximum, section_id, existing["id"]))
                    sid = int(existing["id"])
                else:
                    cur = c.execute("INSERT INTO services(provider_id,external_id,platform,name,category,provider_rate,price_usd,price_points,min_qty,max_qty,enabled,delivery_mode,section_id) VALUES(?,?,?,?,?,?,?,?,?,?,1,'provider',?)",
                                    (pid, external_id, platform, name, category, rate, round(selling, 6), points, minimum, maximum, section_id))
                    sid = int(cur.lastrowid)
            context.user_data.clear()
            await update.effective_message.reply_text(
                f"✅ تمت إضافة الخدمة #{sid} إلى {PLATFORMS.get(platform, platform)}.\n"
                f"الاسم: {name}\nتكلفة المزود/1000: ${rate:g}\nسعر البيع/1000: ${selling:g}\n"
                f"الكمية: {minimum} - {maximum}",
                reply_markup=kb([[btn("🛠 إدارة الخدمة", f"svcadmin:{sid}")], [btn("🔙 إدارة التطبيق", f"platstat:{platform}")]])
            )
        except (ValueError, TypeError, KeyError) as exc:
            await update.effective_message.reply_text("السعر غير صحيح أو انتهت جلسة إضافة الخدمة. أرسل رقماً مثل 1.50 أو اكتب إلغاء.")
        except Exception as exc:
            log.exception("Could not import provider service")
            await update.effective_message.reply_text(f"تعذر حفظ الخدمة: {str(exc)[:180]}")
        return

    if state in ("provider_edit_name", "provider_edit_url", "provider_edit_key") and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            pid = context.user_data.get("provider_edit_id")
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء تعديل المزود.", reply_markup=kb([[btn("🔙 صفحة المزود", f"provider:{pid}")], [btn("🌐 المزودون", "providers")]]))
            return
        pid = int(context.user_data.get("provider_edit_id", 0) or 0)
        field = state.removeprefix("provider_edit_")
        value = text.strip()
        if field == "name":
            if not value or len(value) > 100:
                await update.effective_message.reply_text("أرسل اسماً من 1 إلى 100 حرف."); return
            column = "name"
        elif field == "url":
            parsed = urlparse(value)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or len(value) > 500:
                await update.effective_message.reply_text("الرابط غير صحيح. يجب أن يبدأ بـ https:// أو http://"); return
            column = "api_url"
        else:
            if not value or len(value) > 1000:
                await update.effective_message.reply_text("مفتاح API فارغ أو طويل بشكل غير طبيعي."); return
            column = "api_key"
        with db() as c:
            cur = c.execute(f"UPDATE providers SET {column}=? WHERE id=?", (value, pid))
        context.user_data.clear()
        if cur.rowcount:
            await update.effective_message.reply_text("✅ تم تحديث بيانات المزود. يمكنك اختبار الاتصال من صفحته.", reply_markup=kb([[btn("🧪 اختبار API", f"ptest:{pid}")], [btn("🌐 صفحة المزود", f"provider:{pid}")], [btn("🌐 المزودون", "providers")]]))
        else:
            await update.effective_message.reply_text("لم يتم العثور على المزود.", reply_markup=kb([[btn("🌐 المزودون", "providers")]]))
        return

    if state == "provider_name":
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء إضافة المزود.", reply_markup=admin_keyboard())
            return
        context.user_data["provider_name"] = text[:100]
        context.user_data["state"] = "provider_url"
        await update.effective_message.reply_text(
            "🔗 أرسل رابط API الكامل للمزود الذي تريد إضافته.\n"
            "مثال: https://example.com/api/v2\n"
            "يمكنك إضافة أي مزود يدعم واجهة SMM متوافقة.\n"
            "اكتب إلغاء للتراجع."
        )
        return

    if state == "provider_url":
        parsed = urlparse(text)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            await update.effective_message.reply_text("الرابط غير صحيح. أرسل رابطاً يبدأ بـ https:// أو http://")
            return
        context.user_data["provider_url"] = text
        context.user_data["state"] = "provider_key"
        await update.effective_message.reply_text("أرسل مفتاح API للمزود. لا تشاركه مع أحد.")
        return

    if state == "provider_key" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء إضافة المزود.", reply_markup=admin_keyboard())
            return
        name = str(context.user_data.get("provider_name", "Provider")).strip()[:100]
        api_url = str(context.user_data.get("provider_url", "")).strip()
        api_key = text.strip()
        if not api_key or len(api_key) > 1000:
            await update.effective_message.reply_text("مفتاح API فارغ أو طويل بشكل غير طبيعي. أرسله مجدداً أو اكتب إلغاء.")
            return
        status_msg = None
        try:
            # Acknowledge immediately so a slow provider/network never looks like a dead bot.
            status_msg = await update.effective_message.reply_text("⏳ استلمت مفتاح المزود، جارٍ حفظ البيانات...")
            with db() as c:
                cur = c.execute("INSERT INTO providers(name,api_url,api_key,enabled,owner_id,created) VALUES(?,?,?,1,?,?)",
                                (name, api_url, api_key, uid, datetime.now(timezone.utc).isoformat()))
                pid = int(cur.lastrowid)
            context.user_data.clear()
            await status_msg.edit_text(
                f"✅ تم حفظ المزود «{name}» برقم #{pid}.\n⏳ جارٍ اختبار المفتاح وجلب قائمة الخدمات الآن..."
            )
            try:
                provider = get_provider(pid)
                catalog = await api_call(provider, "services")
                if not isinstance(catalog, list):
                    detail = catalog.get("error") if isinstance(catalog, dict) else None
                    raise RuntimeError(str(detail or "رد المزود ليس قائمة خدمات بالشكل المتوقع")[:180])
                await status_msg.edit_text(
                    f"✅ تمت إضافة المزود واختبار الاتصال بنجاح.\n"
                    f"🌐 الاسم: {name}\n🆔 الرقم: #{pid}\n📦 عدد الخدمات التي أعادها المزود: {len(catalog)}\n\n"
                    "ادخل إلى التطبيقات > إنستغرام > اختيار خدمة من المزود، ثم اختر الخدمة وحدد سعر البيع."
                , reply_markup=kb([[btn("🧪 اختبار API", f"ptest:{pid}")], [btn("🌐 صفحة المزود", f"provider:{pid}")], [btn("📸 إدارة إنستغرام", "platstat:instagram")], [btn("🔙 لوحة التحكم", "admin")]]))
            except Exception as api_exc:
                log.warning("Provider %s saved but API test failed: %s", pid, api_exc)
                await status_msg.edit_text(
                    f"⚠️ تم حفظ المزود «{name}» برقم #{pid}، لكن اختبار API فشل.\n"
                    f"السبب: {str(api_exc)[:300]}\n\n"
                    "راجع رابط API والمفتاح من لوحة المزود، وتأكد أن المزود يستخدم API متوافقاً مع نظام SMM Panel."
                , reply_markup=kb([[btn("🔁 إعادة اختبار API", f"ptest:{pid}")], [btn("🌐 صفحة المزود", f"provider:{pid}")], [btn("🔙 لوحة التحكم", "admin")]]))
        except Exception as exc:
            log.exception("Could not save provider")
            error_text = f"❌ لم يتم حفظ المزود: {str(exc)[:250]}"
            try:
                if status_msg is not None:
                    await status_msg.edit_text(error_text, reply_markup=admin_keyboard())
                else:
                    await update.effective_message.reply_text(error_text, reply_markup=admin_keyboard())
            except TelegramError:
                await update.effective_message.reply_text(error_text, reply_markup=admin_keyboard())
        return

    if state == "profit":
        try:
            value = float(text)
            if not 0 <= value <= 10000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل نسبة صحيحة بين 0 و10000.")
            return
        set_setting("profit_percent", value)
        context.user_data.clear()
        await update.effective_message.reply_text("تم تحديث نسبة الربح.", reply_markup=admin_keyboard())
        return

    if state == "points_usd":
        try:
            value = float(text)
            if value <= 0 or value > 100000000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل عدداً موجباً صحيحاً للنقاط لكل دولار.")
            return
        set_setting("points_per_usd", value)
        context.user_data.clear()
        await update.effective_message.reply_text("تم تحديث النقاط لكل دولار.", reply_markup=admin_keyboard())
        return

    setting_map = {
        "edit_ref_reward": ("default_referral_reward", "مكافأة الدعوة"),
        "edit_daily": ("daily_reward", "الهدية اليومية"),
        "edit_transfer_min": ("transfer_min", "أقل تحويل"),
        "edit_star_rate": ("points_per_star", "النقاط لكل نجمة"),
    }
    if state in setting_map:
        try:
            value = int(text)
            if value < 0 or value > 100000000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل قيمة صحيحة غير سالبة.")
            return
        key, label = setting_map[state]
        set_setting(key, value)
        context.user_data.clear()
        await update.effective_message.reply_text(f"تم تحديث {label}.", reply_markup=admin_keyboard())
        return

    if state == "paid_gate_price" and is_admin(uid):
        try:
            value = int(text)
            if value < 1 or value > 1000000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل عدداً صحيحاً من 1 إلى 1000000.")
            return
        set_setting("paid_gate_stars", str(value))
        context.user_data.clear()
        await update.effective_message.reply_text(f"تم تحديد سعر الدخول إلى {value} نجمة.", reply_markup=admin_keyboard())
        return

    if state == "orders_channel" and is_admin(uid):
        target = text.strip()
        if target.startswith(("https://t.me/", "http://t.me/")):
            parsed = urlparse(target)
            parts = [part for part in parsed.path.split("/") if part]
            # Public channel URLs can be resolved by username. Private invite links must be added as a chat_id instead.
            if parts and not parts[0].startswith(("+", "joinchat")):
                target = "@" + parts[0]
        if target == "0":
            set_setting("orders_channel", "")
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء ربط قناة الطلبات.", reply_markup=admin_keyboard())
            return
        try:
            chat = await context.bot.get_chat(target)
            await context.bot.send_message(chat_id=chat.id, text="✅ تم ربط قناة الطلبات بنجاح. ستظهر هنا الطلبات بعد تأكيدها من الزبائن.")
            target = str(chat.id)
        except TelegramError:
            await update.effective_message.reply_text("تعذر الوصول للقناة أو إرسال رسالة إليها. للقناة العامة أرسل @username أو https://t.me/username، وللقناة الخاصة أرسل chat_id الرقمي. تأكد أن البوت مشرف ويملك صلاحية إرسال الرسائل.")
            return
        set_setting("orders_channel", target)
        context.user_data.clear()
        await update.effective_message.reply_text("✅ تم ربط قناة الطلبات بنجاح.", reply_markup=admin_keyboard())
        return

    if state in ("edit_channel_reward", "edit_channel_price") and is_admin(uid):
        try:
            value = int(text)
            maximum = 1000000 if state == "edit_channel_reward" else 100000000
            if not 1 <= value <= maximum:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل رقماً صحيحاً ضمن الحدود الموضحة.")
            return
        if state == "edit_channel_reward":
            set_setting("channel_join_reward", str(value))
            # Update only tasks created for funded channels, not manually managed tasks.
            with db() as c:
                c.execute("UPDATE channel_tasks SET reward=? WHERE owner_id>0", (value,))
            label = "مكافأة العضو"
        else:
            set_setting("channel_member_price", str(value))
            with db() as c:
                c.execute("UPDATE channel_tasks SET member_price=? WHERE owner_id>0", (value,))
            label = "سعر العضو"
        context.user_data.clear()
        await update.effective_message.reply_text(f"✅ تم تحديث {label} إلى {value} نقطة.", reply_markup=kb([[btn("📣 إعدادات تمويل القنوات", "channel_funding_settings")], [btn("🔙 لوحة التحكم", "admin")]]))
        return

    if state == "completed_channel" and is_admin(uid):
        target = text.strip()
        if target == "0":
            set_setting("completed_orders_channel", "")
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء قناة الطلبات المكتملة.", reply_markup=admin_keyboard())
            return
        try:
            chat = await context.bot.get_chat(target)
            await context.bot.send_message(chat_id=chat.id, text="✅ تم ربط قناة إشعارات الطلبات المكتملة بنجاح.")
            target = str(chat.id)
        except TelegramError:
            await update.effective_message.reply_text("تعذر الوصول إلى القناة أو إرسال رسالة إليها. أضف البوت إلى القناة كمسؤول ثم أعد إرسال @username أو chat_id.")
            return
        set_setting("completed_orders_channel", target)
        context.user_data.clear()
        await update.effective_message.reply_text("تم ربط قناة الطلبات المكتملة.", reply_markup=admin_keyboard())
        return

    if state == "fund_quantity":
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء طلب التمويل.", reply_markup=home_keyboard(uid))
            return
        try:
            quantity = int(text.replace(",", "").replace("٬", "").strip())
            minimum = max(1, int(get_setting("channel_funding_min_qty", "20") or 20))
            maximum = max(minimum, int(get_setting("channel_funding_max_qty", "100000") or 100000))
            if quantity < minimum or quantity > maximum:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text(f"أرسل كمية صحيحة من {get_setting('channel_funding_min_qty', '20')} إلى {get_setting('channel_funding_max_qty', '100000')}.")
            return
        price = max(1, int(get_setting("channel_member_price", "15") or 15))
        context.user_data["fund_quantity"] = quantity
        context.user_data["fund_price"] = price
        context.user_data["state"] = "fund_channel_chat"
        await update.effective_message.reply_text(
            "⚠️ ارفع البوت أدمن في قناتك.\n"
            "أرسل رابط قناتك أو اسم المستخدم (مثل @mlojlkkkjj):",
            reply_markup=kb([[btn("❌ إلغاء", "fund_cancel")]])
        )
        return

    if state == "fund_channel_chat":
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء طلب التمويل.", reply_markup=home_keyboard(uid))
            return
        try:
            chat = await context.bot.get_chat(text)
            if chat.type not in ("channel", "supergroup"):
                await update.effective_message.reply_text("أرسل رابط قناة أو مجموعة عامة فقط.")
                return
            bot_me = await context.bot.get_me()
            bot_member = await context.bot.get_chat_member(chat.id, bot_me.id)
            if bot_member.status not in ("administrator", "creator"):
                await update.effective_message.reply_text(
                    "🧑‍✈️ صلاحيات غير كافية\n"
                    "• ارفع البوت كـ مدير في القناة مع صلاحيات دعوة/إدارة الأعضاء.\n"
                    "ثم أعد الإرسال ✅"
                )
                return
            if bot_member.status == "administrator" and hasattr(bot_member, "can_invite_users") and not bot_member.can_invite_users:
                await update.effective_message.reply_text(
                    "🧑‍✈️ صلاحيات غير كافية\n"
                    "• فعّل للبوت صلاحية دعوة المستخدمين/إدارة الأعضاء ثم أعد الإرسال ✅"
                )
                return
            owner_member = await context.bot.get_chat_member(chat.id, uid)
            if owner_member.status not in ("administrator", "creator"):
                await update.effective_message.reply_text("❌ يجب أن تكون مالكاً أو مشرفاً في القناة حتى تتمكن من تمويلها.")
                return
            username = ("@" + chat.username) if getattr(chat, "username", None) else text.strip()
            quantity = int(context.user_data.get("fund_quantity", 0))
            price = int(context.user_data.get("fund_price", 15))
            total = quantity * price
            available = balance(uid)
            if available < total:
                await update.effective_message.reply_text(
                    f"❌ رصيدك غير كافٍ لإتمام الطلب.\n💎 رصيدك الحالي: {available} نقطة\n💰 تكلفة التمويل: {total} نقطة\n\nاشحن رصيدك ثم أعد الطلب.",
                    reply_markup=kb([[btn("❌ إلغاء", "fund_cancel")], [btn("🔙 رجوع", "fund_channels")]])
                )
                return
            title = (chat.title or chat.username or text)[:150]
            pending = {
                "chat_id": str(chat.id), "username": username, "title": title,
                "funding_type": context.user_data.get("funding_type", "slow"),
                "quantity": quantity, "price_per_member": price, "total_cost": total,
            }
            context.user_data["funding_review"] = pending
            context.user_data.pop("state", None)
            mode_name = "تمويل الاشتراك الإجباري" if pending["funding_type"] == "mandatory" else "تمويل بطيء (الانضمام للقنوات)"
            await update.effective_message.reply_text(
                f"📜 مراجعة الطلب\n\n📣 القناة: {username}\n👥 الكمية: {quantity}\n"
                f"💰 السعر/عضو: {price}\n📦 الإجمالي: {total} نقطة\n⚙️ الطريقة: {mode_name}\n\nهل تريد المتابعة؟",
                reply_markup=kb([[btn("✅ تأكيد الطلب", "fund_confirm")], [btn("إلغاء ❌", "fund_cancel")]])
            )
        except TelegramError:
            await update.effective_message.reply_text(
                "تعذر الوصول إلى القناة. تأكد أن الرابط صحيح وأن القناة عامة، وأن البوت مشرف فيها، ثم أعد الإرسال."
            )
        return

    if state == "api_credit_user_id" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel", "/cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        try:
            target = int(text)
            if target <= 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل Telegram ID رقمياً وصحيحاً، أو اكتب إلغاء.")
            return
        with db() as c:
            account = c.execute("SELECT user_id,balance,active FROM api_clients WHERE user_id=?", (target,)).fetchone()
        if not account:
            context.user_data.clear()
            await update.effective_message.reply_text(
                f"لا يوجد حساب API للمستخدم {target}. اطلب منه إنشاء حساب API أولاً، ثم أعد العملية.",
                reply_markup=kb([[btn("👥 عملاء API", "api_clients_admin")], [btn("🔙 لوحة التحكم", "admin")]])
            )
            return
        context.user_data["api_credit_target"] = target
        context.user_data["state"] = "api_credit_amount"
        await update.effective_message.reply_text(
            f"حساب API: {target}\nالرصيد الحالي: {account['balance']}\nالحالة: {'فعال' if account['active'] else 'موقوف'}\n\nأرسل مقدار الرصيد الذي تريد إضافته كعدد صحيح موجب."
        )
        return

    if state == "api_credit_amount" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel", "/cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        try:
            amount = int(text)
            if amount <= 0 or amount > 1_000_000_000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل عدداً صحيحاً موجباً لا يتجاوز 1,000,000,000.")
            return
        target = int(context.user_data.get("api_credit_target", 0))
        now = datetime.now(timezone.utc).isoformat()
        with db() as c:
            row = c.execute("SELECT balance FROM api_clients WHERE user_id=?", (target,)).fetchone()
            if not row:
                context.user_data.clear()
                await update.effective_message.reply_text("حساب API غير موجود؛ لم تتم إضافة الرصيد.", reply_markup=admin_keyboard())
                return
            c.execute("UPDATE api_clients SET balance=balance+?,updated=? WHERE user_id=?", (amount, now, target))
            new_balance = int(row["balance"] or 0) + amount
            ref = f"admin-api-credit:{uid}:{target}:{time.time_ns()}"
            c.execute("INSERT INTO api_ledger(user_id,amount,kind,reference,details,created) VALUES(?,?,?,?,?,?)",
                      (target, amount, "admin_credit", ref, f"Credited by admin {uid}", now))
        context.user_data.clear()
        await update.effective_message.reply_text(
            f"✅ تمت إضافة رصيد API بنجاح.\n👤 المستخدم: {target}\n➕ المضاف: {amount}\n💰 الرصيد الجديد: {new_balance}",
            reply_markup=kb([[btn("👥 عملاء API", "api_clients_admin")], [btn("🔙 لوحة التحكم", "admin")]])
        )
        try:
            await context.bot.send_message(target, f"💰 تمت إضافة رصيد إلى حساب API الخاص بك من الإدارة.\n➕ الرصيد المضاف: {amount}\n💰 رصيد API الحالي: {new_balance}")
        except TelegramError:
            log.warning("Could not notify API user %s about admin credit", target)
        try:
            await context.bot.send_message(OWNER_ID, f"🔔 إضافة رصيد API يدوية\n🛡️ المشرف: {uid}\n👤 المستخدم: {target}\n➕ المضاف: {amount}\n💰 الرصيد الجديد: {new_balance}")
        except TelegramError:
            log.warning("Could not notify owner about admin API credit")
        return

    if state == "api_admin_key_user_id" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel", "/cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        try:
            target = int(text)
            if target <= 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل Telegram ID رقمياً وصحيحاً، أو اكتب إلغاء.")
            return
        token = "smmp_" + secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        with db() as c:
            existing = c.execute("SELECT user_id FROM api_clients WHERE user_id=?", (target,)).fetchone()
            if existing:
                c.execute("UPDATE api_clients SET token_hash=?,token_prefix=?,active=1,updated=? WHERE user_id=?",
                          (hashlib.sha256(token.encode()).hexdigest(), token[:12], now, target))
                kind = "admin_rotated"
            else:
                c.execute("INSERT INTO api_clients(user_id,token_hash,token_prefix,balance,active,created,updated) VALUES(?,?,?,0,1,?,?)",
                          (target, hashlib.sha256(token.encode()).hexdigest(), token[:12], now, now))
                kind = "admin_created"
            c.execute("INSERT INTO api_ledger(user_id,amount,kind,reference,details,created) VALUES(?,0,?,?,?,?)",
                      (target, kind, f"{kind}:{uid}:{target}:{time.time_ns()}", f"API key issued by admin {uid}; previous key revoked if present", now))
        context.user_data.clear()
        try:
            await context.bot.send_message(target,
                "🔐 أنشأت الإدارة مفتاح API جديداً لحسابك. تم إبطال المفتاح السابق إن وُجد. احفظ المفتاح الآن؛ لن يظهر كاملاً مرة أخرى.\n\n"
                f"المفتاح: <code>{token}</code>\nرابط API: {api_url_display()}", parse_mode="HTML")
            sent_msg = "\n📩 تم إرسال المفتاح الجديد إلى المستخدم برسالة خاصة."
        except TelegramError:
            sent_msg = "\n⚠️ تعذّر إرسال المفتاح للمستخدم. لم يُعرض المفتاح في المحادثة الإدارية لأسباب أمنية؛ اطلب من المستخدم فتح البوت والسماح بالرسائل ثم أعد التجديد."
            log.warning("Could not send admin-created API key to user %s", target)
        await update.effective_message.reply_text(
            f"✅ تم إنشاء/تجديد مفتاح API للمستخدم {target}.\n🔎 بادئة المفتاح: {token[:12]}{sent_msg}",
            reply_markup=kb([[btn("👥 عملاء API", "api_clients_admin")], [btn("🔙 لوحة التحكم", "admin")]])
        )
        try:
            await context.bot.send_message(OWNER_ID, f"🔔 الإدارة أنشأت/جدّدت مفتاح API\n🛡️ المشرف: {uid}\n👤 المستخدم: {target}\n🔎 البادئة: {token[:12]}\nلم يتم إرسال المفتاح الكامل للإدارة.")
        except TelegramError:
            pass
        return

    if state == "api_link_price" and is_admin(uid):
        try:
            value = float(text.replace(",", "."))
            if not math.isfinite(value) or value < 0 or value > 100000000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل سعراً رقمياً من 0 إلى 100000000.")
            return
        set_setting("api_link_price", value)
        context.user_data.clear()
        await update.effective_message.reply_text(f"تم حفظ سعر ربط API: {value:g}. تنبيه: الإعداد لا يخصم المبلغ تلقائياً.", reply_markup=admin_keyboard())
        return

    if state == "provider_margin" and is_admin(uid):
        pid = int(context.user_data.get("provider_margin_id", 0))
        if text.casefold() in ("عام", "default", "global"):
            value = -1
        else:
            try:
                value = float(text)
                if not math.isfinite(value) or not 0 <= value <= 10000:
                    raise ValueError
            except ValueError:
                await update.effective_message.reply_text("أرسل نسبة من 0 إلى 10000، أو اكتب عام.")
                return
        with db() as c:
            c.execute("UPDATE providers SET profit_percent=? WHERE id=?", (value, pid))
        context.user_data.clear()
        await update.effective_message.reply_text("تم حفظ هامش ربح المزود. اضغط (إعادة حساب الأسعار) لتطبيقه على الخدمات الموجودة.", reply_markup=kb([[btn("💵 الأسعار والأرباح", "pricing")], [btn("🌐 المزودون", "providers")], [btn("🔙 لوحة التحكم", "admin")]]))
        return

    if state == "fc_chat" and is_admin(uid):
        target = text.strip()
        title = target
        try:
            chat = await context.bot.get_chat(target)
            title = chat.title or chat.username or target
        except TelegramError:
            await update.effective_message.reply_text("لم أتمكن من الوصول إلى القناة. تأكد من المعرف وأن البوت يستطيع الوصول إليها.")
            return
        with db() as c:
            c.execute("INSERT OR REPLACE INTO forced_channels(chat_id,title,enabled) VALUES(?,?,1)", (target, title))
        context.user_data.clear()
        await update.effective_message.reply_text("تمت إضافة قناة الاشتراك الإجباري.", reply_markup=admin_keyboard())
        return

    if state == "task_chat" and is_admin(uid):
        context.user_data["task_chat"] = text
        context.user_data["state"] = "task_title"
        await update.effective_message.reply_text("أرسل اسم المهمة الذي سيظهر للمستخدمين.")
        return

    if state == "task_title" and is_admin(uid):
        context.user_data["task_title"] = text[:150]
        context.user_data["state"] = "task_reward"
        await update.effective_message.reply_text("أرسل مكافأة المهمة بالنقاط.")
        return

    if state == "task_reward" and is_admin(uid):
        try:
            reward = int(text)
            if reward < 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل مكافأة صحيحة غير سالبة.")
            return
        chat_id = context.user_data.get("task_chat", "")
        title = context.user_data.get("task_title", chat_id)
        with db() as c:
            c.execute("INSERT INTO channel_tasks(chat_id,title,reward,enabled) VALUES(?,?,?,1)", (chat_id, title, reward))
        context.user_data.clear()
        await update.effective_message.reply_text("تمت إضافة المهمة.", reply_markup=admin_keyboard())
        return

    if state == "add_admin" and is_admin(uid):
        try:
            target = int(text)
            if target < 1:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل Telegram ID صحيحاً.")
            return
        with db() as c:
            c.execute("INSERT OR IGNORE INTO admins(user_id,added_by,created) VALUES(?,?,?)", (target, uid, datetime.now(timezone.utc).isoformat()))
        context.user_data.clear()
        await update.effective_message.reply_text("تمت إضافة المشرف إذا كان المعرّف صحيحاً.", reply_markup=admin_keyboard())
        return

    if state == "vip_price_stars" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        try:
            value = int(text)
            if not 1 <= value <= 1000000:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text("أرسل عدداً صحيحاً من 1 إلى 1000000.")
            return
        set_setting("vip_price_stars", str(value))
        context.user_data.clear()
        await update.effective_message.reply_text(f"✅ تم تحديث سعر VIP إلى {value} نجمة.", reply_markup=admin_keyboard())
        return

    if state == "menu_button_rename" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء تعديل الاسم.", reply_markup=admin_keyboard())
            return
        key = context.user_data.get("menu_rename_key")
        if key not in UI_LABELS or not text.strip() or len(text.strip()) > 60:
            await update.effective_message.reply_text("أرسل اسماً من 1 إلى 60 حرفاً، أو اكتب إلغاء.")
            return
        set_setting("ui_label_" + key, text.strip())
        context.user_data.clear()
        await update.effective_message.reply_text("✅ تم حفظ اسم الزر.", reply_markup=kb([[btn("🛠 إدارة القوائم والأزرار", "menu_button_manager")], [btn("👁 عرض الواجهة", "home")], [btn("🔙 لوحة التحكم", "admin")]]))
        return

    if state == "ui_text_edit" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء التعديل.", reply_markup=admin_keyboard())
            return
        setting_key = context.user_data.get("ui_text_setting_key")
        kind = context.user_data.get("ui_text_kind", "label")
        title = context.user_data.get("ui_text_title", "النص")
        if not setting_key or len(text.strip()) > (3500 if kind == "message" else 100):
            await update.effective_message.reply_text("النص طويل أو تعذر تحديد العنصر. أعد المحاولة أو اكتب إلغاء.")
            return
        set_setting(setting_key, text.strip())
        context.user_data.clear()
        await update.effective_message.reply_text(f"✅ تم حفظ {title} بنجاح.\nيمكن استخدام متغيرات مثل {{user_id}} و{{username}} و{{points}} و{{order_id}} و{{service_name}} و{{quantity}} و{{link}} و{{cost}}، حسب نوع الرسالة.", reply_markup=kb([[btn("📝 متابعة تعديل الأسماء والكلايش", "interface_text_settings")], [btn("🔙 لوحة التحكم", "admin")]]))
        return

    if state == "completed_count_button_name" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard())
            return
        if len(text.strip()) > 60:
            await update.effective_message.reply_text("الاسم طويل؛ أرسل اسماً لا يتجاوز 60 حرفاً.")
            return
        set_setting("completed_count_button_name", text.strip())
        context.user_data.clear()
        await update.effective_message.reply_text("✅ تم تحديث اسم زر الطلبات المنجزة. استخدم {count} لإظهار العدد تلقائياً.", reply_markup=admin_keyboard())
        return

    if state == "broadcast_message" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear()
            await update.effective_message.reply_text("تم إلغاء الإذاعة.", reply_markup=admin_keyboard())
            return
        broadcast_text = text[:4000]
        with db() as c:
            user_rows = c.execute("SELECT user_id FROM users").fetchall()
            channel_rows = c.execute("SELECT chat_id FROM channel_tasks WHERE enabled=1").fetchall()
            funding_rows = c.execute("SELECT chat_id FROM channel_funding_requests WHERE status='approved'").fetchall()
        targets = {int(row["user_id"]) for row in user_rows if row["user_id"]}
        channel_targets = {str(row["chat_id"]).strip() for row in list(channel_rows) + list(funding_rows) if row["chat_id"]}
        targets.update(channel_targets)
        sent = failed = 0
        for target in targets:
            try:
                await context.bot.send_message(chat_id=target, text=broadcast_text, disable_web_page_preview=True)
                sent += 1
                await asyncio.sleep(0.04)
            except TelegramError as exc:
                failed += 1
                log.info("Broadcast failed for %s: %s", target, exc)
            except Exception:
                failed += 1
                log.exception("Unexpected broadcast failure for %s", target)
        context.user_data.clear()
        await update.effective_message.reply_text(
            f"📡 انتهت الإذاعة.\n\n✅ تم الإرسال إلى: {sent}\n❌ تعذّر الإرسال إلى: {failed}\n👥 المستخدمون المسجلون: {len(user_rows)}\n📣 القنوات المعروفة للبوت: {len(channel_targets)}",
            reply_markup=admin_keyboard()
        )
        return

    if state == "support_text_edit" and is_admin(uid):
        if text.casefold() in ("إلغاء", "الغاء", "cancel"):
            context.user_data.clear(); await update.effective_message.reply_text("تم الإلغاء.", reply_markup=admin_keyboard()); return
        set_setting("support", text[:2000])
        context.user_data.clear()
        await update.effective_message.reply_text("✅ تم تحديث نص الدعم الفني.", reply_markup=admin_keyboard())
        return

    await update.effective_message.reply_text("لم أفهم القيمة. استخدم /start للعودة إلى القائمة.")


# =========================================================
# PAYMENTS
# =========================================================

async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    try:
        parts = (query.invoice_payload or "").split(":")
        if len(parts) != 3:
            raise ValueError("invalid payload")
        kind, uid_text, amount_text = parts
        if int(uid_text) != query.from_user.id:
            raise ValueError("wrong user")
        expected_amount = int(amount_text)
        if query.currency != "XTR" or query.total_amount != expected_amount or expected_amount < 1:
            raise ValueError("wrong currency or amount")
        if kind == "access":
            if expected_amount != max(1, int(get_setting("paid_gate_stars", "10"))) or get_setting("paid_gate_enabled", "0") != "1":
                raise ValueError("access payment is not enabled or price changed")
        elif kind == "points":
            if expected_amount not in (10, 25, 50, 100):
                raise ValueError("invalid points package")
        elif kind == "vip":
            if expected_amount != max(1, int(get_setting("vip_price_stars", "100"))):
                raise ValueError("VIP price changed")
        elif kind == "api":
            if expected_amount not in api_stars_packages():
                raise ValueError("invalid API topup package")
            with db() as c:
                if not c.execute("SELECT 1 FROM api_clients WHERE user_id=? AND active=1", (query.from_user.id,)).fetchone():
                    raise ValueError("API account is not active")
        else:
            raise ValueError("unknown payment kind")
        await query.answer(ok=True)
    except (ValueError, TypeError):
        await query.answer(ok=False, error_message="تعذر التحقق من بيانات الدفع أو تغيّر السعر. أعد المحاولة من داخل البوت.")


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.effective_message.successful_payment
    uid = update.effective_user.id
    payload = payment.invoice_payload or ""
    charge_id = payment.telegram_payment_charge_id
    try:
        parts = payload.split(":")
        if (len(parts) != 3 or int(parts[1]) != uid
                or payment.currency != "XTR" or int(parts[2]) != payment.total_amount):
            await update.effective_message.reply_text("تعذر التحقق من عملية الدفع.")
            return
        kind, _, amount_text = parts
        amount = int(amount_text)
        with db() as c:
            exists = c.execute("SELECT 1 FROM payments WHERE charge_id=?", (charge_id,)).fetchone()
            if exists:
                await update.effective_message.reply_text("تم تسجيل هذه العملية مسبقاً.")
                return
            if kind == "access":
                expected = max(1, int(get_setting("paid_gate_stars", "10")))
                if amount != expected or get_setting("paid_gate_enabled", "0") != "1":
                    await update.effective_message.reply_text("تعذر تأكيد سعر الدخول الحالي. تواصل مع الإدارة.")
                    return
                c.execute(
                    "INSERT OR REPLACE INTO paid_access(user_id,charge_id,stars,paid_at) VALUES(?,?,?,?)",
                    (uid, charge_id, amount, datetime.now(timezone.utc).isoformat())
                )
                points = 0
            elif kind == "points":
                points = amount * max(0, int(get_setting("points_per_star", "10")))
                c.execute("UPDATE users SET points=points+? WHERE user_id=?", (points, uid))
            elif kind == "api":
                if amount not in api_stars_packages():
                    await update.effective_message.reply_text("باقة API غير صالحة.")
                    return
                credits = amount * max(1, int(get_setting("api_stars_rate", "1")))
                changed = c.execute("UPDATE api_clients SET balance=balance+?,updated=? WHERE user_id=? AND active=1", (credits, datetime.now(timezone.utc).isoformat(), uid)).rowcount
                if not changed:
                    await update.effective_message.reply_text("حساب API غير موجود أو موقوف. تواصل مع الإدارة.")
                    return
                c.execute("INSERT OR IGNORE INTO api_ledger(user_id,amount,kind,reference,details,created) VALUES(?,?,?,?,?,?)", (uid, credits, "topup", "stars:"+charge_id, f"Telegram Stars {amount}", datetime.now(timezone.utc).isoformat()))
                points = credits
            elif kind == "vip":
                days = max(1, int(get_setting("vip_days", "30")))
                row = c.execute("SELECT vip_until FROM users WHERE user_id=?", (uid,)).fetchone()
                now = datetime.now(timezone.utc)
                try:
                    existing_until = datetime.fromisoformat(row["vip_until"]) if row and row["vip_until"] else now
                except ValueError:
                    existing_until = now
                start_at = max(now, existing_until)
                until = (start_at + __import__("datetime").timedelta(days=days)).isoformat()
                c.execute("UPDATE users SET vip_until=? WHERE user_id=?", (until, uid))
                points = 0
            else:
                await update.effective_message.reply_text("نوع الدفع غير معروف.")
                return
            c.execute("INSERT INTO payments(charge_id,user_id,stars,credited_points,created) VALUES(?,?,?,?,?)", (charge_id, uid, payment.total_amount, points, datetime.now(timezone.utc).isoformat()))
        if kind == "access":
            await update.effective_message.reply_text(
                "✅ تم الدفع وفتح الوصول إلى البوت بنجاح.",
                reply_markup=home_keyboard(uid)
            )
        elif kind == "points":
            await update.effective_message.reply_text(f"✅ تم الدفع بنجاح وإضافة {points} نقطة.\nرصيدك الحالي: {balance(uid)}")
        elif kind == "api":
            with db() as c:
                api_row = c.execute("SELECT balance,token_prefix FROM api_clients WHERE user_id=?", (uid,)).fetchone()
            api_balance = int(api_row["balance"] or 0) if api_row else 0
            await update.effective_message.reply_text(f"✅ تم شحن رصيد API بنجاح.\n⭐ المدفوع: {amount} نجمة\n➕ الرصيد المضاف: {points}\n💰 رصيد API الحالي: {api_balance}\n🔗 الرابط: {api_url_display()}\nاستخدم زر API لعرض حالة حسابك.", reply_markup=home_keyboard(uid))
            try:
                username = update.effective_user.username or "بدون"
                await context.bot.send_message(OWNER_ID, f"🔔 إشعار شحن API ناجح\n\n👤 المستخدم: {uid} (@{username})\n⭐ المبلغ المدفوع: {amount} نجمة Telegram\n➕ الرصيد المضاف: {points}\n💰 رصيد API بعد الشحن: {api_balance}\n🧾 رقم العملية: {charge_id}")
            except TelegramError:
                log.warning("Could not notify owner about API top-up for user %s", uid)
        else:
            await update.effective_message.reply_text(f"⭐ تم تفعيل VIP لمدة {days} يوم.\nينتهي في: {until}")
    except Exception:
        log.exception("Payment processing failed")
        await update.effective_message.reply_text("تم استلام إشعار الدفع لكن تعذرت معالجته. تواصل مع الإدارة مع الاحتفاظ بإيصال الدفع.")


async def manual_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not message.photo:
        return
    if context.user_data.get("state") != "manual_receipt":
        return
    uid = user.id
    method = context.user_data.get("manual_method")
    amount = context.user_data.get("manual_amount_usd")
    reference = context.user_data.get("manual_reference", "")
    if method not in MANUAL_PAYMENT_METHODS or not amount:
        context.user_data.clear()
        await message.reply_text("انتهت جلسة طلب الدفع. ابدأ من زر شحن النقاط.")
        return
    receipt_id = message.photo[-1].file_id
    with db() as c:
        cur = c.execute("""INSERT INTO manual_deposits(user_id,method,amount_usd,reference,receipt_file_id,status,created)
                           VALUES(?,?,?,?,?,'pending',?)""",
                        (uid, method, float(amount), reference[:300], receipt_id, datetime.now(timezone.utc).isoformat()))
        rid = cur.lastrowid
    context.user_data.clear()
    await message.reply_text(f"✅ تم إرسال طلب الدفع اليدوي #{rid} إلى الإدارة للمراجعة. لن يُضاف الرصيد إلا بعد قبول الإيصال.", reply_markup=home_keyboard(uid))
    try:
        await context.bot.send_photo(
            chat_id=OWNER_ID, photo=receipt_id,
            caption=(f"🧾 طلب دفع يدوي جديد #{rid}\nالمستخدم: {uid}\n"
                     f"الطريقة: {MANUAL_PAYMENT_METHODS[method]}\nالمبلغ: ${float(amount):.2f}\n"
                     f"مرجع العملية: {reference or 'غير مرفق'}"),
            reply_markup=kb([[btn("🔎 مراجعة الطلب", f"payreq:{rid}")]])
        )
    except TelegramError:
        log.exception("Could not notify owner about manual deposit %s", rid)
        await message.reply_text("تنبيه: تعذر إرسال الإشعار للمشرف. افتح لوحة الإدارة > طلبات الدفع اليدوي.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Keep polling alive on per-update failures and log enough context to diagnose them.
    err = context.error
    if isinstance(err, NetworkError):
        log.warning("Temporary Telegram network error while handling update: %s", err.__class__.__name__)
        return
    log.error("Unhandled exception while handling update: %s", err, exc_info=err)


# =========================================================
# PUBLIC CUSTOMER API SERVER (aiohttp)
# =========================================================
async def send_api_event_notice(bot, user_id, user_text, owner_text=None):
    """Send safe API-operation notifications to the customer and owner."""
    if bot is None:
        return
    try:
        await bot.send_message(chat_id=int(user_id), text=user_text)
    except (TelegramError, TypeError, ValueError):
        log.info("Could not send API event notice to user %s", user_id)
    if owner_text and int(user_id) != int(OWNER_ID):
        try:
            await bot.send_message(chat_id=OWNER_ID, text=owner_text)
        except (TelegramError, TypeError, ValueError):
            log.info("Could not send API event notice to owner for user %s", user_id)


def api_url_display():
    """Return the public API URL from explicit config or common hosting domains."""
    configured = (os.getenv("API_PUBLIC_URL", "").strip()
                  or get_setting("api_public_url", "").strip())
    if not configured:
        # Common hosting platforms expose the public hostname through environment variables.
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
        if railway_domain:
            configured = railway_domain if railway_domain.startswith(("http://", "https://")) else "https://" + railway_domain
        elif render_url:
            configured = render_url
    if configured:
        configured = configured.rstrip("/")
        if configured.startswith("https://"):
            configured = configured.removesuffix("/api/v1").removesuffix("/api/v2").rstrip("/")
            return configured + "/api/v2"
    return ("غير مضبوط بعد — يجب نشر خادم API على استضافة عامة مع HTTPS، ثم ضبط "
            "API_PUBLIC_URL على النطاق العام الأساسي. تشغيله على Pydroid 3 وحده لا ينشئ رابطاً عاماً.")


def api_client_status(uid):
    with db() as c:
        row = c.execute("SELECT active,balance FROM api_clients WHERE user_id=?", (uid,)).fetchone()
    if row is None:
        return "غير منشأ"
    return ("فعال" if row["active"] else "موقوف") + f" | الرصيد {row['balance']}"

async def customer_api(request):
    if request.method == "GET":
        return web.json_response({"ok": True, "service": "SMM Customer API", "endpoint": "/api/v2", "compatible_endpoints": ["/api/v2", "/api/v1"], "auth": "Bearer API_KEY or form field key", "actions": ["services", "balance", "add", "status"]})
    # Accept both JSON/Bearer requests and the classic SMM-panel form format
    # (application/x-www-form-urlencoded: key=...&action=services).
    try:
        if request.content_type == "application/json":
            data = await request.json()
        else:
            data = dict(await request.post())
    except Exception:
        return web.json_response({"error": "JSON or form-encoded body required"}, status=400)
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else str(data.get("key", ""))
    if not token or len(token) < 20:
        return web.json_response({"error": "API key required"}, status=401)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db() as c:
        client = c.execute("SELECT * FROM api_clients WHERE token_hash=?", (token_hash,)).fetchone()
    if not client or not client["active"]:
        return web.json_response({"error": "Invalid or disabled API key"}, status=401)
    uid = int(client["user_id"])
    action = str(data.get("action", "")).lower()
    if action == "balance":
        with db() as c:
            row = c.execute("SELECT balance FROM api_clients WHERE user_id=?", (uid,)).fetchone()
        return web.json_response({"ok": True, "balance": row["balance"]})
    if action == "services":
        with db() as c:
            rows = c.execute("SELECT s.id,s.name,s.category,s.price_points,s.min_qty,s.max_qty,s.platform,s.price_usd FROM services s JOIN providers p ON p.id=s.provider_id WHERE s.enabled=1 AND p.enabled=1 ORDER BY s.id").fetchall()
        # Classic SMM panel clients expect an array with service/name/type/category/rate/min/max.
        classic = [{"service": int(r["id"]), "name": r["name"], "type": "Default",
                    "category": (r["category"] or r["platform"] or "Other"),
                    "rate": str(r["price_points"]), "min": int(r["min_qty"] or 1),
                    "max": int(r["max_qty"] or 100000),
                    "currency": "POINTS"} for r in rows]
        if request.content_type != "application/json" and not auth.lower().startswith("bearer "):
            return web.json_response(classic)
        return web.json_response({"ok": True, "services": [dict(r) for r in rows]})
    if action == "status":
        try: order_id = int(data.get("order", 0))
        except (ValueError, TypeError): return web.json_response({"error":"order must be an integer"}, status=400)
        with db() as c:
            row = c.execute("SELECT a.id,a.client_order_id,a.provider_order_id,a.service_id,a.cost,a.status,a.created,s.name,s.provider_id,p.api_url,p.api_key,p.enabled AS provider_enabled FROM api_orders a JOIN services s ON s.id=a.service_id JOIN providers p ON p.id=s.provider_id WHERE a.id=? AND a.user_id=?", (order_id,uid)).fetchone()
        if not row: return web.json_response({"error":"Order not found"}, status=404)
        status_text = str(row["status"] or "pending")
        if row["provider_order_id"] and row["provider_enabled"]:
            try:
                provider_status = await api_call(row, "status", {"order": row["provider_order_id"]})
                if isinstance(provider_status, dict):
                    status_text = str(provider_status.get("status", status_text))
                    with db() as c:
                        c.execute("UPDATE api_orders SET status=? WHERE id=? AND user_id=?", (status_text, order_id, uid))
            except Exception as exc:
                log.warning("Could not refresh provider status for API order %s: %s", order_id, exc)
        return web.json_response({"charge": row["cost"], "start_count": "", "status": status_text, "remains": "", "currency": "POINTS", "order": order_id, "client_order_id": row["client_order_id"]})
    if action != "add":
        return web.json_response({"error":"Unknown action"}, status=400)
    try:
        service_id=int(data.get("service",0)); qty=int(data.get("quantity",0)); link=str(data.get("link", "")).strip(); client_order_id=str(data.get("client_order_id", "")).strip() or ("panel-" + secrets.token_hex(12))
        if not link.startswith(("http://","https://")) or qty < 1 or len(client_order_id)>100: raise ValueError()
    except (ValueError,TypeError):
        return web.json_response({"error":"service, valid http(s) link, positive quantity and client_order_id are required"}, status=400)
    with db() as c:
        duplicate=c.execute("SELECT id,status,cost FROM api_orders WHERE user_id=? AND client_order_id=?", (uid,client_order_id)).fetchone()
        if duplicate: return web.json_response({"ok":True,"order":duplicate["id"],"status":duplicate["status"],"duplicate":True})
        service=c.execute("SELECT s.*,p.api_url,p.api_key,p.enabled provider_enabled FROM services s JOIN providers p ON p.id=s.provider_id WHERE s.id=? AND s.enabled=1",(service_id,)).fetchone()
        if not service: return web.json_response({"error":"Service not found or disabled"},status=404)
        if qty < int(service["min_qty"] or 1) or qty > int(service["max_qty"] or 100000): return web.json_response({"error":"Quantity outside service limits"},status=400)
        if not service["provider_enabled"]: return web.json_response({"error":"Provider disabled"},status=400)
        unit=max(0,int(service["price_points"] or 0)); cost=max(1, math.ceil(unit*qty/1000))
        c.execute("BEGIN IMMEDIATE")
        current=c.execute("SELECT balance,active FROM api_clients WHERE user_id=?",(uid,)).fetchone()
        if not current or not current["active"]: return web.json_response({"error":"API account disabled"},status=401)
        if current["balance"] < cost: return web.json_response({"error":"Insufficient API balance","required":cost,"balance":current["balance"]},status=402)
        c.execute("UPDATE api_clients SET balance=balance-?,updated=? WHERE user_id=? AND balance>=?",(cost,datetime.now(timezone.utc).isoformat(),uid,cost))
        cur=c.execute("INSERT INTO api_orders(user_id,client_order_id,service_id,cost,status,created) VALUES(?,?,?,?,'submitting',?)",(uid,client_order_id,service_id,cost,datetime.now(timezone.utc).isoformat()))
        api_order_id=cur.lastrowid
        c.execute("INSERT INTO api_ledger(user_id,amount,kind,reference,details,created) VALUES(?,?,'order_debit',?,?,?)",(uid,-cost,f"api-order:{api_order_id}",f"Service {service_id}; qty {qty}",datetime.now(timezone.utc).isoformat()))
    try:
        result=await api_call(service,"add",{"service":service["external_id"],"link":link,"quantity":qty})
        provider_id=str(result.get("order", "")) if isinstance(result,dict) else ""
        if not provider_id: raise RuntimeError("Provider did not confirm order")
        with db() as c:
            c.execute("UPDATE api_orders SET provider_order_id=?,status='submitted' WHERE id=?", (provider_id, api_order_id))
            remaining = c.execute("SELECT balance FROM api_clients WHERE user_id=?", (uid,)).fetchone()
        bot = request.app.get("telegram_bot")
        await send_api_event_notice(
            bot, uid,
            f"✅ تم تنفيذ طلبك عبر API\n🆔 رقم طلب API: #{api_order_id}\n📦 الخدمة: {service['name']}\n🔢 الكمية: {qty}\n💳 التكلفة: {cost} نقطة\n💰 الرصيد المتبقي: {int(remaining['balance']) if remaining else 'غير متاح'}",
            f"🔔 طلب API جديد تم إرساله للمزود\n👤 المستخدم: {uid}\n🆔 طلب API: #{api_order_id}\n🆔 طلب المزود: {provider_id}\n🛍 الخدمة: {service['name']}\n🔢 الكمية: {qty}\n💳 التكلفة: {cost} نقطة\n📌 الحالة: submitted"
        )
        if request.content_type != "application/json" and not auth.lower().startswith("bearer "):
            return web.json_response({"order": api_order_id})
        return web.json_response({"ok":True,"order":api_order_id,"provider_order_id":provider_id,"charge":cost,"status":"submitted"})
    except Exception as exc:
        log.warning("API provider submit failed for order %s: %s",api_order_id,exc)
        with db() as c:
            c.execute("UPDATE api_clients SET balance=balance+?,updated=? WHERE user_id=?",(cost,datetime.now(timezone.utc).isoformat(),uid))
            c.execute("INSERT OR IGNORE INTO api_ledger(user_id,amount,kind,reference,details,created) VALUES(?,?,'refund',?,?,?)",(uid,cost,f"api-refund:{api_order_id}","Provider submission failed; refunded",datetime.now(timezone.utc).isoformat()))
            c.execute("UPDATE api_orders SET status='failed' WHERE id=?",(api_order_id,))
            restored = c.execute("SELECT balance FROM api_clients WHERE user_id=?", (uid,)).fetchone()
        bot = request.app.get("telegram_bot")
        await send_api_event_notice(
            bot, uid,
            f"⚠️ تعذر إرسال طلب API #{api_order_id} للمزود. تمت إعادة {cost} نقطة إلى رصيدك.\n💰 رصيدك الحالي: {int(restored['balance']) if restored else 'غير متاح'}",
            f"⚠️ فشل طلب API وتم رد الرصيد\n👤 المستخدم: {uid}\n🆔 طلب API: #{api_order_id}\n💳 المبلغ المسترد: {cost} نقطة\n📄 السبب: {str(exc)[:250]}"
        )
        return web.json_response({"error":"Provider submission failed; balance refunded","order":api_order_id},status=502)

async def start_api_server(application):
    host=os.getenv("API_HOST", "0.0.0.0")
    # Railway/Render and similar platforms usually provide PORT; API_PORT remains supported locally.
    port=int(os.getenv("PORT", os.getenv("API_PORT", "8080")))
    app=web.Application(client_max_size=1024*64)
    app["telegram_bot"] = application.bot
    # /api/v2 is the standard endpoint for most SMM panels; /api/v1 remains as an alias.
    app.router.add_route("GET","/api/v1",customer_api)
    app.router.add_route("POST","/api/v1",customer_api)
    app.router.add_route("GET","/api/v2",customer_api)
    app.router.add_route("POST","/api/v2",customer_api)
    # Lightweight health endpoint for hosting health checks.
    async def health_check(request):
        return web.json_response({"ok": True, "service": "SMM Customer API", "endpoint": "/api/v2"})
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner=web.AppRunner(app)
    await runner.setup()
    site=web.TCPSite(runner,host,port)
    await site.start()
    application.bot_data["customer_api_runner"]=runner
    log.info("Customer API listening on %s:%s. For external clients set API_PUBLIC_URL to a real public HTTPS tunnel/domain; the phone itself does not create a public URL.",host,port)

async def stop_api_server(application):
    runner=application.bot_data.get("customer_api_runner")
    if runner: await runner.cleanup()

# =========================================================
# Automatic provider status monitor (website is the source of truth)
# =========================================================
async def monitor_provider_orders(application):
    """Poll provider statuses with bounded concurrency and one-time state updates."""
    semaphore = asyncio.Semaphore(4)  # avoid slow sequential polling without flooding providers

    async def check_one(order):
        async with semaphore:
            try:
                status_result = await api_call(
                    order, "status", {"order": order["provider_order_id"]}
                )
                if not isinstance(status_result, dict):
                    return
                raw_status = " ".join(
                    str(status_result.get("status", "")).strip().casefold().split()
                )
                if not raw_status:
                    return

                if raw_status in {
                    "completed", "complete", "completed successfully",
                    "done", "finished",
                }:
                    with db() as c:
                        cur = c.execute(
                            "UPDATE orders SET status='completed' WHERE id=? AND status='submitted'",
                            (order["id"],),
                        )
                        if cur.rowcount != 1:
                            return
                    try:
                        await application.bot.send_message(
                            chat_id=order["user_id"],
                            text=render_template(
                                "order_complete", order_id=order["id"],
                                user_id=order["user_id"], service_name=order["service_name"],
                                quantity=order["quantity"], cost=order["cost_points"],
                                link=order["link"],
                            ),
                        )
                    except TelegramError:
                        # State remains final; log delivery failure rather than
                        # repeatedly changing the order or risking duplicate refunds.
                        log.exception("Could not notify user about completed order %s", order["id"])

                # Generic canceled/rejected/failed statuses are deliberately ignored.
                # Only explicit manual-admin rejection labels cause a rejection notice.
                elif raw_status in {
                    "canceled by admin", "cancelled by admin",
                    "canceled by owner", "cancelled by owner",
                    "rejected by admin", "rejected by owner",
                    "manually rejected", "rejected manually",
                }:
                    with db() as c:
                        cur = c.execute(
                            "UPDATE orders SET status='rejected' WHERE id=? AND status='submitted'",
                            (order["id"],),
                        )
                        if cur.rowcount != 1:
                            return
                    try:
                        await application.bot.send_message(
                            chat_id=order["user_id"],
                            text=render_template(
                                "order_rejected", order_id=order["id"],
                                user_id=order["user_id"], service_name=order["service_name"],
                                quantity=order["quantity"], cost=order["cost_points"],
                                link=order["link"],
                            ),
                        )
                    except TelegramError:
                        log.exception("Could not notify user about manually rejected order %s", order["id"])
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Provider status check failed for order %s", order["id"])

    while True:
        try:
            with db() as c:
                rows = c.execute("""
                    SELECT o.*, s.name AS service_name, s.provider_id,
                           p.api_url, p.api_key, p.enabled AS provider_enabled
                    FROM orders o
                    JOIN services s ON s.id=o.service_id
                    JOIN providers p ON p.id=s.provider_id
                    WHERE o.status='submitted' AND COALESCE(o.provider_order_id,'')<>''
                    ORDER BY o.id ASC LIMIT 100
                """).fetchall()
            if rows:
                await asyncio.gather(*(check_one(order) for order in rows))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Provider order monitor cycle failed")
        try:
            poll_seconds = int(get_setting("provider_status_poll_seconds", "30"))
        except (TypeError, ValueError):
            poll_seconds = 30
        await asyncio.sleep(max(15, min(poll_seconds, 3600)))

async def start_order_monitor(application):
    # Create the pooled session once during startup and reuse it for all providers.
    await get_http_session()
    application.bot_data["provider_order_monitor_task"] = asyncio.create_task(monitor_provider_orders(application))
    await start_api_server(application)

async def stop_order_monitor(application):
    global _HTTP_SESSION
    task = application.bot_data.get("provider_order_monitor_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Provider monitor shutdown error")
    await stop_api_server(application)
    if _HTTP_SESSION is not None and not _HTTP_SESSION.closed:
        await _HTTP_SESSION.close()
    _HTTP_SESSION = None

# =========================================================
# APPLICATION ENTRY POINT
# بيانات المبرمج تظهر قبل أي طلب لتوكن البوت
# =========================================================
def show_programmer_banner():
    print("=" * 58)
    print("💎✨ 𝗠𝗔𝗛𝗠𝗢𝗨𝗗 | محمود - ULTIMATE SMM ✨💎")
    print(f"المبرمج: {PROGRAMMER_NAME}")
    print(f"تيليجرام المبرمج: {PROGRAMMER_TELEGRAM}")
    print(f"المنطقة: {OWNER_REGION_LABEL}")
    print(f"قناة تيليجرام: {REQUIRED_CHANNEL_URL}")
    print("=" * 58)


def startup_access_gate():
    """Open the owner's channel first, then require the tool password.

    This is a local launch gate for the Python script. It cannot verify a
    Telegram subscription by itself; actual subscription verification remains
    inside the Telegram bot after it starts.
    """
    show_programmer_banner()
    print("\nسيتم فتح قناة محمود. افتح الرابط، ثم ارجع إلى التطبيق/الطرفية.")
    try:
        opened = webbrowser.open(REQUIRED_CHANNEL_URL, new=2)
        if not opened:
            print("إذا لم يفتح الرابط تلقائياً، افتحه يدوياً:")
            print(REQUIRED_CHANNEL_URL)
    except Exception as exc:
        print("تعذّر فتح الرابط تلقائياً؛ افتحه يدوياً:")
        print(REQUIRED_CHANNEL_URL)
        log.debug("Could not open channel URL automatically: %s", exc)

    try:
        input("بعد الرجوع من القناة، اضغط Enter للمتابعة...")
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("تم إلغاء التشغيل.")

    # Password is deliberately requested BEFORE the bot token.
    for attempt in range(3):
        try:
            entered = getpass("أدخل كلمة مرور الأداة للمتابعة: ")
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("تم إلغاء التشغيل.")
        if entered == ACCESS_PASSWORD:
            print("✅ كلمة المرور صحيحة. متابعة التشغيل...\n")
            return
        remaining = 2 - attempt
        if remaining:
            print(f"❌ كلمة المرور غير صحيحة. المحاولات المتبقية: {remaining}")
    raise SystemExit("⛔ تم إيقاف الأداة بسبب إدخال كلمة مرور خاطئة 3 مرات.")


def main():
    global BOT_TOKEN, OWNER_ID

    # For a real background/server deployment set RUN_HEADLESS=1. Interactive
    # phone launches keep the existing local access gate by default.
    # This gate is not a server supervisor; use the hosting platform's restart policy.
    if os.getenv("RUN_HEADLESS", "1").strip().lower() not in {"1", "true", "yes"}:
        startup_access_gate()
    else:
        show_programmer_banner()
        log.info("Headless mode enabled; skipping interactive startup prompts")

    # In mobile Python environments (such as Pydroid), ask for credentials
    # interactively when environment variables have not been configured.
    headless = os.getenv("RUN_HEADLESS", "1").strip().lower() in {"1", "true", "yes"}
    if not BOT_TOKEN and headless:
        raise RuntimeError("وضع الخلفية يحتاج BOT_TOKEN كمتغير بيئة قبل التشغيل.")
    if not BOT_TOKEN:
        BOT_TOKEN = input("أدخل توكن بوت تيليجرام من BotFather: ").strip()
    if not BOT_TOKEN:
        raise RuntimeError("توكن البوت فارغ. أعد التشغيل وأدخل التوكن الصحيح.")

    if OWNER_ID <= 0 and headless:
        raise RuntimeError("وضع الخلفية يحتاج OWNER_ID كمتغير بيئة قبل التشغيل.")
    if OWNER_ID <= 0:
        owner_text = input("أدخل Telegram ID الخاص بك (معرّف المشرف): ").strip()
        try:
            OWNER_ID = int(owner_text)
            if OWNER_ID <= 0:
                raise ValueError
        except ValueError as exc:
            raise RuntimeError("Telegram ID غير صحيح؛ أدخل أرقام المعرّف فقط.") from exc

    init_db()
    print(f"قاعدة البيانات المستخدمة: {os.path.abspath(DB_FILE)}")
    if os.getenv("RUN_HEADLESS", "1").strip().lower() in {"1", "true", "yes"}:
        print("وضع الخلفية مفعّل. اجعل منصة الاستضافة تعيد التشغيل تلقائياً عند التعطل.")
    # Increase connection timeouts to tolerate slow mobile networks.
    request = HTTPXRequest(
        connection_pool_size=24,
        connect_timeout=15.0,
        read_timeout=25.0,
        write_timeout=20.0,
        pool_timeout=10.0,
    )
    updates_request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=15.0,
        read_timeout=25.0,
        write_timeout=20.0,
        pool_timeout=10.0,
    )
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(updates_request)
        .concurrent_updates(24)
        .post_init(start_order_monitor)
        .post_shutdown(stop_order_monitor)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(MessageHandler(filters.PHOTO, manual_receipt_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    log.info("ULTIMATE SMM bot is starting | Programmer: %s (%s) | Region label: %s", PROGRAMMER_NAME, PROGRAMMER_TELEGRAM, OWNER_REGION_LABEL)
    # Retry startup after transient network failures (e.g. httpx.ConnectError).
    # This cannot fix a blocked/offline connection, but avoids exiting on a brief outage.
    retry_delay = 5
    while True:
        try:
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                bootstrap_retries=-1,
                close_loop=True,
            )
            break  # normal stop (e.g. Ctrl+C)
        except NetworkError as exc:
            log.error(
                "تعذر الاتصال بواجهة Telegram API: %s. ستتم إعادة المحاولة بعد %s ثانية. "
                "تحقق من الإنترنت أو حجب تيليجرام على الشبكة.",
                exc.__class__.__name__, retry_delay,
            )
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
        except KeyboardInterrupt:
            log.info("تم إيقاف البوت يدويًا.")
            break

if __name__ == "__main__":
    main()
