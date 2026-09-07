#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Will Be Earn Shop - Telegram Bot + Website Admin Panel (single-file project)

Requirements:
    pip install "python-telegram-bot>=22.7,<23" "Flask>=3.0,<4"

Environment variables (recommended):
    BOT_TOKEN=123456:ABC...
    ADMIN_USERNAME=admin
    ADMIN_PASSWORD=change-me-now
    SECRET_KEY=change-this-secret
    ADMIN_HOST=0.0.0.0
    ADMIN_PORT=8080

Run:
    python bot.py

Open admin panel:
    http://YOUR_SERVER_IP:8080

IMPORTANT:
- Use this marketplace only for products/content you are legally allowed to sell.
- Auto Stock can instantly deliver generic digital items/codes that you are authorized to distribute.
- Do not use Auto Stock to distribute third-party login credentials or unauthorized content.
- Manual Delivery remains available when ready stock is unavailable.
"""

import os
import re
import html
import json
import time
import sqlite3
import secrets
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from functools import wraps

from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "shop.db")
ADMIN_HOST = os.getenv("ADMIN_HOST", "0.0.0.0")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8080"))
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-ME-" + secrets.token_hex(16))
DEFAULT_ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "admin_uploads")
MAX_DELIVERY_FILE_MB = int(os.getenv("MAX_DELIVERY_FILE_MB", "45"))
MAX_DELIVERY_FILE_BYTES = MAX_DELIVERY_FILE_MB * 1024 * 1024
ALLOWED_DELIVERY_EXTENSIONS = {
    "txt", "pdf", "zip", "rar", "7z",
    "jpg", "jpeg", "png", "webp",
    "doc", "docx", "xls", "xlsx",
    "apk"
}
os.makedirs(UPLOAD_DIR, exist_ok=True)

SUPPORT_USERNAME_DEFAULT = "Ariyan_Ahamed_Ari"
HOTMAIL_URL_DEFAULT = "https://dongvanfb.net/read_mail_box/"
FR_OUTLOOK_URL_DEFAULT = "https://dongvanfb.net/read_mail_box/"
API_GMAIL_URL_DEFAULT = "https://tridib.codes/"

MAIN_BUY = "Buy Products"
MAIN_PROFILE = "My Profile"
MAIN_DEPOSIT = "Deposit"
MAIN_CODE = "Get Code"
MAIN_SUPPORT = "Support"
MAIN_USDT_SELL = "USDT Sell"
MAIN_LANGUAGE = "Language"

DB_LOCK = threading.RLock()


# Telegram button custom-emoji registry.
# Admin can set/replace/clear every ID from:
# Website Admin Panel -> Button Emojis
BUTTON_EMOJI_DEFINITIONS = {
    "main_buy_products": "Buy Products",
    "main_profile": "My Profile",
    "main_deposit": "Deposit",
    "main_get_code": "Get Code",
    "main_support": "Support",
    "main_usdt_sell": "USDT Sell",
    "main_language": "Language",

    "category_vpn": "VPN",
    "category_proxy": "Proxy",
    "category_mail": "Mail",
    "category_premium_apk": "Premium Apk",

    "product_item_mail": "Mail product row",
    "product_item_vpn": "VPN product row",
    "product_item_proxy": "Proxy product row",
    "product_item_premium_apk": "Premium Apk product row",

    "profile_balance": "Balance Details",
    "profile_deposits": "Deposit History",
    "profile_referral": "Referral",
    "profile_purchases": "Purchases",

    "confirm_order": "Confirm Order",
    "deposit_paid": "Paid",
    "deposit_screenshot": "Screenshot",
    "support_message_admin": "Message Admin",

    "code_hotmail": "Hotmail/Outlook",
    "code_fr_outlook": "Fr Outlook Code",
    "code_api_gmail": "API Gmail Code",

    "back": "Back",
    "cancel": "Cancel",
}


MESSAGE_EMOJI_DEFINITIONS = {
    "welcome": "Welcome / Start",
    "balance": "Balance",
    "menu_hint": "Menu Hint",

    "buy_products": "Buy Products",
    "profile": "Profile",
    "profile_name": "Profile Name",
    "profile_joined": "Profile Joined",
    "bdt_balance": "BDT Balance",
    "usdt_balance": "USDT Balance",
    "how_it_works": "How It Works",

    "deposit": "Deposit",
    "bkash": "bKash",
    "nagad": "Nagad",
    "binance": "Binance Deposit",
    "cash_voucher": "Cash Voucher",
    "rocket": "Rocket",

    "get_code": "Get Code",
    "support": "Support",
    "usdt_sell": "USDT Sell",
    "language": "Language",

    "mail": "Mail",
    "vpn": "VPN",
    "proxy": "Proxy",
    "premium_apk": "Premium Apk",

    "order_summary": "Order Summary",
    "order_success": "Order Success",
    "order_id": "Order ID",
    "product": "Product",
    "quantity": "Quantity",
    "total": "Total",
    "delivery_time": "Delivery Time",
    "thank_you": "Thank You",
    "insufficient_balance": "Insufficient Balance",
    "insufficient_stock": "Insufficient Stock",

    "deposit_pending": "Deposit Pending",
    "transaction_id": "Transaction ID",
    "payment_screenshot": "Payment Screenshot",
    "deposit_approved": "Deposit Approved",
    "deposit_rejected": "Deposit Rejected",

    "referral": "Referral",
    "purchases": "Purchases",
    "history": "History",
    "warning": "Warning",
    "success": "Success",
    "error": "Error",
}


MESSAGE_TEMPLATE_DEFINITIONS = {
    "order_placed": {
        "label": "Order Placed Successfully",
        "body": (
            "[[emoji_key:order_success]] <b>Order Placed Successfully!</b>\n\n"
            "[[emoji_key:order_id]] Order ID: <b>#{order_id}</b>\n"
            "[[emoji_key:product]] Product: <b>{product_name}</b>\n"
            "[[emoji_key:quantity]] Quantity: <b>{quantity}</b>\n"
            "[[emoji_key:total]] Total: <b>{total_bdt} BDT</b>\n\n"
            "[[emoji_key:delivery_time]] <b>Delivery Time: Within {delivery_minutes} Minutes</b>\n\n"
            "আপনার অর্ডার Admin-এর কাছে পাঠানো হয়েছে। "
            "Admin order accept করে Text/File/App পাঠালেই আপনি এই bot-এর chat-এ পেয়ে যাবেন।\n\n"
            "[[emoji_key:thank_you]] Thank you for your order!"
        ),
    },
    "order_waiting": {
        "label": "Order Waiting For Stock",
        "body": (
            "[[emoji_key:warning]] <b>Order Received — Please Wait</b>\n\n"
            "[[emoji_key:order_id]] Order ID: <b>#{order_id}</b>\n"
            "[[emoji_key:product]] Product: <b>{product_name}</b>\n"
            "[[emoji_key:quantity]] Quantity: <b>{quantity}</b>\n"
            "[[emoji_key:total]] Total: <b>{total_bdt} BDT</b>\n\n"
            "এই মুহূর্তে Ready Stock পর্যাপ্ত নেই। আপনার order Pending রাখা হয়েছে।\n"
            "Stock ready হলে Admin এই bot-এর chat-এ delivery পাঠাবে।"
        ),
    },
    "order_auto_delivery": {
        "label": "Instant Auto Stock Delivery",
        "body": (
            "[[emoji_key:success]] <b>Instant Delivery Completed!</b>\n\n"
            "[[emoji_key:order_id]] Order ID: <b>#{order_id}</b>\n"
            "[[emoji_key:product]] Product: <b>{product_name}</b>\n"
            "[[emoji_key:quantity]] Quantity: <b>{quantity}</b>\n\n"
            "Your purchased stock has been sent below."
        ),
    },
    "order_accepted": {
        "label": "Order Accepted",
        "body": (
            "[[emoji_key:success]] <b>Your Order Has Been Accepted!</b>\n\n"
            "[[emoji_key:order_id]] Order ID: <b>#{order_id}</b>\n"
            "[[emoji_key:product]] Product: <b>{product_name}</b>\n\n"
            "[[emoji_key:success]] Your delivery is ready."
        ),
    },
    "order_delivery_text": {
        "label": "Order Delivery Text Header",
        "body": (
            "[[emoji_key:product]] <b>Order Delivery</b>\n\n"
            "{delivery_text}"
        ),
    },
    "order_rejected": {
        "label": "Order Rejected / Refunded",
        "body": (
            "[[emoji_key:error]] <b>Order Rejected</b>\n\n"
            "Order #{order_id} could not be fulfilled.\n"
            "[[emoji_key:balance]] {refund_bdt} BDT has been returned to your balance."
        ),
    },
    "deposit_approved": {
        "label": "Deposit Approved",
        "body": (
            "[[emoji_key:deposit_approved]] <b>Deposit Approved</b>\n\n"
            "Amount: {amount_bdt} BDT\n"
            "{bonus_line}\n"
            "Your balance has been updated."
        ),
    },
    "deposit_rejected": {
        "label": "Deposit Rejected",
        "body": (
            "[[emoji_key:deposit_rejected]] <b>Deposit Rejected</b>\n\n"
            "Your deposit could not be verified.\n"
            "Please contact support if you believe this is an error."
        ),
    },
}


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    con = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def db_execute(sql, params=(), fetchone=False, fetchall=False):
    with DB_LOCK:
        con = db_connect()
        try:
            cur = con.execute(sql, params)
            con.commit()
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            return cur.lastrowid
        finally:
            con.close()


def init_db():
    with DB_LOCK:
        con = db_connect()
        cur = con.cursor()

        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT NOT NULL,
            bdt_balance REAL NOT NULL DEFAULT 0,
            usdt_balance REAL NOT NULL DEFAULT 0,
            joined_at TEXT NOT NULL,
            referred_by INTEGER,
            referral_count INTEGER NOT NULL DEFAULT 0,
            first_deposit_bonus_used INTEGER NOT NULL DEFAULT 0,
            banned INTEGER NOT NULL DEFAULT 0,
            language TEXT NOT NULL DEFAULT 'bn'
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            price_bdt REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            delivery_mode TEXT NOT NULL DEFAULT 'manual',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS product_stock_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            order_id INTEGER,
            created_at TEXT NOT NULL,
            sold_at TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_product_stock_available
        ON product_stock_items(product_id, status, id);

        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            amount_bdt REAL NOT NULL,
            trx_id TEXT,
            screenshot_file_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT,
            note TEXT,
            UNIQUE(trx_id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price_bdt REAL NOT NULL,
            total_bdt REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            delivery_text TEXT,
            delivery_file_name TEXT,
            delivery_file_path TEXT,
            delivered_at TEXT,
            delivered_by TEXT,
            stock_deducted INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS button_emojis (
            button_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            emoji_id TEXT NOT NULL DEFAULT '',
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS message_emojis (
            emoji_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            emoji_id TEXT NOT NULL DEFAULT '',
            fallback TEXT NOT NULL DEFAULT '⭐',
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS message_templates (
            template_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            body TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS force_join_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            button_name TEXT NOT NULL,
            join_url TEXT NOT NULL,
            check_chat TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            icon TEXT NOT NULL DEFAULT '💵',
            account_number TEXT NOT NULL DEFAULT '',
            instructions TEXT NOT NULL DEFAULT '',
            min_deposit REAL NOT NULL DEFAULT 20,
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_username TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # Migrate older databases without deleting existing data.
        user_columns = {
            row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()
        }
        if "language" not in user_columns:
            cur.execute("ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'bn'")

        product_columns = {
            row["name"] for row in cur.execute("PRAGMA table_info(products)").fetchall()
        }
        if "delivery_mode" not in product_columns:
            cur.execute("ALTER TABLE products ADD COLUMN delivery_mode TEXT NOT NULL DEFAULT 'manual'")

        order_columns = {
            row["name"] for row in cur.execute("PRAGMA table_info(orders)").fetchall()
        }
        order_migrations = {
            "delivery_text": "ALTER TABLE orders ADD COLUMN delivery_text TEXT",
            "delivery_file_name": "ALTER TABLE orders ADD COLUMN delivery_file_name TEXT",
            "delivery_file_path": "ALTER TABLE orders ADD COLUMN delivery_file_path TEXT",
            "delivered_at": "ALTER TABLE orders ADD COLUMN delivered_at TEXT",
            "delivered_by": "ALTER TABLE orders ADD COLUMN delivered_by TEXT",
            # Older versions deducted numeric stock for every order. Mark legacy
            # rows as stock-deducted so old refunds keep behaving correctly.
            "stock_deducted": "ALTER TABLE orders ADD COLUMN stock_deducted INTEGER NOT NULL DEFAULT 1",
        }
        for col, sql in order_migrations.items():
            if col not in order_columns:
                cur.execute(sql)

        defaults = {
            "bot_username": "will_be_eran_shop_bot",
            "support_username": SUPPORT_USERNAME_DEFAULT,
            "usdt_rate": "125.0",
            "min_deposit": "20.0",
            "referral_percent": "25.0",
            "first_deposit_bonus_percent": "10.0",
            "delivery_minutes": "10",
            "usdt_sell_rate": "125",
            "usdt_sell_admin_username": "Ariyan_Ahamed_Ari",
            "usdt_sell_enabled": "1",
            "bkash_number": "01833878871",
            "nagad_number": "",
            "rocket_number": "",
            "binance_usdt_address": "",
            "cash_voucher_note": "Contact support for voucher instructions.",
            "hot_mail_url": HOTMAIL_URL_DEFAULT,
            "fr_outlook_url": FR_OUTLOOK_URL_DEFAULT,
            "api_gmail_url": API_GMAIL_URL_DEFAULT,
        }
        for k, v in defaults.items():
            cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))

        # Seed all known Telegram button emoji slots.
        for button_key, label in BUTTON_EMOJI_DEFINITIONS.items():
            cur.execute(
                "INSERT OR IGNORE INTO button_emojis(button_key,label,emoji_id,updated_at) VALUES(?,?,?,?)",
                (button_key, label, "", now_str())
            )

        # Seed all known Telegram message emoji slots.
        message_fallbacks = {
            "welcome": "👋",
            "balance": "💰",
            "menu_hint": "📌",
            "buy_products": "🛍️",
            "profile": "👤",
            "profile_name": "👤",
            "profile_joined": "📅",
            "bdt_balance": "💵",
            "usdt_balance": "💴",
            "how_it_works": "📌",

            "deposit": "💳",
            "bkash": "💳",
            "nagad": "💳",
            "binance": "💛",
            "cash_voucher": "🎫",
            "rocket": "💳",

            "get_code": "🔑",
            "support": "🆘",
            "usdt_sell": "💵",
            "language": "🌐",
            "mail": "📧",
            "vpn": "🛡️",
            "proxy": "🌐",
            "premium_apk": "📱",
            "order_summary": "🧾",
            "order_success": "✅",
            "order_id": "🧾",
            "product": "📦",
            "quantity": "💎",
            "total": "💰",
            "delivery_time": "⏳",
            "thank_you": "🙏",
            "insufficient_balance": "❌",
            "insufficient_stock": "❌",
            "deposit_pending": "🕘",
            "transaction_id": "🔖",
            "payment_screenshot": "📱",
            "deposit_approved": "✅",
            "deposit_rejected": "❌",
            "referral": "👥",
            "purchases": "🛍️",
            "history": "📜",
            "warning": "⚠️",
            "success": "✅",
            "error": "❌",
        }
        for emoji_key, label in MESSAGE_EMOJI_DEFINITIONS.items():
            cur.execute(
                "INSERT OR IGNORE INTO message_emojis(emoji_key,label,emoji_id,fallback,updated_at) VALUES(?,?,?,?,?)",
                (emoji_key, label, "", message_fallbacks.get(emoji_key, "⭐"), now_str())
            )

        # Install the supplied Premium Message Emoji pack one time only.
        premium_pack_done = cur.execute(
            "SELECT value FROM settings WHERE key='premium_message_pack_20260826_v1'"
        ).fetchone()
        if not premium_pack_done:
            premium_message_ids = {
                "welcome": "5353027129250453493",
                "balance": "6235459831302460476",
                "menu_hint": "5397782960512444700",
                "buy_products": "5406683434124859552",

                "vpn": "5190447043545438788",
                "proxy": "5447410659077661506",
                "mail": "5348494358205207761",

                "profile": "5193063022226086560",
                "profile_name": "5193063022226086560",
                "profile_joined": "6238042150324409739",
                "bdt_balance": "5409048419211682843",
                "usdt_balance": "5402186569006210455",

                "referral": "5420145051336485498",
                "how_it_works": "5397782960512444700",

                "deposit": "5190899075968441286",
                "bkash": "5348469219761626211",
                "nagad": "5352985330628730418",
                "binance": "5348212415077064131",
                "cash_voucher": "5352552689983067014",
                "rocket": "5346042941196507141",

                "get_code": "5296369303661067030",
                "support": "5337302974806922068",
            }
            for emoji_key, emoji_id in premium_message_ids.items():
                cur.execute(
                    "UPDATE message_emojis SET emoji_id=?, updated_at=? WHERE emoji_key=?",
                    (emoji_id, now_str(), emoji_key)
                )
            cur.execute(
                "INSERT OR REPLACE INTO settings(key,value) VALUES('premium_message_pack_20260826_v1','1')"
            )

        # Seed editable message templates.
        for template_key, info in MESSAGE_TEMPLATE_DEFINITIONS.items():
            cur.execute(
                "INSERT OR IGNORE INTO message_templates(template_key,label,body,updated_at) VALUES(?,?,?,?)",
                (template_key, info["label"], info["body"], now_str())
            )

        # Sample products matching the shared UI.
        count = cur.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
        if count == 0:
            now = now_str()
            samples = [
                ("Mail", "Fr Outlook", 0.95, 5176),
                ("Mail", "Hotmail Trusted", 0.90, 1454),
                ("Mail", "Outlook Trusted", 0.90, 1681),
                ("Mail", "Outlook.cl", 1.00, 279),
                ("Mail", "Outlook.cz", 1.00, 404),
            ]
            cur.executemany(
                "INSERT INTO products(category,name,price_bdt,stock,active,created_at) VALUES(?,?,?,?,1,?)",
                [(c, n, p, s, now) for c, n, p, s in samples]
            )

        pm_count = cur.execute("SELECT COUNT(*) c FROM payment_methods").fetchone()["c"]
        if pm_count == 0:
            now = now_str()
            methods = [
                ("bKash", "bkash", "🔴", "01833878871", "Send money to the number below.", 20.0, 1, 10, now),
                ("Nagad", "nagad", "🔴", "", "Send money to the number below.", 20.0, 1, 20, now),
                ("Rocket", "rocket", "🟣", "", "Send money to the number below.", 20.0, 1, 30, now),
                ("Binance (USDT)", "binance", "🟡", "", "Send USDT to the wallet address below.", 20.0, 1, 40, now),
                ("Cash Voucher", "voucher", "🎟️", "", "Contact support for voucher instructions.", 20.0, 1, 50, now),
            ]
            cur.executemany(
                "INSERT INTO payment_methods(name,code,icon,account_number,instructions,min_deposit,active,sort_order,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                methods
            )

        admin_count = cur.execute("SELECT COUNT(*) c FROM admins").fetchone()["c"]
        if admin_count == 0:
            cur.execute(
                "INSERT INTO admins(username,password_hash) VALUES(?,?)",
                (DEFAULT_ADMIN_USER, generate_password_hash(DEFAULT_ADMIN_PASS))
            )

        con.commit()
        con.close()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_setting(key, default=""):
    row = db_execute("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return row["value"] if row else default


def set_setting(key, value):
    db_execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value))
    )


def fsetting(key, default=0.0):
    try:
        return float(get_setting(key, default))
    except Exception:
        return float(default)


def admin_log(action):
    username = session.get("admin_user", "unknown")
    db_execute(
        "INSERT INTO admin_logs(admin_username,action,created_at) VALUES(?,?,?)",
        (username, action, now_str())
    )




def normalize_custom_emoji_id(value):
    value = (value or "").strip()
    if not value:
        return ""
    # Telegram custom emoji IDs are numeric strings.
    if not re.fullmatch(r"\d{5,30}", value):
        raise ValueError("Custom Emoji ID must contain digits only.")
    return value


def get_button_emoji(button_key):
    if not button_key:
        return ""
    row = db_execute(
        "SELECT emoji_id FROM button_emojis WHERE button_key=?",
        (button_key,),
        fetchone=True
    )
    return (row["emoji_id"] or "").strip() if row else ""


def get_message_emoji(emoji_key):
    if not emoji_key:
        return ""
    row = db_execute(
        "SELECT emoji_id,fallback FROM message_emojis WHERE emoji_key=?",
        (emoji_key,),
        fetchone=True
    )
    if not row:
        return ""
    emoji_id = (row["emoji_id"] or "").strip()
    fallback = (row["fallback"] or "⭐").strip() or "⭐"
    if not emoji_id:
        return ""
    return f'<tg-emoji emoji-id="{emoji_id}">{html.escape(fallback)}</tg-emoji>'


def msg_icon(emoji_key, text, bold=False):
    icon = get_message_emoji(emoji_key)
    if bold:
        text = f"<b>{text}</b>"
    return f"{icon} {text}".strip()


def save_message_emoji(emoji_key, label, emoji_id, fallback="⭐"):
    emoji_id = normalize_custom_emoji_id(emoji_id)
    fallback = (fallback or "⭐").strip() or "⭐"
    db_execute(
        """INSERT INTO message_emojis(emoji_key,label,emoji_id,fallback,updated_at)
           VALUES(?,?,?,?,?)
           ON CONFLICT(emoji_key) DO UPDATE SET
             label=excluded.label,
             emoji_id=excluded.emoji_id,
             fallback=excluded.fallback,
             updated_at=excluded.updated_at""",
        (emoji_key, label, emoji_id, fallback, now_str())
    )


def message_emoji_rows():
    rows = []
    for key, label in MESSAGE_EMOJI_DEFINITIONS.items():
        row = db_execute(
            "SELECT emoji_id,fallback FROM message_emojis WHERE emoji_key=?",
            (key,),
            fetchone=True
        )
        rows.append((
            key,
            label,
            (row["emoji_id"] if row else "") or "",
            (row["fallback"] if row else "⭐") or "⭐",
        ))
    return rows


def get_message_template(template_key):
    row = db_execute(
        "SELECT body FROM message_templates WHERE template_key=?",
        (template_key,),
        fetchone=True
    )
    if row:
        return row["body"]
    info = MESSAGE_TEMPLATE_DEFINITIONS.get(template_key)
    return info["body"] if info else ""


def save_message_template(template_key, label, body):
    db_execute(
        """INSERT INTO message_templates(template_key,label,body,updated_at)
           VALUES(?,?,?,?)
           ON CONFLICT(template_key) DO UPDATE SET
             label=excluded.label,
             body=excluded.body,
             updated_at=excluded.updated_at""",
        (template_key, label, body, now_str())
    )


def render_message_template(template_key, **values):
    """
    Render an editable message template.

    Supported custom emoji placeholders:
      [[emoji_key:success]]
        Uses the Custom Emoji ID saved in Admin -> Message Emojis.

      [[emoji:5368324170671202286|⭐]]
        Uses a Custom Emoji ID directly in the message.
        The part after | is the optional fallback emoji.

    You can place unlimited emoji placeholders anywhere in one message.
    Normal template variables such as {order_id} are also supported.
    """
    template = get_message_template(template_key)

    # Escape dynamic values so user/admin data cannot break Telegram HTML.
    safe_values = {}
    for key, value in values.items():
        if value is None:
            value = ""
        safe_values[key] = html.escape(str(value))

    class SafeTemplateDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    text = template.format_map(SafeTemplateDict(safe_values))

    def replace_named(match):
        key = match.group(1).strip()
        return get_message_emoji(key)

    def replace_direct(match):
        emoji_id = match.group(1).strip()
        fallback = (match.group(2) or "⭐").strip() or "⭐"
        try:
            emoji_id = normalize_custom_emoji_id(emoji_id)
        except ValueError:
            return ""
        if not emoji_id:
            return ""
        return f'<tg-emoji emoji-id="{emoji_id}">{html.escape(fallback)}</tg-emoji>'

    # Named emoji slots.
    text = re.sub(r"\[\[emoji_key:([a-zA-Z0-9_:\-]+)\]\]", replace_named, text)

    # Direct emoji IDs. Example: [[emoji:5368324170671202286|🔥]]
    text = re.sub(r"\[\[emoji:(\d{5,30})(?:\|([^\]]{1,8}))?\]\]", replace_direct, text)

    return text


def message_template_rows():
    rows = []
    for key, info in MESSAGE_TEMPLATE_DEFINITIONS.items():
        row = db_execute(
            "SELECT label,body,updated_at FROM message_templates WHERE template_key=?",
            (key,),
            fetchone=True
        )
        rows.append({
            "key": key,
            "label": row["label"] if row else info["label"],
            "body": row["body"] if row else info["body"],
            "updated_at": row["updated_at"] if row else "",
        })
    return rows


def save_button_emoji(button_key, label, emoji_id):
    emoji_id = normalize_custom_emoji_id(emoji_id)
    db_execute(
        """INSERT INTO button_emojis(button_key,label,emoji_id,updated_at)
           VALUES(?,?,?,?)
           ON CONFLICT(button_key) DO UPDATE SET
             label=excluded.label,
             emoji_id=excluded.emoji_id,
             updated_at=excluded.updated_at""",
        (button_key, label, emoji_id, now_str())
    )


def category_emoji_key(category):
    mapping = {
        "Mail": "product_item_mail",
        "VPN": "product_item_vpn",
        "Proxy": "product_item_proxy",
        "Premium Apk": "product_item_premium_apk",
    }
    return mapping.get(category, "")


def dynamic_button_emoji_rows():
    """Return static + dynamic payment method emoji slots for Admin Panel."""
    rows = []
    for key, label in BUTTON_EMOJI_DEFINITIONS.items():
        rows.append((key, label, get_button_emoji(key), "Bot Button"))

    for pm in get_payment_methods(active_only=False):
        key = f"payment_method:{pm['code']}"
        label = f"Payment: {pm['name']}"
        rows.append((key, label, get_button_emoji(key), "Payment Method"))

    products = db_execute(
        "SELECT id,name,category FROM products ORDER BY category,id",
        fetchall=True
    )
    for product in products:
        key = f"product:{product['id']}"
        label = f"Product: {product['name']} ({product['category']})"
        rows.append((key, label, get_button_emoji(key), "Product Button"))

    return rows


def get_payment_methods(active_only=False):
    sql = "SELECT * FROM payment_methods"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY sort_order ASC, id ASC"
    return db_execute(sql, fetchall=True)


def get_payment_method(code):
    return db_execute("SELECT * FROM payment_methods WHERE code=?", (code,), fetchone=True)


def payment_methods_markup():
    methods = get_payment_methods(active_only=True)
    rows, row = [], []
    for m in methods:
        style = "success" if m["code"] == "binance" else "primary"
        btn = ikb(
            m["name"],
            f'dep_method:{m["code"]}',
            style=style,
            emoji_key=f'payment_method:{m["code"]}'
        )
        if m["code"] in ("bkash", "nagad"):
            row.append(btn)
            if len(row) == 2:
                rows.append(row)
                row = []
        else:
            if row:
                rows.append(row)
                row = []
            rows.append([btn])
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)




# =========================================================
# PRODUCT AUTO-STOCK
# =========================================================

def product_available_stock(product_id):
    row = db_execute(
        "SELECT COUNT(*) c FROM product_stock_items WHERE product_id=? AND status='available'",
        (product_id,),
        fetchone=True
    )
    return int(row["c"] if row else 0)


def sync_product_stock(product_id):
    count = product_available_stock(product_id)
    db_execute("UPDATE products SET stock=? WHERE id=?", (count, product_id))
    return count


def parse_stock_lines(raw_text):
    items = []
    seen = set()
    for line in (raw_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        value = line.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items


def add_product_stock(product_id, raw_text):
    items = parse_stock_lines(raw_text)
    added = 0
    skipped = 0

    with DB_LOCK:
        con = db_connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            for item in items:
                exists = con.execute(
                    "SELECT id FROM product_stock_items WHERE product_id=? AND content=? LIMIT 1",
                    (product_id, item)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

                con.execute(
                    """INSERT INTO product_stock_items
                       (product_id,content,status,created_at)
                       VALUES(?,?,'available',?)""",
                    (product_id, item, now_str())
                )
                added += 1

            count = con.execute(
                "SELECT COUNT(*) c FROM product_stock_items WHERE product_id=? AND status='available'",
                (product_id,)
            ).fetchone()["c"]
            con.execute("UPDATE products SET stock=? WHERE id=?", (count, product_id))
            con.commit()
        finally:
            con.close()

    return added, skipped


def split_delivery_items(items, max_chars=3200):
    """Split plain-text stock into Telegram-safe chunks."""
    chunks = []
    current = ""
    for i, item in enumerate(items, 1):
        line = f"{i}. {item}"
        if len(line) > max_chars:
            # Keep very long single items safe too.
            if current:
                chunks.append(current)
                current = ""
            for pos in range(0, len(line), max_chars):
                chunks.append(line[pos:pos + max_chars])
            continue

        candidate = line if not current else current + "\n" + line
        if len(candidate) > max_chars:
            chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


# =========================================================
# LANGUAGE / LOCALIZATION
# =========================================================

UI_TEXT = {
    "en": {
        "buy_products": "Buy Products",
        "my_profile": "My Profile",
        "deposit": "Deposit",
        "get_code": "Get Code",
        "support": "Support",
        "usdt_sell": "USDT Sell",
        "language": "Language",
        "choose_language": "Choose your language:",
        "language_changed": "Language changed to English.",
        "select_category": "Select a category:",
        "select_link": "Select a link:",
        "select_payment": "Select payment method:",
        "name": "Name",
        "balance": "Balance",
        "joined": "Joined",
        "my_balance": "My Balance",
        "rate": "Rate",
        "referral_program": "Referral Program",
        "your_link": "Your Link",
        "referred_users": "Referred Users",
        "how_it_works": "How it works:",
        "referral_rule_1": "You earn {rp:.1f}% when your referral makes their first deposit",
        "referral_rule_2": "First depositors also get {bp:.1f}% bonus",
        "support_text": "Write your problem or question. Admin will reply soon.",
        "support_hint": "Tap the button below to message Admin:",
        "message_admin": "Message Admin",
        "cancel": "Cancel",
        "back": "Back",
        "menu_hint": "Choose an option from the menu below 👇",
        "usdt_sell_text": "If you want to sell USDT, send a message to Admin.",
        "no_bargain": "Please do not bargain about the price in inbox.",
        "service_unavailable": "USDT Sell service is currently unavailable.",
        "deposit_amount": "Enter deposit amount in BDT:",
        "minimum": "Minimum",
        "vpn_duration": "VPN — Select Duration:",
        "proxy_plan": "Proxy — Select Plan:",
        "mail_category": "Mail — Select Category:",
        "premium_apk": "Premium Apk — Select Product:",
    },
    "bn": {
        "buy_products": "পণ্য কিনুন",
        "my_profile": "আমার প্রোফাইল",
        "deposit": "ডিপোজিট",
        "get_code": "কোড নিন",
        "support": "সাপোর্ট",
        "usdt_sell": "USDT Sell",
        "language": "ভাষা",
        "choose_language": "আপনার ভাষা নির্বাচন করুন:",
        "language_changed": "ভাষা বাংলা করা হয়েছে।",
        "select_category": "একটি ক্যাটাগরি নির্বাচন করুন:",
        "select_link": "একটি লিংক নির্বাচন করুন:",
        "select_payment": "পেমেন্ট মেথড নির্বাচন করুন:",
        "name": "নাম",
        "balance": "ব্যালেন্স",
        "joined": "যোগদান",
        "my_balance": "আমার ব্যালেন্স",
        "rate": "রেট",
        "referral_program": "রেফারেল প্রোগ্রাম",
        "your_link": "আপনার লিংক",
        "referred_users": "রেফার করা ইউজার",
        "how_it_works": "যেভাবে কাজ করে:",
        "referral_rule_1": "রেফার করা ইউজারের প্রথম ডিপোজিটে আপনি {rp:.1f}% পাবেন",
        "referral_rule_2": "প্রথমবার ডিপোজিটকারীও {bp:.1f}% বোনাস পাবে",
        "support_text": "আপনার সমস্যা বা প্রশ্ন লিখুন, Admin শীঘ্রই reply করবে।",
        "support_hint": "নিচের বাটনে ট্যাপ করে message শুরু করুন:",
        "message_admin": "Admin-কে Message",
        "cancel": "বাতিল",
        "back": "ফিরে যান",
        "menu_hint": "নিচের মেনু থেকে বেছে নিন 👇",
        "usdt_sell_text": "ডলার Sell করতে চাইলে Admin-কে SMS দিন।",
        "no_bargain": "Price নিয়ে inbox-এ দামাদামি করবেন না।",
        "service_unavailable": "USDT Sell service বর্তমানে বন্ধ আছে।",
        "deposit_amount": "ডিপোজিট amount BDT-তে লিখুন:",
        "minimum": "সর্বনিম্ন",
        "vpn_duration": "VPN — মেয়াদ নির্বাচন করুন:",
        "proxy_plan": "Proxy — প্ল্যান নির্বাচন করুন:",
        "mail_category": "Mail — ক্যাটাগরি নির্বাচন করুন:",
        "premium_apk": "Premium Apk — প্রোডাক্ট নির্বাচন করুন:",
    },
}


def normalize_language(value):
    return "en" if str(value).lower() == "en" else "bn"


def get_user_language(uid):
    row = db_execute("SELECT language FROM users WHERE telegram_id=?", (uid,), fetchone=True)
    if not row:
        return "bn"
    return normalize_language(row["language"])


def set_user_language(uid, language):
    language = normalize_language(language)
    db_execute("UPDATE users SET language=? WHERE telegram_id=?", (language, uid))
    return language


def t(lang, key, **kwargs):
    lang = normalize_language(lang)
    value = UI_TEXT.get(lang, UI_TEXT["bn"]).get(key, UI_TEXT["en"].get(key, key))
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value


def main_menu_values(lang):
    return {
        "buy": t(lang, "buy_products"),
        "profile": t(lang, "my_profile"),
        "deposit": t(lang, "deposit"),
        "code": t(lang, "get_code"),
        "support": t(lang, "support"),
        "usdt_sell": t(lang, "usdt_sell"),
        "language": t(lang, "language"),
    }


def matches_main_button(text, key):
    for lang in ("bn", "en"):
        if text == main_menu_values(lang)[key]:
            return True
    return False



# =========================================================
# FORCE JOIN
# =========================================================

def get_force_join_channels(active_only=True):
    sql = "SELECT * FROM force_join_channels"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY sort_order ASC, id ASC"
    return db_execute(sql, fetchall=True)


def derive_check_chat(join_url):
    value = (join_url or "").strip()
    m = re.match(
        r"^https?://(?:t\.me|telegram\.me)/([A-Za-z0-9_]{5,32})/?(?:\?.*)?$",
        value,
        re.I,
    )
    if not m:
        return ""
    username = m.group(1)
    if username.lower() in {"joinchat", "share", "addstickers", "proxy", "socks"}:
        return ""
    return "@" + username


def force_join_prompt_text(lang):
    if normalize_language(lang) == "en":
        return (
            "🔒 <b>Join Required</b>\n\n"
            "To use this bot, please join all required channels/groups below.\n\n"
            "After joining, tap <b>✅ I've Joined</b>."
        )
    return (
        "🔒 <b>Join Required</b>\n\n"
        "Bot ব্যবহার করতে নিচের প্রয়োজনীয় Channel/Group-গুলোতে Join করুন।\n\n"
        "Join করার পর <b>✅ I've Joined</b> বাটনে চাপুন।"
    )


async def get_missing_force_join_channels(bot, user_id):
    missing = []
    for row in get_force_join_channels(active_only=True):
        check_chat = (row["check_chat"] or "").strip()
        if not check_chat:
            missing.append(row)
            continue
        try:
            member = await bot.get_chat_member(chat_id=check_chat, user_id=user_id)
            status = str(member.status).lower()
            joined = status in {"member", "administrator", "creator", "owner"}
            if status == "restricted":
                joined = bool(getattr(member, "is_member", False))
            if not joined:
                missing.append(row)
        except Exception:
            missing.append(row)
    return missing


async def send_force_join_prompt(update, context, missing_channels=None):
    uid = update.effective_user.id
    lang = get_user_language(uid)
    if missing_channels is None:
        missing_channels = await get_missing_force_join_channels(context.bot, uid)

    rows = []
    for item in missing_channels:
        rows.append([ikb(item["button_name"], url=item["join_url"], style="primary")])
    rows.append([ikb("✅ I've Joined", "force_join_check", style="success")])

    await update.effective_message.reply_text(
        force_join_prompt_text(lang),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def ensure_force_join(update, context):
    if not get_force_join_channels(active_only=True):
        return True
    missing = await get_missing_force_join_channels(context.bot, update.effective_user.id)
    if not missing:
        return True
    await send_force_join_prompt(update, context, missing)
    return False


async def force_join_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = update.effective_user.id
    lang = get_user_language(uid)
    missing = await get_missing_force_join_channels(context.bot, uid)

    if missing:
        rows = []
        for item in missing:
            rows.append([ikb(item["button_name"], url=item["join_url"], style="primary")])
        rows.append([ikb("✅ I've Joined", "force_join_check", style="success")])

        text = (
            "❌ <b>Still Not Joined</b>\n\nPlease join all required channels/groups first."
            if lang == "en"
            else
            "❌ <b>এখনও সবগুলোতে Join করা হয়নি</b>\n\nআগে প্রয়োজনীয় সব Channel/Group-এ Join করুন।"
        )
        await q.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    await q.edit_message_text(
        "✅ <b>Verified!</b>\n\nYou can now use the bot."
        if lang == "en"
        else
        "✅ <b>Verified!</b>\n\nএখন আপনি Bot ব্যবহার করতে পারবেন।",
        parse_mode=ParseMode.HTML,
    )
    await q.message.reply_text(
        t(lang, "menu_hint"),
        reply_markup=main_reply_keyboard(lang),
    )


# =========================================================
# TELEGRAM BUTTON HELPERS
# =========================================================

def ikb(text, callback_data=None, url=None, style="primary", emoji_key=None):
    kwargs = {"text": text, "style": style}
    emoji_id = get_button_emoji(emoji_key) if emoji_key else ""
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    return InlineKeyboardButton(**kwargs)


def rkb(text, style="primary", emoji_key=None):
    kwargs = {"text": text, "style": style}
    emoji_id = get_button_emoji(emoji_key) if emoji_key else ""
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    return KeyboardButton(**kwargs)


def main_reply_keyboard(lang="bn"):
    labels = main_menu_values(lang)
    return ReplyKeyboardMarkup(
        [
            [rkb(labels["buy"], style="success", emoji_key="main_buy_products")],
            [
                rkb(labels["profile"], style="primary", emoji_key="main_profile"),
                rkb(labels["deposit"], style="primary", emoji_key="main_deposit"),
            ],
            [
                rkb(labels["code"], style="primary", emoji_key="main_get_code"),
                rkb(labels["support"], style="primary", emoji_key="main_support"),
            ],
            [
                rkb(labels["usdt_sell"], style="success", emoji_key="main_usdt_sell"),
                rkb(labels["language"], style="primary", emoji_key="main_language"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def back_markup(callback_data):
    return InlineKeyboardMarkup([[
        ikb("Back", callback_data=callback_data, style="danger", emoji_key="back")
    ]])


# =========================================================
# USER / REFERRAL
# =========================================================

def ensure_user(tg_user, referrer_id=None):
    uid = tg_user.id
    row = db_execute("SELECT * FROM users WHERE telegram_id=?", (uid,), fetchone=True)

    if row:
        db_execute(
            "UPDATE users SET username=?, full_name=? WHERE telegram_id=?",
            (tg_user.username or "", tg_user.full_name or "User", uid)
        )
        return

    valid_ref = None
    if referrer_id and referrer_id != uid:
        ref = db_execute("SELECT telegram_id FROM users WHERE telegram_id=?", (referrer_id,), fetchone=True)
        if ref:
            valid_ref = referrer_id

    db_execute(
        """INSERT INTO users
        (telegram_id,username,full_name,joined_at,referred_by)
        VALUES(?,?,?,?,?)""",
        (uid, tg_user.username or "", tg_user.full_name or "User",
         datetime.now().strftime("%Y-%m-%d"), valid_ref)
    )

    if valid_ref:
        db_execute(
            "UPDATE users SET referral_count=referral_count+1 WHERE telegram_id=?",
            (valid_ref,)
        )


def get_user(uid):
    return db_execute("SELECT * FROM users WHERE telegram_id=?", (uid,), fetchone=True)


def is_banned(uid):
    row = get_user(uid)
    return bool(row and row["banned"])


# =========================================================
# TELEGRAM SCREENS
# =========================================================

async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    lang = get_user_language(update.effective_user.id)
    rate = fsetting("usdt_rate", 125.0)
    usdt = user["bdt_balance"] / rate if rate > 0 else 0
    text = (
        f"{msg_icon('welcome', 'Will be Earn Shop', bold=True)}\n\n"
        f"{msg_icon('balance', t(lang, 'balance') + ':')} "
        f"<b>{user['bdt_balance']:.2f} BDT</b> / <b>{usdt:.4f} USDT</b>\n\n"
        f"{msg_icon('menu_hint', t(lang, 'menu_hint'))}"
    )
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=main_reply_keyboard(lang)
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    referrer = None
    if context.args:
        m = re.fullmatch(r"ref_(\d+)", context.args[0])
        if m:
            referrer = int(m.group(1))
    ensure_user(update.effective_user, referrer)
    if not await ensure_force_join(update, context):
        return
    await send_start(update, context)


async def show_product_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [
            ikb("VPN", "cat:VPN", style="primary", emoji_key="category_vpn"),
            ikb("Proxy", "cat:Proxy", style="primary", emoji_key="category_proxy"),
        ],
        [
            ikb("Mail", "cat:Mail", style="primary", emoji_key="category_mail"),
            ikb("Premium Apk", "cat:Premium Apk", style="success", emoji_key="category_premium_apk"),
        ],
    ])
    await update.effective_message.reply_text(
        f"{msg_icon('buy_products', t(lang, 'buy_products'), bold=True)}\n\n"
        f"{t(lang, 'select_category')}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    category = q.data.split(":", 1)[1]
    lang = get_user_language(update.effective_user.id)

    products = db_execute(
        "SELECT * FROM products WHERE active=1 AND category=? ORDER BY id ASC",
        (category,), fetchall=True
    )

    rows = []
    for p in products:
        if p["delivery_mode"] == "auto":
            availability = (
                f"{p['stock']} ready"
                if int(p["stock"]) > 0
                else "Wait delivery"
            )
        else:
            availability = "Manual delivery"

        rows.append([
            ikb(
                f"{p['name']} · {p['price_bdt']:.2f} BDT · {availability}",
                f"prod:{p['id']}",
                style="primary",
                emoji_key=f"product:{p['id']}"
            )
        ])
    rows.append([ikb("Back", "product_categories", style="danger", emoji_key="back")])

    if category == "VPN":
        title = f"{msg_icon('vpn', t(lang, 'vpn_duration'))}"
    elif category == "Proxy":
        title = f"{msg_icon('proxy', t(lang, 'proxy_plan'), bold=True)}"
    elif category == "Mail":
        title = f"{msg_icon('mail', t(lang, 'mail_category'), bold=True)}"
    elif category == "Premium Apk":
        title = f"{msg_icon('premium_apk', t(lang, 'premium_apk'), bold=True)}"
    else:
        title = f"{html.escape(category)} — Select Product:"

    await q.edit_message_text(
        title,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def product_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    lang = get_user_language(update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [
            ikb("VPN", "cat:VPN", style="primary", emoji_key="category_vpn"),
            ikb("Proxy", "cat:Proxy", style="primary", emoji_key="category_proxy"),
        ],
        [
            ikb("Mail", "cat:Mail", style="primary", emoji_key="category_mail"),
            ikb("Premium Apk", "cat:Premium Apk", style="success", emoji_key="category_premium_apk"),
        ],
    ])
    await q.edit_message_text(
        f"{msg_icon('buy_products', t(lang, 'buy_products'), bold=True)}\n\n"
        f"{t(lang, 'select_category')}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    pid = int(q.data.split(":")[1])
    p = db_execute("SELECT * FROM products WHERE id=? AND active=1", (pid,), fetchone=True)
    if not p:
        await q.edit_message_text("❌ Product unavailable.")
        return

    context.user_data.clear()
    context.user_data.update({
        "state": "await_quantity",
        "product_id": pid,
        "category": p["category"],
    })

    detail_icons = {
        "Mail": "📧",
        "VPN": "🛡️",
        "Proxy": "🌐",
        "Premium Apk": "📱",
    }
    detail_icon = detail_icons.get(p["category"], "🛍️")
    if p["delivery_mode"] == "auto" and int(p["stock"]) > 0:
        delivery_line = f"⚡ Ready Stock: {p['stock']} — Instant delivery available"
    elif p["delivery_mode"] == "auto":
        delivery_line = "⏳ Ready Stock: 0 — Order করলে wait করতে হবে"
    else:
        delivery_line = "⏳ Delivery: Admin/manual delivery"

    text = (
        f"{detail_icon} <b>{html.escape(p['name'])}</b>\n"
        f"💰 {p['price_bdt']:.2f} BDT / piece\n"
        f"{delivery_line}\n\n"
        "Enter quantity:"
    )
    await q.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [ikb("Cancel", f"cat:{p['category']}", style="danger", emoji_key="cancel")]
        ])
    )


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    u = get_user(update.effective_user.id)
    lang = get_user_language(update.effective_user.id)
    rate = fsetting("usdt_rate", 125.0)
    usdt = u["bdt_balance"] / rate if rate > 0 else 0
    text = (
        f"{msg_icon('profile', t(lang, 'my_profile'), bold=True)}\n\n"
        f"{msg_icon('profile_name', t(lang, 'name') + '       :')} <b>{html.escape(u['full_name'])}</b>\n"
        f"{msg_icon('balance', t(lang, 'balance') + '   :')} "
        f"<b>{u['bdt_balance']:.2f} BDT</b> / <b>{usdt:.4f} USDT</b>\n"
        f"{msg_icon('profile_joined', t(lang, 'joined') + '     :')} {u['joined_at']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [
            ikb("Balance Details", "profile_balance", style="primary", emoji_key="profile_balance"),
            ikb("Deposit History", "profile_deposits", style="primary", emoji_key="profile_deposits"),
        ],
        [
            ikb("Referral", "profile_referral", style="primary", emoji_key="profile_referral"),
            ikb("Purchases", "profile_purchases", style="primary", emoji_key="profile_purchases"),
        ],
    ])
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    action = q.data
    u = get_user(update.effective_user.id)
    lang = get_user_language(update.effective_user.id)

    if action == "profile_home":
        await show_profile(update, context, edit=True)
        return

    if action == "profile_balance":
        rate = fsetting("usdt_rate", 125.0)
        usdt = u["bdt_balance"] / rate if rate > 0 else 0
        text = (
            f"{msg_icon('balance', t(lang, 'my_balance'), bold=True)}\n\n"
            f"{msg_icon('bdt_balance', 'BDT    :')} <b>{u['bdt_balance']:.2f} ৳</b>\n"
            f"{msg_icon('usdt_balance', 'USDT  :')} <b>{usdt:.6f} $</b>\n\n"
            f"{t(lang, 'rate')}   : 1 USDT = {rate:.1f} BDT\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_markup("profile_home"))
        return

    if action == "profile_deposits":
        rows = db_execute(
            "SELECT * FROM deposits WHERE telegram_id=? ORDER BY id DESC LIMIT 10",
            (u["telegram_id"],), fetchall=True
        )
        if not rows:
            text = f"{msg_icon('history', 'No deposit history.')}"
        else:
            chunks = ["📜 <b>Deposit History</b>\n"]
            for d in rows:
                icon = {"approved": "✅", "rejected": "❌", "pending": "🕘"}.get(d["status"], "•")
                chunks.append(
                    f"{icon} #{d['id']} · {d['method']} · {d['amount_bdt']:.2f} BDT\n"
                    f"Status: {d['status'].title()} · {d['created_at']}"
                )
            text = "\n\n".join(chunks)
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_markup("profile_home"))
        return

    if action == "profile_referral":
        bot_username = get_setting("bot_username", "will_be_eran_shop_bot").lstrip("@")
        rp = fsetting("referral_percent", 25)
        bp = fsetting("first_deposit_bonus_percent", 10)
        link = f"https://t.me/{bot_username}?start=ref_{u['telegram_id']}"
        text = (
            f"{msg_icon('referral', t(lang, 'referral_program'), bold=True)}\n\n"
            f"{t(lang, 'your_link')}:\n<code>{html.escape(link)}</code>\n\n"
            f"{t(lang, 'referred_users')}: <b>{u['referral_count']}</b>\n\n"
            f"{msg_icon('how_it_works', t(lang, 'how_it_works'), bold=True)}\n"
            f"• {t(lang, 'referral_rule_1', rp=rp)}\n"
            f"• {t(lang, 'referral_rule_2', bp=bp)}"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_markup("profile_home"))
        return

    if action == "profile_purchases":
        rows = db_execute(
            "SELECT * FROM orders WHERE telegram_id=? ORDER BY id DESC LIMIT 10",
            (u["telegram_id"],), fetchall=True
        )
        if not rows:
            text = f"{msg_icon('purchases', 'No purchases yet.')}"
        else:
            out = ["🛍️ <b>Purchases</b>\n"]
            for o in rows:
                status_icon = "✅" if o["status"] in ("delivered", "completed") else ("❌" if o["status"] == "rejected" else "⏳")
                out.append(
                    f"{status_icon} #{o['id']} · {html.escape(o['product_name'])}\n"
                    f"Qty: {o['quantity']} · Total: {o['total_bdt']:.2f} BDT\n"
                    f"Status: {html.escape(o['status'].title())} · {o['created_at']}"
                )
            text = "\n\n".join(out)
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_markup("profile_home"))


async def show_deposit_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(update.effective_user.id)
    methods = get_payment_methods(active_only=True)
    if not methods:
        await update.effective_message.reply_text("⚠️ No deposit method is available right now.")
        return
    await update.effective_message.reply_text(
        f"{msg_icon('deposit', t(lang, 'deposit'), bold=True)}\n\n"
        f"{t(lang, 'select_payment')}",
        parse_mode=ParseMode.HTML,
        reply_markup=payment_methods_markup(),
    )


async def deposit_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    method_code = q.data.split(":", 1)[1]
    lang = get_user_language(update.effective_user.id)
    method = get_payment_method(method_code)
    context.user_data.clear()

    if not method or not method["active"]:
        await q.edit_message_text("⚠️ This payment method is currently unavailable.")
        return

    if method_code == "voucher":
        context.user_data.update({
            "state": "await_voucher_code",
            "method": method_code
        })
        await q.edit_message_text(
            f"{msg_icon('cash_voucher', 'Cash Voucher', bold=True)}\n\n"
            "Enter your voucher code:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                ikb("Back", "deposit_methods", style="danger", emoji_key="back")
            ]])
        )
        return

    if method_code == "binance":
        context.user_data.update({
            "state": "await_binance_currency",
            "method": method_code
        })
        await q.edit_message_text(
            f"{msg_icon('binance', 'Binance Deposit', bold=True)}\n\n"
            "Select currency:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    ikb("BDT", "binance_currency:bdt", style="primary"),
                    ikb("USDT", "binance_currency:usdt", style="success"),
                ],
                [ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")]
            ])
        )
        return

    context.user_data.update({
        "state": "await_deposit_amount",
        "method": method_code
    })
    min_dep = float(method["min_deposit"] or 0)

    method_emoji_key = {
        "bkash": "bkash",
        "nagad": "nagad",
        "rocket": "rocket",
    }.get(method_code, "deposit")

    await q.edit_message_text(
        f"{msg_icon(method_emoji_key, html.escape(method['name']), bold=True)}\n\n"
        f"{t(lang, 'deposit_amount')}\n"
        f"({t(lang, 'minimum')}: {min_dep:.1f} BDT)",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")
        ]])
    )


async def deposit_methods_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    lang = get_user_language(update.effective_user.id)
    context.user_data.clear()
    methods = get_payment_methods(active_only=True)
    if not methods:
        await q.edit_message_text("⚠️ No deposit method is available right now.")
        return
    await q.edit_message_text(
        f"{msg_icon('deposit', t(lang, 'deposit'), bold=True)}\n\n"
        f"{t(lang, 'select_payment')}",
        parse_mode=ParseMode.HTML,
        reply_markup=payment_methods_markup(),
    )


async def binance_currency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return

    currency = q.data.split(":", 1)[1].lower()
    method = get_payment_method("binance")
    if not method or not method["active"]:
        context.user_data.clear()
        await q.edit_message_text("This payment method is currently unavailable.")
        return

    context.user_data.update({
        "method": "binance",
        "binance_currency": currency,
    })

    min_dep = float(method["min_deposit"] or 0)
    rate = fsetting("usdt_rate", 125.0)

    if currency == "usdt":
        min_usdt = (min_dep / rate) if rate > 0 else 0
        context.user_data["state"] = "await_binance_usdt_amount"
        await q.edit_message_text(
            f"{msg_icon('binance', 'Binance Deposit', bold=True)}\n\n"
            f"Enter deposit amount in USDT:\n"
            f"(Minimum: {min_usdt:.4f} USDT)",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")
            ]])
        )
    else:
        context.user_data["state"] = "await_deposit_amount"
        await q.edit_message_text(
            f"{msg_icon('binance', 'Binance Deposit', bold=True)}\n\n"
            f"Enter deposit amount in BDT:\n"
            f"(Minimum: {min_dep:.1f} BDT)",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")
            ]])
        )


async def paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    method = context.user_data.get("method")
    amount = context.user_data.get("amount")
    if not method or not amount:
        await q.edit_message_text("❌ Deposit session expired. Start again.")
        return

    context.user_data["state"] = "await_trxid"

    if method == "binance":
        trx_hint = (
            "Paste the full BEP20/BSC transaction hash.\n"
            "Example format: <code>0x</code> + 64 hexadecimal characters."
        )
    else:
        trx_hint = (
            "Send the TrxID from your payment SMS\n"
            "(e.g. <i>DF27TNVV17</i>)"
        )

    await q.edit_message_text(
        "🔖 <b>Enter Transaction ID</b>\n\n"
        f"Amount: {amount:.2f} BDT via {html.escape(method)}\n\n"
        f"{trx_hint}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")]])
    )


async def screenshot_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    context.user_data["state"] = "await_payment_screenshot"
    await q.edit_message_text(
        f"{msg_icon('payment_screenshot', 'Payment Screenshot পাঠান', bold=True)}\n\n"
        "Payment এর screenshot পাঠান — Admin শীঘ্রই verify করবে।\n\n"
        "<i>TrxID না দিলে manual verification হবে।</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")]])
    )


async def show_get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [
            ikb(
                "Hotmail/Outlook",
                url=get_setting("hot_mail_url", HOTMAIL_URL_DEFAULT),
                style="primary",
                emoji_key="code_hotmail"
            )
        ],
        [
            ikb(
                "Fr Outlook Code",
                url=get_setting("fr_outlook_url", FR_OUTLOOK_URL_DEFAULT),
                style="primary",
                emoji_key="code_fr_outlook"
            )
        ],
        [
            ikb(
                "API Gmail Code",
                url=get_setting("api_gmail_url", API_GMAIL_URL_DEFAULT),
                style="primary",
                emoji_key="code_api_gmail"
            )
        ],
    ])
    await update.effective_message.reply_text(
        f"{msg_icon('get_code', t(lang, 'get_code'), bold=True)}\n\n"
        f"{t(lang, 'select_link')}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(update.effective_user.id)
    username = get_setting("support_username", SUPPORT_USERNAME_DEFAULT).lstrip("@")
    kb = InlineKeyboardMarkup([
        [ikb(t(lang, "message_admin"), url=f"https://t.me/{username}", style="primary", emoji_key="support_message_admin")],
        [ikb(t(lang, "cancel"), "support_cancel", style="danger", emoji_key="cancel")],
    ])
    await update.effective_message.reply_text(
        f"{msg_icon('support', t(lang, 'support'), bold=True)}\n\n"
        f"{t(lang, 'support_text')}\n\n"
        f"<i>{t(lang, 'support_hint')}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


async def show_usdt_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(update.effective_user.id)
    enabled = get_setting("usdt_sell_enabled", "1").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        await update.effective_message.reply_text(
            t(lang, "service_unavailable"),
            reply_markup=main_reply_keyboard(lang)
        )
        return

    try:
        sell_rate = float(get_setting("usdt_sell_rate", "125"))
    except Exception:
        sell_rate = 125.0

    admin_username = get_setting(
        "usdt_sell_admin_username",
        "Ariyan_Ahamed_Ari"
    ).strip().lstrip("@")

    text = (
        f"{msg_icon('usdt_sell', t(lang, 'usdt_sell'), bold=True)}\n\n"
        f"{t(lang, 'usdt_sell_text')}\n\n"
        f"<b>Per Dollar: 1 USDT = {sell_rate:g} BDT</b>\n\n"
        f"{t(lang, 'no_bargain')}"
    )

    rows = []
    if admin_username:
        rows.append([
            ikb(
                f"@{admin_username}",
                url=f"https://t.me/{admin_username}",
                style="primary"
            )
        ])
    rows.append([
        ikb("Cancel", "usdt_sell_cancel", style="danger", emoji_key="cancel")
    ])

    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def usdt_sell_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    await q.edit_message_text("USDT Sell closed.")


async def show_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [
            ikb("বাংলা", "set_language:bn", style="success"),
            ikb("English", "set_language:en", style="primary"),
        ]
    ])
    await update.effective_message.reply_text(
        f"{msg_icon('language', t(lang, 'language'), bold=True)}\n\n"
        f"{t(lang, 'choose_language')}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return

    language = q.data.split(":", 1)[1]
    language = set_user_language(update.effective_user.id, language)
    context.user_data.clear()

    await q.edit_message_text(
        f"{msg_icon('language', t(language, 'language_changed'), bold=True)}",
        parse_mode=ParseMode.HTML
    )

    await q.message.reply_text(
        t(language, "menu_hint"),
        reply_markup=main_reply_keyboard(language)
    )


async def support_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return
    await q.edit_message_text("❌ Support closed.")


# =========================================================
# MESSAGE STATE HANDLER
# =========================================================

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    ensure_user(update.effective_user)
    uid = update.effective_user.id

    if is_banned(uid):
        await update.message.reply_text("🚫 Your account is restricted.")
        return

    if not await ensure_force_join(update, context):
        return

    text = (update.message.text or "").strip()

    # Persistent main keyboard (accepts both Bangla and English labels)
    lang = get_user_language(uid)

    if matches_main_button(text, "buy") or text == MAIN_BUY:
        context.user_data.clear()
        await show_product_categories(update, context)
        return
    if matches_main_button(text, "profile") or text == MAIN_PROFILE:
        context.user_data.clear()
        await show_profile(update, context)
        return
    if matches_main_button(text, "deposit") or text == MAIN_DEPOSIT:
        context.user_data.clear()
        await show_deposit_methods(update, context)
        return
    if matches_main_button(text, "code") or text == MAIN_CODE:
        context.user_data.clear()
        await show_get_code(update, context)
        return
    if matches_main_button(text, "support") or text == MAIN_SUPPORT:
        context.user_data.clear()
        await show_support(update, context)
        return
    if matches_main_button(text, "usdt_sell") or text == MAIN_USDT_SELL:
        context.user_data.clear()
        await show_usdt_sell(update, context)
        return
    if matches_main_button(text, "language") or text == MAIN_LANGUAGE:
        context.user_data.clear()
        await show_language(update, context)
        return

    state = context.user_data.get("state")

    # Quantity input
    if state == "await_quantity":
        if not re.fullmatch(r"\d+", text):
            await update.message.reply_text("❌ Enter a valid quantity.")
            return
        qty = int(text)
        pid = context.user_data.get("product_id")
        p = db_execute("SELECT * FROM products WHERE id=? AND active=1", (pid,), fetchone=True)
        if not p:
            context.user_data.clear()
            await update.message.reply_text("❌ Product unavailable.")
            return
        if qty < 1:
            await update.message.reply_text("❌ Quantity must be at least 1.")
            return
        user = get_user(uid)
        total = round(p["price_bdt"] * qty, 2)
        rate = fsetting("usdt_rate", 125.0)
        total_usdt = total / rate if rate > 0 else 0
        need = max(total - user["bdt_balance"], 0)

        context.user_data.update({
            "state": "await_order_confirm",
            "quantity": qty,
            "total": total,
        })

        if need > 0:
            status = f"⚠️ Need <b>{need:.2f} BDT</b> more."
        elif p["delivery_mode"] == "auto" and int(p["stock"]) >= qty:
            status = "✅ Sufficient balance. ⚡ Ready stock আছে — instant delivery হবে।"
        else:
            status = "✅ Sufficient balance. ⏳ Ready stock না থাকলে order pending থাকবে।"
        order_icons = {
            "Mail": "📧",
            "VPN": "🛡️",
            "Proxy": "🌐",
            "Premium Apk": "📱",
        }
        order_icon = order_icons.get(p["category"], "🛍️")
        msg = (
            f"{msg_icon('order_summary', 'Order Summary', bold=True)}\n\n"
            f"⚡ Product  : {html.escape(p['name'])}\n"
            f"💎 Quantity : {qty}\n"
            f"💰 Total    : {total:.2f} BDT / {total_usdt:.4f} USDT\n"
            f"👛 Balance  : {user['bdt_balance']:.2f} BDT\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{status}"
        )
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                ikb("Confirm Order", "order_confirm", style="success", emoji_key="confirm_order"),
                ikb("Cancel", f"cat:{p['category']}", style="danger", emoji_key="cancel"),
            ]])
        )
        return

    # Binance USDT amount
    if state == "await_binance_usdt_amount":
        try:
            usdt_amount = float(text)
        except Exception:
            await update.message.reply_text("Enter a valid USDT amount.")
            return

        pm = get_payment_method("binance")
        if not pm or not pm["active"]:
            context.user_data.clear()
            await update.message.reply_text("This payment method is currently unavailable.")
            return

        rate = fsetting("usdt_rate", 125.0)
        min_bdt = float(pm["min_deposit"] or 0)
        min_usdt = (min_bdt / rate) if rate > 0 else 0

        if usdt_amount < min_usdt:
            await update.message.reply_text(
                f"Minimum deposit is {min_usdt:.4f} USDT."
            )
            return

        amount_bdt = round(usdt_amount * rate, 2)
        context.user_data.update({
            "amount": amount_bdt,
            "usdt_amount": round(usdt_amount, 6),
            "state": "await_paid_click",
            "method": "binance",
        })

        target = (pm["account_number"] or "").strip()
        if not target:
            context.user_data.clear()
            await update.message.reply_text(
                "Binance payment details are not configured. Please contact support.",
                reply_markup=main_reply_keyboard(get_user_language(update.effective_user.id))
            )
            return

        await update.message.reply_text(
            f"{msg_icon('binance', 'Binance Deposit', bold=True)}\n\n"
            f"Send <b>{usdt_amount:.6f} USDT</b> to:\n"
            f"<code>{html.escape(target)}</code>\n\n"
            "After sending, tap <b>Paid</b> below:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [ikb("Paid", "deposit_paid", style="success", emoji_key="deposit_paid")],
                [ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")],
            ])
        )
        return

    # Cash Voucher code
    if state == "await_voucher_code":
        voucher_code = text.strip()
        if len(voucher_code) < 3:
            await update.message.reply_text("Enter a valid voucher code.")
            return

        # Voucher validation/credit can be expanded later from the Admin Panel.
        # For now keep the code in the user's session and direct them to support.
        context.user_data["voucher_code"] = voucher_code
        context.user_data["state"] = "idle"
        await update.message.reply_text(
            f"{msg_icon('cash_voucher', 'Cash Voucher', bold=True)}\n\n"
            f"Voucher Code: <code>{html.escape(voucher_code)}</code>\n\n"
            "Voucher submitted. Admin verification is required.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_reply_keyboard(get_user_language(update.effective_user.id))
        )
        return

    # Deposit amount
    if state == "await_deposit_amount":
        try:
            amount = float(text)
        except Exception:
            await update.message.reply_text("❌ Enter a valid amount.")
            return

        method_code = context.user_data["method"]
        pm = get_payment_method(method_code)
        if not pm or not pm["active"]:
            await update.message.reply_text("⚠️ This payment method is currently unavailable.")
            context.user_data.clear()
            return

        min_dep = float(pm["min_deposit"] or 0)
        if amount < min_dep:
            await update.message.reply_text(f"❌ Minimum deposit is {min_dep:.2f} BDT.")
            return

        amount = round(amount, 2)
        context.user_data.update({"amount": amount, "state": "await_paid_click"})
        method = method_code
        target = pm["account_number"].strip()
        title = pm["name"]

        if not target:
            await update.message.reply_text(
                f"⚠️ {title} payment details are not configured. Please contact support.",
                reply_markup=main_reply_keyboard(get_user_language(update.effective_user.id))
            )
            context.user_data.clear()
            return

        if method == "binance":
            rate = fsetting("usdt_rate", 125.0)
            usdt_amt = amount / rate if rate > 0 else 0
            body = (
                f"🟡 <b>{title}</b>\n\n"
                f"Send <b>{usdt_amt:.4f} USDT</b> ({amount:.2f} BDT) to:\n"
                f"<code>{html.escape(target)}</code>\n\n"
                "<i>Tap the address above to copy</i>\n\n"
                "After sending, tap <b>Paid</b> below:"
            )
        else:
            body = (
                f"💵 <b>{title}</b>\n\n"
                f"Send <b>{amount:.2f} BDT</b> to:\n"
                f"<code>{html.escape(target)}</code>\n\n"
                "<i>Tap the number above to copy</i>\n\n"
                "After sending, tap <b>Paid</b> below:"
            )

        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [ikb("Paid", "deposit_paid", style="success", emoji_key="deposit_paid")],
                [ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")],
            ])
        )
        return

    # Transaction ID
    if state == "await_trxid":
        method = (context.user_data.get("method") or "").lower()
        trx_raw = re.sub(r"\s+", "", text.strip())

        if method == "binance":
            # BEP20 / BSC hashes are normally 32-byte hashes:
            # 64 hex chars, usually displayed with a leading 0x (66 chars total).
            bep20_match = re.fullmatch(r"(?:0x)?([0-9a-fA-F]{64})", trx_raw)
            if bep20_match:
                trx = "0x" + bep20_match.group(1).lower()
            elif re.fullmatch(r"[A-Za-z0-9_-]{10,120}", trx_raw):
                # Also allow Binance internal TxIDs / compatible provider IDs.
                trx = trx_raw
            else:
                await update.message.reply_text(
                    "❌ Invalid BEP20/Binance Transaction ID.\n\n"
                    "BEP20 hash হলে পুরো 0x + 64 hexadecimal characters দিন।"
                )
                return
        else:
            if not re.fullmatch(r"[A-Za-z0-9_-]{5,120}", trx_raw):
                await update.message.reply_text("❌ Invalid TrxID format. Please try again.")
                return
            trx = trx_raw.upper()

        duplicate = db_execute(
            "SELECT id FROM deposits WHERE LOWER(trx_id)=LOWER(?)",
            (trx,),
            fetchone=True
        )
        if duplicate:
            await update.message.reply_text("❌ This TrxID has already been submitted.")
            return

        context.user_data.update({"trx_id": trx, "state": "trx_recorded"})

        amount = float(context.user_data["amount"])
        await update.message.reply_text(
            f"{msg_icon('deposit_pending', 'TrxID রেকর্ড করা হয়েছে।', bold=True)}\n\n"
            f"{msg_icon('transaction_id', 'TrxID:')} <code>{html.escape(trx)}</code>\n"
            f"{msg_icon('total', 'Amount:')} {amount:.0f} BDT\n\n"
            "Payment-এর SMS আসামাত্রই আপনার deposit স্বয়ংক্রিয়ভাবে confirm হয়ে যাবে — অপেক্ষা করুন।\n\n"
            "<i>চাইলে screenshot দিন:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [ikb("Screenshot দিন", "deposit_screenshot", style="primary", emoji_key="deposit_screenshot")],
                [ikb("Cancel", "deposit_methods", style="danger", emoji_key="cancel")],
            ])
        )
        return

    # Ignore random text but keep UI friendly
    if text:
        await update.message.reply_text(
            t(lang, "menu_hint"),
            reply_markup=main_reply_keyboard(lang)
        )


async def photo_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    ensure_user(update.effective_user)

    if not await ensure_force_join(update, context):
        return

    if context.user_data.get("state") != "await_payment_screenshot":
        await update.message.reply_text("📌 এই screenshot-এর জন্য কোনো active payment request নেই.")
        return

    uid = update.effective_user.id
    method = context.user_data.get("method")
    amount = context.user_data.get("amount")
    trx = context.user_data.get("trx_id")
    file_id = update.message.photo[-1].file_id

    if not method or not amount:
        context.user_data.clear()
        await update.message.reply_text("❌ Deposit session expired. Please start again.")
        return

    try:
        dep_id = db_execute(
            """INSERT INTO deposits
            (telegram_id,method,amount_bdt,trx_id,screenshot_file_id,status,created_at)
            VALUES(?,?,?,?,?,'pending',?)""",
            (uid, method, float(amount), trx, file_id, now_str())
        )
    except sqlite3.IntegrityError:
        await update.message.reply_text("❌ This TrxID has already been submitted.")
        return

    context.user_data.clear()
    await update.message.reply_text(
        f"{msg_icon('deposit_pending', 'Payment sent for review!', bold=True)}\n\nAdmin will verify shortly.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_reply_keyboard(get_user_language(update.effective_user.id))
    )


async def order_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await ensure_force_join(update, context):
        return

    uid = update.effective_user.id
    pid = context.user_data.get("product_id")
    qty = context.user_data.get("quantity")

    if not pid or not qty:
        await q.edit_message_text("❌ Order session expired. Please start again.")
        return

    qty = int(qty)
    auto_items = []
    auto_reserved = False

    # Atomic balance check + stock reservation/order creation.
    with DB_LOCK:
        con = db_connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            user = con.execute(
                "SELECT * FROM users WHERE telegram_id=?",
                (uid,)
            ).fetchone()
            product = con.execute(
                "SELECT * FROM products WHERE id=? AND active=1",
                (pid,)
            ).fetchone()

            if not product:
                con.rollback()
                await q.edit_message_text("❌ Product unavailable.")
                return

            total = round(float(product["price_bdt"]) * qty, 2)
            if user["bdt_balance"] + 1e-9 < total:
                con.rollback()
                await q.edit_message_text(
                    f"{msg_icon('insufficient_balance', 'Insufficient Balance', bold=True)}\n\n"
                    f"{msg_icon('total', 'Required:')} {total:.2f} BDT\n"
                    f"{msg_icon('balance', 'Current:')} {user['bdt_balance']:.2f} BDT",
                    parse_mode=ParseMode.HTML
                )
                context.user_data.clear()
                return

            if product["delivery_mode"] == "auto":
                rows = con.execute(
                    """SELECT id,content FROM product_stock_items
                       WHERE product_id=? AND status='available'
                       ORDER BY id ASC LIMIT ?""",
                    (pid, qty)
                ).fetchall()

                if len(rows) == qty:
                    auto_items = [r["content"] for r in rows]
                    auto_ids = [r["id"] for r in rows]
                    auto_reserved = True
                else:
                    auto_ids = []
            else:
                auto_ids = []

            con.execute(
                "UPDATE users SET bdt_balance=bdt_balance-? WHERE telegram_id=?",
                (total, uid)
            )

            cur = con.execute(
                """INSERT INTO orders
                (telegram_id,product_id,product_name,quantity,unit_price_bdt,total_bdt,
                 status,created_at,stock_deducted)
                VALUES(?,?,?,?,?,?,'pending',?,?)""",
                (
                    uid, pid, product["name"], qty, product["price_bdt"],
                    total, now_str(), 1 if auto_reserved else 0
                )
            )
            order_id = cur.lastrowid

            if auto_reserved:
                placeholders = ",".join("?" for _ in auto_ids)
                con.execute(
                    f"""UPDATE product_stock_items
                        SET status='reserved',order_id=?
                        WHERE id IN ({placeholders})""",
                    (order_id, *auto_ids)
                )

                remaining = con.execute(
                    """SELECT COUNT(*) c FROM product_stock_items
                       WHERE product_id=? AND status='available'""",
                    (pid,)
                ).fetchone()["c"]
                con.execute(
                    "UPDATE products SET stock=? WHERE id=?",
                    (remaining, pid)
                )

            con.commit()
        finally:
            con.close()

    context.user_data.clear()

    if not auto_reserved:
        # No ready auto-stock, or product is configured for manual delivery.
        waiting_message = render_message_template(
            "order_waiting",
            order_id=order_id,
            product_name=product["name"],
            quantity=qty,
            total_bdt=f"{total:.2f}",
        )
        await q.edit_message_text(
            waiting_message,
            parse_mode=ParseMode.HTML
        )
        return

    # Ready stock was atomically reserved. Deliver it immediately.
    try:
        intro = render_message_template(
            "order_auto_delivery",
            order_id=order_id,
            product_name=product["name"],
            quantity=qty,
        )
        await q.edit_message_text(intro, parse_mode=ParseMode.HTML)

        chunks = split_delivery_items(auto_items)
        for index, chunk in enumerate(chunks, 1):
            title = (
                f"📦 Order #{order_id} • {product['name']}\n"
                f"Stock {index}/{len(chunks)}\n\n"
            )
            await context.bot.send_message(
                chat_id=uid,
                text=title + chunk
            )

        with DB_LOCK:
            con = db_connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    """UPDATE product_stock_items
                       SET status='sold',sold_at=?
                       WHERE order_id=? AND status='reserved'""",
                    (now_str(), order_id)
                )
                con.execute(
                    """UPDATE orders SET
                       status='delivered',
                       delivery_text=?,
                       delivered_at=?,
                       delivered_by='AUTO-STOCK'
                       WHERE id=?""",
                    ("\n".join(auto_items), now_str(), order_id)
                )
                con.commit()
            finally:
                con.close()

    except Exception as exc:
        # If Telegram delivery itself fails, safely release the stock and refund.
        with DB_LOCK:
            con = db_connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                fresh = con.execute(
                    "SELECT * FROM orders WHERE id=?",
                    (order_id,)
                ).fetchone()

                if fresh and fresh["status"] == "pending":
                    con.execute(
                        "UPDATE users SET bdt_balance=bdt_balance+? WHERE telegram_id=?",
                        (fresh["total_bdt"], fresh["telegram_id"])
                    )
                    con.execute(
                        """UPDATE product_stock_items
                           SET status='available',order_id=NULL
                           WHERE order_id=? AND status='reserved'""",
                        (order_id,)
                    )
                    available = con.execute(
                        """SELECT COUNT(*) c FROM product_stock_items
                           WHERE product_id=? AND status='available'""",
                        (pid,)
                    ).fetchone()["c"]
                    con.execute(
                        "UPDATE products SET stock=? WHERE id=?",
                        (available, pid)
                    )
                    con.execute(
                        """UPDATE orders SET status='rejected',delivery_text=?
                           WHERE id=?""",
                        (f"Automatic Telegram delivery failed: {type(exc).__name__}", order_id)
                    )
                    con.commit()
                else:
                    con.rollback()
            finally:
                con.close()

        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    f"❌ Order #{order_id} auto-delivery failed.\n"
                    f"{total:.2f} BDT has been refunded to your balance."
                )
            )
        except Exception:
            pass

# =========================================================
# WEBSITE ADMIN PANEL
# =========================================================

webapp = Flask(__name__)
webapp.secret_key = SECRET_KEY
webapp.config['MAX_CONTENT_LENGTH'] = MAX_DELIVERY_FILE_BYTES + (1024 * 1024)

BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} - Shop Admin</title>
<style>
:root{
  --bg:#f6f8fc;
  --card:#ffffff;
  --text:#111827;
  --muted:#6b7280;
  --border:#e7ebf1;
  --blue:#2563eb;
  --blue2:#4f46e5;
  --green:#16a34a;
  --red:#dc2626;
  --yellow:#d97706;
  --shadow:0 10px 30px rgba(17,24,39,.08);
  --shadow-sm:0 4px 14px rgba(17,24,39,.06);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);
font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
a{color:inherit;text-decoration:none}
button,input,select,textarea{font:inherit}

.app{min-height:100vh}
.topbar{
  height:68px;background:#fff;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;position:sticky;top:0;z-index:1000;
  box-shadow:0 2px 10px rgba(17,24,39,.03)
}
.top-left{display:flex;align-items:center;gap:12px}
.menu-btn{
  width:42px;height:42px;border:1px solid var(--border);background:#fff;
  border-radius:12px;display:flex;align-items:center;justify-content:center;
  cursor:pointer;box-shadow:var(--shadow-sm);font-size:24px;font-weight:800;line-height:1
}
.menu-btn:hover{background:#f8fafc}
.brand-title{font-weight:800;font-size:18px;letter-spacing:-.2px}
.brand-sub{font-size:12px;color:var(--muted);margin-top:1px}
.admin-chip{
  display:flex;align-items:center;gap:9px;background:#f8fafc;border:1px solid var(--border);
  border-radius:999px;padding:7px 11px;color:#374151;font-size:13px
}
.avatar{
  width:30px;height:30px;border-radius:50%;
  background:linear-gradient(135deg,#2563eb,#7c3aed);color:white;
  display:flex;align-items:center;justify-content:center;font-weight:800
}

.sidebar{
  position:fixed;left:0;top:68px;bottom:0;width:270px;background:#fff;
  border-right:1px solid var(--border);padding:16px 12px;z-index:1100;
  transform:translateX(-100%);transition:transform .22s ease;
  box-shadow:16px 0 40px rgba(17,24,39,.08);overflow-y:auto
}
.sidebar.open{transform:translateX(0)}
.sidebar-title{font-size:12px;color:#9ca3af;text-transform:uppercase;font-weight:800;
letter-spacing:.08em;padding:8px 12px 10px}
.nav a{
  display:flex;align-items:center;gap:11px;padding:12px 13px;margin:4px 0;
  border-radius:12px;color:#374151;font-weight:650;transition:.18s
}
.nav a:hover{background:#f3f6fb;color:#111827}
.nav a.active{background:#eef4ff;color:#1d4ed8}
.nav .danger-link{color:#b91c1c}
.nav .danger-link:hover{background:#fff1f2}
.nav-icon{width:22px;text-align:center}

.overlay{
  position:fixed;inset:68px 0 0 0;background:rgba(15,23,42,.28);
  backdrop-filter:blur(1px);z-index:1050;display:none
}
.overlay.show{display:block}

.main{padding:24px;max-width:1480px;margin:0 auto;width:100%}
.page-head{
  display:flex;align-items:flex-start;justify-content:space-between;gap:12px;
  margin-bottom:20px
}
.page-head h1,.top h1{margin:0;font-size:26px;letter-spacing:-.45px}
.page-head p,.muted{color:var(--muted)}
.top{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:20px}
h1{font-size:26px;margin:0} h2{font-size:18px;margin-top:0}

.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px;margin-bottom:22px}
.card{
  background:var(--card);border:1px solid var(--border);border-radius:18px;
  padding:18px;box-shadow:var(--shadow-sm)
}
.stat-label{font-size:13px;color:var(--muted);font-weight:700}
.big{font-size:28px;font-weight:850;margin-top:8px;letter-spacing:-.5px}

.tablewrap{
  overflow:auto;background:#fff;border:1px solid var(--border);
  border-radius:18px;box-shadow:var(--shadow-sm)
}
table{width:100%;border-collapse:collapse;min-width:760px}
th,td{text-align:left;padding:13px 14px;border-bottom:1px solid var(--border);font-size:14px}
th{color:#6b7280;background:#fafbfc;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
tr:hover td{background:#fcfdff}

.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;
  border:0;border-radius:11px;padding:9px 13px;font-weight:750;cursor:pointer;
  transition:transform .12s ease,box-shadow .12s ease
}
.btn:hover{transform:translateY(-1px)}
.primary{background:#2563eb;color:#fff}
.success{background:#16a34a;color:#fff}
.danger{background:#dc2626;color:#fff}
.ghost{background:#f3f4f6;color:#111827;border:1px solid #e5e7eb}

input,select,textarea{
  width:100%;padding:11px 12px;background:#fff;color:#111827;
  border:1px solid #dfe4ea;border-radius:11px;outline:none
}
input:focus,select:focus,textarea:focus{
  border-color:#93b4ff;box-shadow:0 0 0 3px rgba(37,99,235,.08)
}
label{display:block;margin:12px 0 6px;color:#4b5563;font-size:13px;font-weight:700}
.formgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.actions{display:flex;gap:8px;flex-wrap:wrap}
.flash{
  padding:12px 14px;border-radius:12px;background:#eff6ff;color:#1e40af;
  border:1px solid #dbeafe;margin-bottom:14px
}
.badge{padding:5px 9px;border-radius:999px;font-size:12px;font-weight:800}
.pending{background:#fff7ed;color:#b45309}
.approved{background:#ecfdf5;color:#047857}
.rejected{background:#fff1f2;color:#be123c}
.loginbox{
  max-width:430px;margin:10vh auto;background:#fff;border:1px solid var(--border);
  border-radius:20px;padding:26px;box-shadow:var(--shadow)
}
img.pay{max-width:360px;width:100%;border-radius:14px;border:1px solid var(--border)}
.section-title{font-size:18px;font-weight:800;margin:0 0 12px}

@media(max-width:1000px){
  .cards{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:700px){
  .topbar{height:62px;padding:0 12px}
  .sidebar{top:62px;width:82vw;max-width:290px}
  .overlay{inset:62px 0 0 0}
  .main{padding:14px}
  .cards{grid-template-columns:1fr}
  .formgrid{grid-template-columns:1fr}
  .brand-sub{display:none}
  .brand-title{font-size:16px}
  .admin-chip span.label{display:none}
  .page-head h1,.top h1,h1{font-size:22px}
}
</style>
</head>
<body>

{% if session.get('admin_user') %}
<div class="app">
  <header class="topbar">
    <div class="top-left">
      <button class="menu-btn" id="menuBtn" aria-label="Open menu">⋮</button>
      <div>
        <div class="brand-title">🛍️ Will Be Earn Shop</div>
        <div class="brand-sub">Premium Admin Control Panel</div>
      </div>
    </div>

    <div class="admin-chip">
      <div class="avatar">{{ session.get('admin_user','A')[0]|upper }}</div>
      <span class="label">{{ session.get('admin_user') }}</span>
    </div>
  </header>

  <aside class="sidebar" id="sidebar">
    <div class="sidebar-title">Navigation</div>
    <nav class="nav">
      <a href="{{ url_for('admin_dashboard') }}"><span class="nav-icon">📊</span> Dashboard</a>
      <a href="{{ url_for('admin_users') }}"><span class="nav-icon">👥</span> Users</a>
      <a href="{{ url_for('admin_deposits') }}"><span class="nav-icon">💳</span> Deposits</a>
      <a href="{{ url_for('admin_payment_methods') }}"><span class="nav-icon">💸</span> Payment Methods</a>
      <a href="{{ url_for('admin_products') }}"><span class="nav-icon">🛍️</span> Products</a>
      <a href="{{ url_for('admin_orders') }}"><span class="nav-icon">🧾</span> Orders</a>
      <a href="{{ url_for('admin_settings') }}"><span class="nav-icon">⚙️</span> Settings</a>
      <a href="{{ url_for('admin_account') }}"><span class="nav-icon">🔐</span> Admin Account</a>
      <a href="{{ url_for('admin_usdt_sell') }}"><span class="nav-icon">$</span> USDT Sell</a>
      <a href="{{ url_for('admin_force_join') }}"><span class="nav-icon">🔒</span> Force Join</a>
      <a href="{{ url_for('admin_button_emojis') }}"><span class="nav-icon">◈</span> Button Emojis</a>
      <a href="{{ url_for('admin_message_emojis') }}"><span class="nav-icon">◇</span> Message Emojis</a>
      <a href="{{ url_for('admin_message_templates') }}"><span class="nav-icon">T</span> Message Templates</a>
      <a href="{{ url_for('admin_broadcast') }}"><span class="nav-icon">📢</span> Broadcast</a>
      <a href="{{ url_for('admin_logs') }}"><span class="nav-icon">📝</span> Logs</a>
      <a class="danger-link" href="{{ url_for('admin_logout') }}"><span class="nav-icon">🚪</span> Logout</a>
    </nav>
  </aside>

  <div class="overlay" id="overlay"></div>
  <main class="main">
{% else %}
<main class="main">
{% endif %}

{% with messages = get_flashed_messages() %}
  {% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}
{% endwith %}

{{ body|safe }}

</main>
{% if session.get('admin_user') %}</div>{% endif %}

<script>
(function(){
  const btn = document.getElementById('menuBtn');
  const side = document.getElementById('sidebar');
  const overlay = document.getElementById('overlay');

  function openMenu(){
    if(!side) return;
    side.classList.add('open');
    overlay.classList.add('show');
  }
  function closeMenu(){
    if(!side) return;
    side.classList.remove('open');
    overlay.classList.remove('show');
  }

  if(btn) btn.addEventListener('click', function(){
    side.classList.contains('open') ? closeMenu() : openMenu();
  });
  if(overlay) overlay.addEventListener('click', closeMenu);

  document.querySelectorAll('.nav a').forEach(function(a){
    a.addEventListener('click', closeMenu);
  });

  const path = window.location.pathname;
  document.querySelectorAll('.nav a').forEach(function(a){
    const href = a.getAttribute('href');
    if(href && href !== '/admin' && path.startsWith(href)){
      a.classList.add('active');
    }
    if(path === '/admin' && href === '/admin'){
      a.classList.add('active');
    }
  });
})();
</script>

</body>
</html>
"""


def render_page(title, body_template, **ctx):
    body = render_template_string(body_template, **ctx)
    return render_template_string(BASE_HTML, title=title, body=body)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_user"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


@webapp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = db_execute("SELECT * FROM admins WHERE username=?", (username,), fetchone=True)
        if row and check_password_hash(row["password_hash"], password):
            session["admin_user"] = username
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.")
    body = """
    <div class="loginbox">
      <h1>🔐 Admin Login</h1>
      <p class="muted">Website control panel</p>
      <form method="post">
        <label>Username</label><input name="username" required>
        <label>Password</label><input name="password" type="password" required>
        <button class="btn primary" style="width:100%;margin-top:16px">Login</button>
      </form>
    </div>
    """
    return render_page("Login", body)



@webapp.route("/admin/account", methods=["GET", "POST"])
@login_required
def admin_account():
    current_username = session.get("admin_user", "")

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_username = request.form.get("new_username", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        row = db_execute(
            "SELECT * FROM admins WHERE username=?",
            (current_username,),
            fetchone=True
        )

        if not row or not check_password_hash(row["password_hash"], current_password):
            flash("Current password is incorrect.")
            return redirect(url_for("admin_account"))

        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", new_username):
            flash("Username must be 3-50 characters: letters, numbers, _, . or -")
            return redirect(url_for("admin_account"))

        existing = db_execute(
            "SELECT username FROM admins WHERE username=? AND username<>?",
            (new_username, current_username),
            fetchone=True
        )
        if existing:
            flash("That admin username already exists.")
            return redirect(url_for("admin_account"))

        password_hash = row["password_hash"]
        if new_password:
            if len(new_password) < 8:
                flash("New password must be at least 8 characters.")
                return redirect(url_for("admin_account"))
            if new_password != confirm_password:
                flash("New password and confirmation do not match.")
                return redirect(url_for("admin_account"))
            password_hash = generate_password_hash(new_password)

        with DB_LOCK:
            con = db_connect()
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    "UPDATE admins SET username=?,password_hash=? WHERE username=?",
                    (new_username, password_hash, current_username)
                )
                con.commit()
            finally:
                con.close()

        session["admin_user"] = new_username
        admin_log(
            f"Changed admin account username from {current_username} to {new_username}"
            + (" and changed password" if new_password else "")
        )
        flash("Admin account updated successfully.")
        return redirect(url_for("admin_account"))

    body = """
    <div class="top">
      <div>
        <h1>🔐 Admin Account</h1>
        <div class="muted">Change the Admin Panel username and password.</div>
      </div>
    </div>

    <div class="card" style="max-width:720px">
      <form method="post">
        <label>New Admin Username</label>
        <input name="new_username" value="{{current_username}}" required>

        <label>Current Password</label>
        <input name="current_password" type="password" required
               autocomplete="current-password">

        <label>New Password</label>
        <input name="new_password" type="password"
               placeholder="Leave blank to keep current password"
               autocomplete="new-password">

        <label>Confirm New Password</label>
        <input name="confirm_password" type="password"
               placeholder="Repeat new password"
               autocomplete="new-password">

        <button class="btn success" style="margin-top:16px">
          Save Admin Account
        </button>
      </form>
    </div>
    """
    return render_page(
        "Admin Account",
        body,
        current_username=current_username
    )


@webapp.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@webapp.route("/")
def home():
    return redirect(url_for("admin_dashboard"))


@webapp.route("/admin")
@login_required
def admin_dashboard():
    stats = {
        "users": db_execute("SELECT COUNT(*) c FROM users", fetchone=True)["c"],
        "pending": db_execute("SELECT COUNT(*) c FROM deposits WHERE status='pending'", fetchone=True)["c"],
        "orders": db_execute("SELECT COUNT(*) c FROM orders", fetchone=True)["c"],
        "sales": db_execute("SELECT COALESCE(SUM(total_bdt),0) s FROM orders WHERE status IN ('pending','delivered','completed')", fetchone=True)["s"],
    }
    deposits = db_execute(
        "SELECT d.*,u.full_name,u.username FROM deposits d LEFT JOIN users u ON u.telegram_id=d.telegram_id "
        "ORDER BY d.id DESC LIMIT 8", fetchall=True
    )
    body = """
    <div class="top"><div><h1>📊 Dashboard</h1><div class="muted">Live marketplace overview</div></div></div>
    <div class="cards">
      <div class="card"><div class="muted">Users</div><div class="big">{{stats.users}}</div></div>
      <div class="card"><div class="muted">Pending Deposits</div><div class="big">{{stats.pending}}</div></div>
      <div class="card"><div class="muted">Orders</div><div class="big">{{stats.orders}}</div></div>
      <div class="card"><div class="muted">Sales (BDT)</div><div class="big">{{"%.2f"|format(stats.sales)}}</div></div>
    </div>
    <h2>Recent Deposits</h2>
    <div class="tablewrap"><table>
    <tr><th>ID</th><th>User</th><th>Method</th><th>Amount</th><th>TrxID</th><th>Status</th><th>Date</th></tr>
    {% for d in deposits %}
    <tr><td>#{{d.id}}</td><td>{{d.full_name or d.telegram_id}}</td><td>{{d.method}}</td>
    <td>{{"%.2f"|format(d.amount_bdt)}} BDT</td><td>{{d.trx_id or '-'}}</td>
    <td><span class="badge {{d.status}}">{{d.status}}</span></td><td>{{d.created_at}}</td></tr>
    {% endfor %}
    </table></div>
    """
    return render_page("Dashboard", body, stats=stats, deposits=deposits)


@webapp.route("/admin/users")
@login_required
def admin_users():
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        users = db_execute(
            "SELECT * FROM users WHERE CAST(telegram_id AS TEXT) LIKE ? OR username LIKE ? OR full_name LIKE ? "
            "ORDER BY joined_at DESC LIMIT 500",
            (like, like, like), fetchall=True
        )
    else:
        users = db_execute("SELECT * FROM users ORDER BY joined_at DESC LIMIT 500", fetchall=True)
    body = """
    <div class="top"><div><h1>👥 Users</h1><div class="muted">Search, balance and account controls</div></div></div>
    <form method="get" class="card" style="margin-bottom:14px"><div class="actions">
      <input name="q" value="{{q}}" placeholder="ID / username / name" style="max-width:420px">
      <button class="btn primary">Search</button>
    </div></form>
    <div class="tablewrap"><table>
    <tr><th>ID</th><th>Name</th><th>Username</th><th>Balance</th><th>Joined</th><th>Status</th><th>Action</th></tr>
    {% for u in users %}
    <tr>
      <td>{{u.telegram_id}}</td><td>{{u.full_name}}</td><td>@{{u.username or '-'}}</td>
      <td>{{"%.2f"|format(u.bdt_balance)}} BDT</td><td>{{u.joined_at}}</td>
      <td>{{'Banned' if u.banned else 'Active'}}</td>
      <td><a class="btn ghost" href="{{url_for('admin_user_edit', uid=u.telegram_id)}}">Manage</a></td>
    </tr>{% endfor %}
    </table></div>
    """
    return render_page("Users", body, users=users, q=q)


@webapp.route("/admin/users/<int:uid>", methods=["GET", "POST"])
@login_required
def admin_user_edit(uid):
    u = get_user(uid)
    if not u:
        return "User not found", 404

    if request.method == "POST":
        action = request.form.get("action")
        if action == "set_balance":
            try:
                bal = max(0.0, float(request.form.get("balance", "0")))
            except Exception:
                bal = u["bdt_balance"]
            db_execute("UPDATE users SET bdt_balance=? WHERE telegram_id=?", (bal, uid))
            admin_log(f"Set user {uid} balance to {bal:.2f} BDT")
            flash("Balance updated.")
        elif action == "toggle_ban":
            new = 0 if u["banned"] else 1
            db_execute("UPDATE users SET banned=? WHERE telegram_id=?", (new, uid))
            admin_log(f"{'Banned' if new else 'Unbanned'} user {uid}")
            flash("User status updated.")
        return redirect(url_for("admin_user_edit", uid=uid))

    u = get_user(uid)
    body = """
    <div class="top"><div><h1>👤 User {{u.telegram_id}}</h1><div class="muted">{{u.full_name}} · @{{u.username or '-'}}</div></div></div>
    <div class="card">
      <div class="formgrid">
        <div><b>Joined</b><p>{{u.joined_at}}</p></div>
        <div><b>Referral Count</b><p>{{u.referral_count}}</p></div>
      </div>
      <form method="post">
        <label>BDT Balance</label>
        <input type="number" step="0.01" min="0" name="balance" value="{{u.bdt_balance}}">
        <button class="btn success" name="action" value="set_balance" style="margin-top:12px">Save Balance</button>
      </form>
      <form method="post" style="margin-top:16px">
        <button class="btn {{'success' if u.banned else 'danger'}}" name="action" value="toggle_ban">
          {{'Unban User' if u.banned else 'Ban User'}}
        </button>
      </form>
    </div>
    """
    return render_page("User", body, u=u)


def tg_api_send_message(chat_id, text):
    if not BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception:
        return False



def tg_api_send_document(chat_id, file_path, caption=""):
    """Send a local file to a Telegram user using Bot API multipart upload."""
    if not BOT_TOKEN or not file_path or not os.path.isfile(file_path):
        return False

    try:
        file_size = os.path.getsize(file_path)
        if file_size > MAX_DELIVERY_FILE_BYTES:
            return False

        boundary = "----ShopBotBoundary" + secrets.token_hex(12)
        filename = os.path.basename(file_path)

        parts = []

        def add_field(name, value):
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n".encode("utf-8")
            )

        add_field("chat_id", str(chat_id))
        if caption:
            add_field("caption", caption)

        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()

        body = b"".join(parts) + header + file_bytes + b"\r\n" + f"--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def allowed_delivery_file(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_DELIVERY_EXTENSIONS



@webapp.route("/admin/deposits")
@login_required
def admin_deposits():
    status = request.args.get("status", "all")
    if status in {"pending", "approved", "rejected"}:
        deposits = db_execute(
            "SELECT d.*,u.full_name,u.username FROM deposits d LEFT JOIN users u ON u.telegram_id=d.telegram_id "
            "WHERE d.status=? ORDER BY d.id DESC", (status,), fetchall=True
        )
    else:
        deposits = db_execute(
            "SELECT d.*,u.full_name,u.username FROM deposits d LEFT JOIN users u ON u.telegram_id=d.telegram_id "
            "ORDER BY d.id DESC", fetchall=True
        )
    body = """
    <div class="top"><div><h1>💳 Deposits</h1><div class="muted">Review payment requests</div></div></div>
    <div class="actions" style="margin-bottom:14px">
      <a class="btn ghost" href="?status=all">All</a><a class="btn ghost" href="?status=pending">Pending</a>
      <a class="btn ghost" href="?status=approved">Approved</a><a class="btn ghost" href="?status=rejected">Rejected</a>
    </div>
    <div class="tablewrap"><table>
    <tr><th>ID</th><th>User</th><th>Method</th><th>Amount</th><th>TrxID</th><th>Status</th><th>Date</th><th>Action</th></tr>
    {% for d in deposits %}
    <tr>
      <td>#{{d.id}}</td><td>{{d.full_name or d.telegram_id}}</td><td>{{d.method}}</td>
      <td>{{"%.2f"|format(d.amount_bdt)}} BDT</td><td>{{d.trx_id or '-'}}</td>
      <td><span class="badge {{d.status}}">{{d.status}}</span></td><td>{{d.created_at}}</td>
      <td><a class="btn ghost" href="{{url_for('admin_deposit_view', dep_id=d.id)}}">Review</a></td>
    </tr>{% endfor %}
    </table></div>
    """
    return render_page("Deposits", body, deposits=deposits)


@webapp.route("/admin/deposits/<int:dep_id>", methods=["GET", "POST"])
@login_required
def admin_deposit_view(dep_id):
    d = db_execute(
        "SELECT d.*,u.full_name,u.username FROM deposits d LEFT JOIN users u ON u.telegram_id=d.telegram_id WHERE d.id=?",
        (dep_id,), fetchone=True
    )
    if not d:
        return "Deposit not found", 404

    if request.method == "POST" and d["status"] == "pending":
        action = request.form.get("action")
        note = request.form.get("note", "").strip()

        if action == "approve":
            with DB_LOCK:
                con = db_connect()
                try:
                    con.execute("BEGIN IMMEDIATE")
                    dep = con.execute("SELECT * FROM deposits WHERE id=?", (dep_id,)).fetchone()
                    if dep["status"] != "pending":
                        con.rollback()
                        flash("Already reviewed.")
                        return redirect(url_for("admin_deposit_view", dep_id=dep_id))

                    user = con.execute("SELECT * FROM users WHERE telegram_id=?", (dep["telegram_id"],)).fetchone()
                    amount = float(dep["amount_bdt"])
                    bonus = 0.0
                    referral_bonus = 0.0

                    if not user["first_deposit_bonus_used"]:
                        bp = fsetting("first_deposit_bonus_percent", 10.0)
                        bonus = round(amount * bp / 100.0, 2)

                        if user["referred_by"]:
                            rp = fsetting("referral_percent", 25.0)
                            referral_bonus = round(amount * rp / 100.0, 2)
                            con.execute(
                                "UPDATE users SET bdt_balance=bdt_balance+? WHERE telegram_id=?",
                                (referral_bonus, user["referred_by"])
                            )

                        con.execute(
                            "UPDATE users SET bdt_balance=bdt_balance+?, first_deposit_bonus_used=1 WHERE telegram_id=?",
                            (amount + bonus, dep["telegram_id"])
                        )
                    else:
                        con.execute(
                            "UPDATE users SET bdt_balance=bdt_balance+? WHERE telegram_id=?",
                            (amount, dep["telegram_id"])
                        )

                    con.execute(
                        "UPDATE deposits SET status='approved',reviewed_at=?,reviewed_by=?,note=? WHERE id=?",
                        (now_str(), session["admin_user"], note, dep_id)
                    )
                    con.commit()
                finally:
                    con.close()

            admin_log(f"Approved deposit #{dep_id} ({d['amount_bdt']:.2f} BDT) for user {d['telegram_id']}")
            bonus_line = ""
            if bonus > 0:
                bonus_line = f"First deposit bonus: {bonus:.2f} BDT"
            msg = render_message_template(
                "deposit_approved",
                amount_bdt=f"{d['amount_bdt']:.2f}",
                bonus_line=bonus_line,
            )
            tg_api_send_message(d["telegram_id"], msg)
            flash("Deposit approved and balance credited.")

        elif action == "reject":
            db_execute(
                "UPDATE deposits SET status='rejected',reviewed_at=?,reviewed_by=?,note=? WHERE id=? AND status='pending'",
                (now_str(), session["admin_user"], note, dep_id)
            )
            admin_log(f"Rejected deposit #{dep_id} for user {d['telegram_id']}")
            tg_api_send_message(
                d["telegram_id"],
                render_message_template("deposit_rejected")
            )
            flash("Deposit rejected.")
        return redirect(url_for("admin_deposit_view", dep_id=dep_id))

    # Telegram file preview link is fetched by file_id through Bot API only when needed.
    file_url = None
    if d["screenshot_file_id"] and BOT_TOKEN:
        try:
            api = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={urllib.parse.quote(d['screenshot_file_id'])}"
            with urllib.request.urlopen(api, timeout=10) as r:
                info = json.loads(r.read().decode())
            if info.get("ok"):
                file_path = info["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        except Exception:
            file_url = None

    body = """
    <div class="top"><div><h1>💳 Deposit #{{d.id}}</h1><div class="muted">{{d.full_name or d.telegram_id}}</div></div></div>
    <div class="card">
      <p><b>User:</b> {{d.full_name}} (@{{d.username or '-'}}) · {{d.telegram_id}}</p>
      <p><b>Method:</b> {{d.method}}</p>
      <p><b>Amount:</b> {{"%.2f"|format(d.amount_bdt)}} BDT</p>
      <p><b>TrxID:</b> {{d.trx_id or '-'}}</p>
      <p><b>Status:</b> <span class="badge {{d.status}}">{{d.status}}</span></p>
      <p><b>Created:</b> {{d.created_at}}</p>
      {% if file_url %}<p><b>Screenshot:</b></p><img class="pay" src="{{file_url}}">{% endif %}
      {% if d.status == 'pending' %}
      <form method="post">
        <label>Admin note</label><textarea name="note" rows="3"></textarea>
        <div class="actions" style="margin-top:14px">
          <button class="btn success" name="action" value="approve">✅ Approve</button>
          <button class="btn danger" name="action" value="reject">❌ Reject</button>
        </div>
      </form>
      {% else %}
      <p><b>Reviewed by:</b> {{d.reviewed_by or '-'}}</p><p><b>Note:</b> {{d.note or '-'}}</p>
      {% endif %}
    </div>
    """
    return render_page("Deposit", body, d=d, file_url=file_url)



@webapp.route("/admin/payment-methods", methods=["GET", "POST"])
@login_required
def admin_payment_methods():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code_name = request.form.get("code", "").strip().lower()
        icon = request.form.get("icon", "💵").strip() or "💵"
        account_number = request.form.get("account_number", "").strip()
        instructions = request.form.get("instructions", "").strip()
        try:
            min_deposit = float(request.form.get("min_deposit", "20"))
            sort_order = int(request.form.get("sort_order", "100"))
        except Exception:
            flash("Invalid minimum deposit or sort order.")
            return redirect(url_for("admin_payment_methods"))

        if not re.fullmatch(r"[a-z0-9_]{2,30}", code_name):
            flash("Code must use only lowercase letters, numbers and underscore.")
            return redirect(url_for("admin_payment_methods"))

        try:
            db_execute(
                """INSERT INTO payment_methods
                (name,code,icon,account_number,instructions,min_deposit,active,sort_order,created_at)
                VALUES(?,?,?,?,?,?,1,?,?)""",
                (name, code_name, icon, account_number, instructions, min_deposit, sort_order, now_str())
            )
            admin_log(f"Added payment method {name}")
            flash("Payment method added.")
        except sqlite3.IntegrityError:
            flash("Payment method name/code already exists.")
        return redirect(url_for("admin_payment_methods"))

    methods = get_payment_methods(active_only=False)
    body = """
    <div class="top"><div><h1>Payment Methods</h1><div class="muted">Add, remove, enable/disable and change payment numbers. Telegram premium icons are managed from Button Emojis.</div></div></div>

    <div class="card" style="margin-bottom:16px">
      <h2>Add Payment Method</h2>
      <form method="post">
        <div class="formgrid">
          <div><label>Name</label><input name="name" placeholder="bKash" required></div>
          <div><label>Code</label><input name="code" placeholder="bkash" required></div>
          <div><label>Icon</label><input name="icon" value="💵"></div>
          <div><label>Account / Number / Wallet</label><input name="account_number"></div>
          <div><label>Minimum Deposit</label><input type="number" step="0.01" min="0" name="min_deposit" value="20"></div>
          <div><label>Sort Order</label><input type="number" name="sort_order" value="100"></div>
        </div>
        <label>Instructions</label><textarea name="instructions" rows="3"></textarea>
        <button class="btn success" style="margin-top:14px">➕ Add Method</button>
      </form>
    </div>

    <div class="tablewrap"><table>
      <tr><th>ID</th><th>Method</th><th>Code</th><th>Number/Wallet</th><th>Min</th><th>Status</th><th>Action</th></tr>
      {% for m in methods %}
      <tr>
        <td>#{{m.id}}</td>
        <td>{{m.icon}} {{m.name}}</td>
        <td>{{m.code}}</td>
        <td>{{m.account_number or '-'}}</td>
        <td>{{"%.2f"|format(m.min_deposit)}} BDT</td>
        <td><span class="badge {{'approved' if m.active else 'rejected'}}">{{'ON' if m.active else 'OFF'}}</span></td>
        <td><a class="btn ghost" href="{{url_for('admin_payment_method_edit', mid=m.id)}}">Manage</a></td>
      </tr>
      {% endfor %}
    </table></div>
    """
    return render_page("Payment Methods", body, methods=methods)


@webapp.route("/admin/payment-methods/<int:mid>", methods=["GET", "POST"])
@login_required
def admin_payment_method_edit(mid):
    m = db_execute("SELECT * FROM payment_methods WHERE id=?", (mid,), fetchone=True)
    if not m:
        return "Payment method not found", 404

    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "delete":
            db_execute("DELETE FROM payment_methods WHERE id=?", (mid,))
            admin_log(f"Deleted payment method #{mid} {m['name']}")
            flash("Payment method deleted.")
            return redirect(url_for("admin_payment_methods"))

        if action == "toggle":
            new_status = 0 if m["active"] else 1
            db_execute("UPDATE payment_methods SET active=? WHERE id=?", (new_status, mid))
            admin_log(f"{'Enabled' if new_status else 'Disabled'} payment method #{mid}")
            flash("Payment method status changed.")
            return redirect(url_for("admin_payment_method_edit", mid=mid))

        name = request.form.get("name", "").strip()
        code_name = request.form.get("code", "").strip().lower()
        icon = request.form.get("icon", "💵").strip() or "💵"
        account_number = request.form.get("account_number", "").strip()
        instructions = request.form.get("instructions", "").strip()
        min_deposit = float(request.form.get("min_deposit", m["min_deposit"]))
        sort_order = int(request.form.get("sort_order", m["sort_order"]))

        if not re.fullmatch(r"[a-z0-9_]{2,30}", code_name):
            flash("Invalid code.")
            return redirect(url_for("admin_payment_method_edit", mid=mid))

        try:
            db_execute(
                """UPDATE payment_methods
                SET name=?,code=?,icon=?,account_number=?,instructions=?,min_deposit=?,sort_order=?
                WHERE id=?""",
                (name, code_name, icon, account_number, instructions, min_deposit, sort_order, mid)
            )
            admin_log(f"Updated payment method #{mid} {name}")
            flash("Payment method updated.")
        except sqlite3.IntegrityError:
            flash("Name/code already exists.")
        return redirect(url_for("admin_payment_method_edit", mid=mid))

    m = db_execute("SELECT * FROM payment_methods WHERE id=?", (mid,), fetchone=True)
    body = """
    <div class="top"><div><h1>💸 {{m.icon}} {{m.name}}</h1><div class="muted">Payment method settings</div></div></div>
    <div class="card">
      <form method="post">
        <div class="formgrid">
          <div><label>Name</label><input name="name" value="{{m.name}}" required></div>
          <div><label>Code</label><input name="code" value="{{m.code}}" required></div>
          <div><label>Icon</label><input name="icon" value="{{m.icon}}"></div>
          <div><label>Account / Number / Wallet</label><input name="account_number" value="{{m.account_number}}"></div>
          <div><label>Minimum Deposit</label><input name="min_deposit" type="number" min="0" step="0.01" value="{{m.min_deposit}}"></div>
          <div><label>Sort Order</label><input name="sort_order" type="number" value="{{m.sort_order}}"></div>
        </div>
        <label>Instructions</label><textarea name="instructions" rows="4">{{m.instructions}}</textarea>
        <div class="actions" style="margin-top:14px">
          <button class="btn success" name="action" value="save">💾 Save</button>
          <button class="btn {{'danger' if m.active else 'success'}}" name="action" value="toggle">
            {{'⛔ Turn OFF' if m.active else '✅ Turn ON'}}
          </button>
          <button class="btn danger" name="action" value="delete" onclick="return confirm('Delete this payment method?')">🗑 Delete</button>
        </div>
      </form>
    </div>
    """
    return render_page("Payment Method", body, m=m)


@webapp.route("/admin/products", methods=["GET", "POST"])
@login_required
def admin_products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "Mail").strip()
        delivery_mode = request.form.get("delivery_mode", "manual").strip().lower()
        if delivery_mode not in {"auto", "manual"}:
            delivery_mode = "manual"

        try:
            price = float(request.form.get("price", "0"))
        except Exception:
            flash("Invalid product price.")
            return redirect(url_for("admin_products"))

        if name and price >= 0:
            pid = db_execute(
                """INSERT INTO products
                   (category,name,price_bdt,stock,delivery_mode,active,created_at)
                   VALUES(?,?,?,0,?,1,?)""",
                (category, name, price, delivery_mode, now_str())
            )
            admin_log(f"Added product #{pid} {name} ({delivery_mode})")
            flash("Product added. Open Manage to upload Auto Stock if needed.")
        return redirect(url_for("admin_products"))

    products = db_execute(
        "SELECT * FROM products ORDER BY category,id DESC",
        fetchall=True
    )
    body = """
    <div class="top">
      <div>
        <h1>🛍️ Products</h1>
        <div class="muted">
          Auto Stock = instant delivery. Manual Delivery = order stays pending for Admin.
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>Add Product</h2>
      <form method="post">
        <div class="formgrid">
          <div>
            <label>Category</label>
            <select name="category">
              <option>Mail</option><option>VPN</option>
              <option>Proxy</option><option>Premium Apk</option>
            </select>
          </div>
          <div><label>Name</label><input name="name" required></div>
          <div>
            <label>Price BDT</label>
            <input name="price" type="number" min="0" step="0.01" required>
          </div>
          <div>
            <label>Delivery Mode</label>
            <select name="delivery_mode">
              <option value="auto">⚡ Auto Stock / Instant</option>
              <option value="manual">⏳ Manual / Wait</option>
            </select>
          </div>
        </div>
        <button class="btn success" style="margin-top:14px">Add Product</button>
      </form>
    </div>

    <div class="tablewrap"><table>
      <tr>
        <th>ID</th><th>Category</th><th>Name</th><th>Price</th>
        <th>Mode</th><th>Ready Stock</th><th>Active</th><th>Action</th>
      </tr>
      {% for p in products %}
      <tr>
        <td>#{{p.id}}</td>
        <td>{{p.category}}</td>
        <td>{{p.name}}</td>
        <td>{{"%.2f"|format(p.price_bdt)}} BDT</td>
        <td>
          <span class="badge {{'approved' if p.delivery_mode=='auto' else 'pending'}}">
            {{'AUTO' if p.delivery_mode=='auto' else 'MANUAL'}}
          </span>
        </td>
        <td>{{p.stock if p.delivery_mode=='auto' else '-'}}</td>
        <td>{{'Yes' if p.active else 'No'}}</td>
        <td>
          <a class="btn primary" href="{{url_for('admin_product_edit', pid=p.id)}}">Manage</a>
        </td>
      </tr>
      {% endfor %}
    </table></div>
    """
    return render_page("Products", body, products=products)


@webapp.route("/admin/products/<int:pid>", methods=["GET", "POST"])
@login_required
def admin_product_edit(pid):
    p = db_execute("SELECT * FROM products WHERE id=?", (pid,), fetchone=True)
    if not p:
        return "Product not found", 404

    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "delete":
            db_execute("DELETE FROM product_stock_items WHERE product_id=?", (pid,))
            db_execute("DELETE FROM products WHERE id=?", (pid,))
            admin_log(f"Deleted product #{pid} {p['name']}")
            flash("Product deleted.")
            return redirect(url_for("admin_products"))

        if action == "clear_available_stock":
            db_execute(
                "DELETE FROM product_stock_items WHERE product_id=? AND status='available'",
                (pid,)
            )
            sync_product_stock(pid)
            admin_log(f"Cleared available auto-stock for product #{pid}")
            flash("Available auto-stock cleared.")
            return redirect(url_for("admin_product_edit", pid=pid))

        if action == "add_stock":
            stock_text = request.form.get("stock_text", "")
            stock_file = request.files.get("stock_file")

            if stock_file and stock_file.filename:
                raw = stock_file.read()
                file_text = raw.decode("utf-8-sig", errors="ignore")
                if stock_text.strip():
                    stock_text += "\n"
                stock_text += file_text

            items = parse_stock_lines(stock_text)
            if not items:
                flash("Paste stock or upload a TXT file first.")
                return redirect(url_for("admin_product_edit", pid=pid))

            added, skipped = add_product_stock(pid, stock_text)
            db_execute(
                "UPDATE products SET delivery_mode='auto' WHERE id=?",
                (pid,)
            )
            admin_log(
                f"Uploaded auto-stock for product #{pid}: added={added}, skipped={skipped}"
            )
            flash(f"Stock uploaded: {added} added, {skipped} duplicate(s) skipped.")
            return redirect(url_for("admin_product_edit", pid=pid))

        # Save product settings
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "Mail").strip()
        delivery_mode = request.form.get("delivery_mode", "manual").strip().lower()
        if delivery_mode not in {"auto", "manual"}:
            delivery_mode = "manual"

        try:
            price = float(request.form.get("price", p["price_bdt"]))
        except Exception:
            flash("Invalid price.")
            return redirect(url_for("admin_product_edit", pid=pid))

        active = 1 if request.form.get("active") == "1" else 0
        db_execute(
            """UPDATE products
               SET category=?,name=?,price_bdt=?,delivery_mode=?,active=?
               WHERE id=?""",
            (category, name, price, delivery_mode, active, pid)
        )
        sync_product_stock(pid)
        admin_log(f"Updated product #{pid} {name} ({delivery_mode})")
        flash("Product updated.")
        return redirect(url_for("admin_product_edit", pid=pid))

    p = db_execute("SELECT * FROM products WHERE id=?", (pid,), fetchone=True)
    ready_count = product_available_stock(pid)
    if int(p["stock"]) != ready_count:
        sync_product_stock(pid)
        p = db_execute("SELECT * FROM products WHERE id=?", (pid,), fetchone=True)

    recent_stock = db_execute(
        """SELECT * FROM product_stock_items
           WHERE product_id=?
           ORDER BY id DESC LIMIT 100""",
        (pid,),
        fetchall=True
    )
    sold_count = db_execute(
        "SELECT COUNT(*) c FROM product_stock_items WHERE product_id=? AND status='sold'",
        (pid,),
        fetchone=True
    )["c"]
    reserved_count = db_execute(
        "SELECT COUNT(*) c FROM product_stock_items WHERE product_id=? AND status='reserved'",
        (pid,),
        fetchone=True
    )["c"]

    body = """
    <div class="top">
      <div>
        <h1>✏️ Manage Product #{{p.id}}</h1>
        <div class="muted">Configure delivery mode and upload ready stock.</div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>Product Settings</h2>
      <form method="post">
        <label>Category</label>
        <select name="category">
          {% for c in ['Mail','VPN','Proxy','Premium Apk'] %}
          <option {{'selected' if p.category==c else ''}}>{{c}}</option>
          {% endfor %}
        </select>

        <label>Name</label>
        <input name="name" value="{{p.name}}" required>

        <label>Price BDT</label>
        <input name="price" type="number" step="0.01" min="0" value="{{p.price_bdt}}">

        <label>Delivery Mode</label>
        <select name="delivery_mode">
          <option value="auto" {{'selected' if p.delivery_mode=='auto' else ''}}>
            ⚡ Auto Stock / Instant Delivery
          </option>
          <option value="manual" {{'selected' if p.delivery_mode=='manual' else ''}}>
            ⏳ Manual Delivery / Wait
          </option>
        </select>

        <label>Active</label>
        <select name="active">
          <option value="1" {{'selected' if p.active else ''}}>Yes</option>
          <option value="0" {{'selected' if not p.active else ''}}>No</option>
        </select>

        <div class="actions" style="margin-top:14px">
          <button class="btn success" name="action" value="save">Save</button>
          <button class="btn danger" name="action" value="delete"
                  onclick="return confirm('Delete this product?')">Delete</button>
        </div>
      </form>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>⚡ Auto Stock</h2>
      <div class="formgrid" style="margin-bottom:14px">
        <div><b>Ready</b><p>{{p.stock}}</p></div>
        <div><b>Reserved</b><p>{{reserved_count}}</p></div>
        <div><b>Sold</b><p>{{sold_count}}</p></div>
      </div>

      <p class="muted">
        One line = one product unit. Use this only for digital items/codes you
        are authorized to distribute. Do not upload third-party login credentials.
      </p>

      <form method="post" enctype="multipart/form-data">
        <label>Paste Stock — one item per line</label>
        <textarea name="stock_text" rows="10"
          placeholder="ITEM-001&#10;ITEM-002&#10;ITEM-003"></textarea>

        <label>Or Upload TXT Stock File</label>
        <input type="file" name="stock_file" accept=".txt,text/plain">

        <div class="actions" style="margin-top:14px">
          <button class="btn success" name="action" value="add_stock">
            Upload Stock
          </button>
          <button class="btn danger" name="action" value="clear_available_stock"
                  onclick="return confirm('Clear all AVAILABLE stock? Sold history will stay.')">
            Clear Available Stock
          </button>
        </div>
      </form>
    </div>

    <div class="tablewrap">
      <table>
        <tr><th>ID</th><th>Stock Item</th><th>Status</th><th>Order</th><th>Added</th></tr>
        {% for s in recent_stock %}
        <tr>
          <td>#{{s.id}}</td>
          <td><code>{{s.content}}</code></td>
          <td>
            <span class="badge {{'approved' if s.status=='sold' else ('pending' if s.status=='reserved' else '')}}">
              {{s.status}}
            </span>
          </td>
          <td>{{'#' ~ s.order_id if s.order_id else '-'}}</td>
          <td>{{s.created_at}}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    """
    return render_page(
        "Manage Product",
        body,
        p=p,
        recent_stock=recent_stock,
        sold_count=sold_count,
        reserved_count=reserved_count
    )

@webapp.route("/admin/orders")
@login_required
def admin_orders():
    status = request.args.get("status", "all").strip().lower()
    allowed = {"pending", "delivered", "completed", "rejected"}
    if status in allowed:
        orders = db_execute(
            "SELECT o.*,u.full_name,u.username FROM orders o "
            "LEFT JOIN users u ON u.telegram_id=o.telegram_id "
            "WHERE o.status=? ORDER BY o.id DESC LIMIT 1000",
            (status,), fetchall=True
        )
    else:
        orders = db_execute(
            "SELECT o.*,u.full_name,u.username FROM orders o "
            "LEFT JOIN users u ON u.telegram_id=o.telegram_id "
            "ORDER BY o.id DESC LIMIT 1000", fetchall=True
        )

    body = """
    <div class="top">
      <div><h1>🧾 Orders</h1><div class="muted">Accept orders and deliver text/files directly to Telegram users</div></div>
    </div>

    <div class="actions" style="margin-bottom:14px">
      <a class="btn ghost" href="?status=all">All</a>
      <a class="btn ghost" href="?status=pending">⏳ Pending</a>
      <a class="btn ghost" href="?status=delivered">✅ Delivered</a>
      <a class="btn ghost" href="?status=rejected">❌ Rejected</a>
    </div>

    <div class="tablewrap"><table>
    <tr><th>ID</th><th>User</th><th>Product</th><th>Qty</th><th>Total</th><th>Status</th><th>Date</th><th>Action</th></tr>
    {% for o in orders %}
    <tr>
      <td>#{{o.id}}</td>
      <td>{{o.full_name or o.telegram_id}}<br><span class="muted">@{{o.username or '-'}}</span></td>
      <td>{{o.product_name}}</td>
      <td>{{o.quantity}}</td>
      <td>{{"%.2f"|format(o.total_bdt)}} BDT</td>
      <td>
        <span class="badge {{'approved' if o.status in ['delivered','completed'] else ('rejected' if o.status=='rejected' else 'pending')}}">
          {{o.status}}
        </span>
      </td>
      <td>{{o.created_at}}</td>
      <td><a class="btn primary" href="{{url_for('admin_order_view', order_id=o.id)}}">Manage</a></td>
    </tr>
    {% endfor %}
    </table></div>
    """
    return render_page("Orders", body, orders=orders)



@webapp.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
@login_required
def admin_order_view(order_id):
    order = db_execute(
        "SELECT o.*,u.full_name,u.username FROM orders o "
        "LEFT JOIN users u ON u.telegram_id=o.telegram_id WHERE o.id=?",
        (order_id,), fetchone=True
    )
    if not order:
        return "Order not found", 404

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "deliver":
            if order["status"] in ("delivered", "completed"):
                flash("This order has already been delivered.")
                return redirect(url_for("admin_order_view", order_id=order_id))

            delivery_text = request.form.get("delivery_text", "").strip()
            upload = request.files.get("delivery_file")

            saved_path = None
            original_name = None

            if upload and upload.filename:
                original_name = secure_filename(upload.filename)
                if not original_name:
                    flash("Invalid file name.")
                    return redirect(url_for("admin_order_view", order_id=order_id))

                if not allowed_delivery_file(original_name):
                    flash("Unsupported file type. Allowed: TXT, PDF, ZIP/RAR/7Z, images, Office files and APK.")
                    return redirect(url_for("admin_order_view", order_id=order_id))

                upload.stream.seek(0, os.SEEK_END)
                size = upload.stream.tell()
                upload.stream.seek(0)

                if size > MAX_DELIVERY_FILE_BYTES:
                    flash(f"File is too large. Maximum {MAX_DELIVERY_FILE_MB} MB.")
                    return redirect(url_for("admin_order_view", order_id=order_id))

                order_folder = os.path.join(UPLOAD_DIR, f"order_{order_id}")
                os.makedirs(order_folder, exist_ok=True)
                stamped = f"{int(time.time())}_{original_name}"
                saved_path = os.path.join(order_folder, stamped)
                upload.save(saved_path)

            if not delivery_text and not saved_path:
                flash("Write delivery text or upload a file/app before accepting the order.")
                return redirect(url_for("admin_order_view", order_id=order_id))

            intro = render_message_template(
                "order_accepted",
                order_id=order_id,
                product_name=order["product_name"],
            )
            intro_ok = tg_api_send_message(order["telegram_id"], intro)

            text_ok = True
            if delivery_text:
                text_ok = tg_api_send_message(
                    order["telegram_id"],
                    render_message_template(
                        "order_delivery_text",
                        delivery_text=delivery_text
                    )
                )

            file_ok = True
            if saved_path:
                file_ok = tg_api_send_document(
                    order["telegram_id"],
                    saved_path,
                    caption=f"Order #{order_id} • {order['product_name']}"
                )

            if intro_ok and text_ok and file_ok:
                db_execute(
                    """UPDATE orders SET status='delivered',delivery_text=?,delivery_file_name=?,
                    delivery_file_path=?,delivered_at=?,delivered_by=? WHERE id=?""",
                    (
                        delivery_text or None,
                        original_name or None,
                        saved_path or None,
                        now_str(),
                        session["admin_user"],
                        order_id,
                    )
                )
                admin_log(f"Delivered order #{order_id} to user {order['telegram_id']}")
                flash("✅ Order accepted and delivery sent to the user.")
            else:
                flash("Telegram delivery failed. Order is still pending so you can try again.")
            return redirect(url_for("admin_order_view", order_id=order_id))

        if action == "reject":
            if order["status"] in ("delivered", "completed"):
                flash("Delivered order cannot be rejected.")
                return redirect(url_for("admin_order_view", order_id=order_id))

            # Refund the deducted balance and restore stock.
            with DB_LOCK:
                con = db_connect()
                try:
                    con.execute("BEGIN IMMEDIATE")
                    fresh = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
                    if fresh["status"] == "pending":
                        con.execute(
                            "UPDATE users SET bdt_balance=bdt_balance+? WHERE telegram_id=?",
                            (fresh["total_bdt"], fresh["telegram_id"])
                        )
                        if int(fresh["stock_deducted"] or 0) == 1:
                            reserved_count = con.execute(
                                """SELECT COUNT(*) c FROM product_stock_items
                                   WHERE order_id=? AND status='reserved'""",
                                (order_id,)
                            ).fetchone()["c"]

                            if reserved_count:
                                # New Auto-Stock order: release its exact reserved items.
                                con.execute(
                                    """UPDATE product_stock_items
                                       SET status='available',order_id=NULL
                                       WHERE order_id=? AND status='reserved'""",
                                    (order_id,)
                                )
                                available = con.execute(
                                    """SELECT COUNT(*) c FROM product_stock_items
                                       WHERE product_id=? AND status='available'""",
                                    (fresh["product_id"],)
                                ).fetchone()["c"]
                                con.execute(
                                    "UPDATE products SET stock=? WHERE id=?",
                                    (available, fresh["product_id"])
                                )
                            else:
                                # Legacy order from older bot versions:
                                # numeric stock had been deducted directly.
                                con.execute(
                                    "UPDATE products SET stock=stock+? WHERE id=?",
                                    (fresh["quantity"], fresh["product_id"])
                                )

                        con.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
                        con.commit()
                    else:
                        con.rollback()
                finally:
                    con.close()

            tg_api_send_message(
                order["telegram_id"],
                render_message_template(
                    "order_rejected",
                    order_id=order_id,
                    refund_bdt=f"{order['total_bdt']:.2f}",
                )
            )
            admin_log(f"Rejected/refunded order #{order_id}")
            flash("Order rejected and balance/stock restored.")
            return redirect(url_for("admin_order_view", order_id=order_id))

    order = db_execute(
        "SELECT o.*,u.full_name,u.username FROM orders o "
        "LEFT JOIN users u ON u.telegram_id=o.telegram_id WHERE o.id=?",
        (order_id,), fetchone=True
    )

    body = """
    <div class="top">
      <div>
        <h1>📦 Order #{{order.id}}</h1>
        <div class="muted">Review and deliver directly to the buyer's Telegram chat</div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <div class="formgrid">
        <div><b>👤 Customer</b><p>{{order.full_name or order.telegram_id}} · @{{order.username or '-'}}</p></div>
        <div><b>📱 Telegram ID</b><p>{{order.telegram_id}}</p></div>
        <div><b>📦 Product</b><p>{{order.product_name}}</p></div>
        <div><b>💎 Quantity</b><p>{{order.quantity}}</p></div>
        <div><b>💰 Total</b><p>{{"%.2f"|format(order.total_bdt)}} BDT</p></div>
        <div><b>📌 Status</b><p><span class="badge {{'approved' if order.status in ['delivered','completed'] else ('rejected' if order.status=='rejected' else 'pending')}}">{{order.status}}</span></p></div>
      </div>
    </div>

    {% if order.status == 'pending' %}
    <div class="card">
      <h2>✅ Accept & Deliver Order</h2>
      <p class="muted">
        You can send text, a file, an APK app, or text + file together.
        Use only files/content you own or are authorized to distribute.
      </p>

      <form method="post" enctype="multipart/form-data">
        <label>📩 Delivery Text / Account Info / Instructions</label>
        <textarea name="delivery_text" rows="8" placeholder="Write the content that should be sent to this user..."></textarea>

        <label>📎 Upload File / App (Optional)</label>
        <input type="file" name="delivery_file"
               accept=".txt,.pdf,.zip,.rar,.7z,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx,.apk">
        <div class="muted" style="margin-top:6px">Maximum file size: {{max_mb}} MB</div>

        <div class="actions" style="margin-top:16px">
          <button class="btn success" name="action" value="deliver">✅ Accept & Send</button>
          <button class="btn danger" name="action" value="reject"
                  onclick="return confirm('Reject this order and refund the user?')">❌ Reject & Refund</button>
        </div>
      </form>
    </div>
    {% elif order.status in ['delivered','completed'] %}
    <div class="card">
      <h2>✅ Delivery Completed</h2>
      <p><b>Delivered:</b> {{order.delivered_at or '-'}}</p>
      <p><b>Admin:</b> {{order.delivered_by or '-'}}</p>
      {% if order.delivery_text %}
      <label>Delivered Text</label>
      <textarea rows="8" readonly>{{order.delivery_text}}</textarea>
      {% endif %}
      {% if order.delivery_file_name %}
      <p><b>📎 Delivered File:</b> {{order.delivery_file_name}}</p>
      {% endif %}
    </div>
    {% else %}
    <div class="card"><h2>❌ Order Rejected / Refunded</h2></div>
    {% endif %}
    """
    return render_page("Order", body, order=order, max_mb=MAX_DELIVERY_FILE_MB)


@webapp.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    keys = [
        ("bot_username", "Bot Username"),
        ("support_username", "Support Telegram Username"),
        ("usdt_rate", "USDT Rate (1 USDT = BDT)"),
        ("min_deposit", "Minimum Deposit BDT"),
        ("referral_percent", "Referral Reward %"),
        ("first_deposit_bonus_percent", "First Deposit Bonus %"),
        ("delivery_minutes", "Order Delivery Time (Minutes)"),
        ("usdt_sell_rate", "USDT Sell Rate (1 USDT = BDT)"),
        ("usdt_sell_admin_username", "USDT Sell Admin Username"),
        ("usdt_sell_enabled", "USDT Sell Enabled (1/0)"),
        ("bkash_number", "bKash Number"),
        ("nagad_number", "Nagad Number"),
        ("rocket_number", "Rocket Number"),
        ("binance_usdt_address", "Binance USDT Address"),
        ("cash_voucher_note", "Cash Voucher Note"),
        ("hot_mail_url", "Hotmail/Outlook Code URL"),
        ("fr_outlook_url", "Fr Outlook Code URL"),
        ("api_gmail_url", "API Gmail Code URL"),
    ]
    if request.method == "POST":
        for key, _ in keys:
            set_setting(key, request.form.get(key, "").strip())
        admin_log("Updated settings")
        flash("Settings saved.")
        return redirect(url_for("admin_settings"))

    vals = {k: get_setting(k) for k, _ in keys}
    body = """
    <div class="top"><div><h1>⚙️ Settings</h1><div class="muted">Bot, payments, referral and links</div></div></div>
    <div class="card"><form method="post">
    {% for key,label in keys %}
      <label>{{label}}</label>
      {% if key == 'cash_voucher_note' %}
      <textarea name="{{key}}" rows="3">{{vals[key]}}</textarea>
      {% else %}
      <input name="{{key}}" value="{{vals[key]}}">
      {% endif %}
    {% endfor %}
    <button class="btn success" style="margin-top:16px">Save Settings</button>
    </form></div>
    """
    return render_page("Settings", body, keys=keys, vals=vals)





@webapp.route("/admin/force-join", methods=["GET", "POST"])
@login_required
def admin_force_join():
    if request.method == "POST":
        button_name = request.form.get("button_name", "").strip()
        join_url = request.form.get("join_url", "").strip()
        check_chat = request.form.get("check_chat", "").strip()
        try:
            sort_order = int(request.form.get("sort_order", "100"))
        except Exception:
            sort_order = 100

        if not button_name:
            flash("Button name is required.")
            return redirect(url_for("admin_force_join"))

        if not re.match(r"^https?://", join_url, re.I):
            flash("Enter a valid Telegram join link.")
            return redirect(url_for("admin_force_join"))

        if not check_chat:
            check_chat = derive_check_chat(join_url)

        if not check_chat:
            flash(
                "Private invite link detected. Enter the Channel/Group Chat ID "
                "(example: -1001234567890) in Check Chat ID / @username."
            )
            return redirect(url_for("admin_force_join"))

        db_execute(
            """INSERT INTO force_join_channels
               (button_name,join_url,check_chat,active,sort_order,created_at)
               VALUES(?,?,?,1,?,?)""",
            (button_name, join_url, check_chat, sort_order, now_str())
        )
        admin_log(f"Added force join: {button_name} ({check_chat})")
        flash("Force Join added.")
        return redirect(url_for("admin_force_join"))

    channels = get_force_join_channels(active_only=False)

    body = """
    <div class="top">
      <div>
        <h1>🔒 Force Join</h1>
        <div class="muted">Require users to join selected Telegram channels/groups.</div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>Add Force Join</h2>
      <form method="post">
        <div class="formgrid">
          <div>
            <label>Button Name</label>
            <input name="button_name" placeholder="Join Main Channel" required>
          </div>
          <div>
            <label>Join Link</label>
            <input name="join_url" placeholder="https://t.me/yourchannel" required>
          </div>
          <div>
            <label>Check Chat ID / @username</label>
            <input name="check_chat" placeholder="@yourchannel or -1001234567890">
            <div class="muted" style="margin-top:6px">
              Public t.me/username links are detected automatically.
              Private invite links require the numeric chat ID.
            </div>
          </div>
          <div>
            <label>Sort Order</label>
            <input name="sort_order" type="number" value="100">
          </div>
        </div>
        <button class="btn success" style="margin-top:14px">Add Force Join</button>
      </form>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>Membership Check</h2>
      <p class="muted">
        Add this bot as an Admin in each required channel/group so Telegram
        membership checking works reliably.
      </p>
    </div>

    <div class="tablewrap">
      <table>
        <tr>
          <th>ID</th><th>Button</th><th>Join Link</th><th>Check Chat</th>
          <th>Status</th><th>Order</th><th>Action</th>
        </tr>
        {% for c in channels %}
        <tr>
          <td>#{{c.id}}</td>
          <td><b>{{c.button_name}}</b></td>
          <td><a href="{{c.join_url}}" target="_blank">{{c.join_url}}</a></td>
          <td><code>{{c.check_chat}}</code></td>
          <td><span class="badge {{'approved' if c.active else 'rejected'}}">{{'ON' if c.active else 'OFF'}}</span></td>
          <td>{{c.sort_order}}</td>
          <td><a class="btn ghost" href="{{url_for('admin_force_join_edit', channel_id=c.id)}}">Manage</a></td>
        </tr>
        {% endfor %}
      </table>
    </div>
    """
    return render_page("Force Join", body, channels=channels)


@webapp.route("/admin/force-join/<int:channel_id>", methods=["GET", "POST"])
@login_required
def admin_force_join_edit(channel_id):
    channel = db_execute(
        "SELECT * FROM force_join_channels WHERE id=?",
        (channel_id,),
        fetchone=True
    )
    if not channel:
        return "Force Join entry not found", 404

    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "delete":
            db_execute("DELETE FROM force_join_channels WHERE id=?", (channel_id,))
            admin_log(f"Deleted force join #{channel_id} {channel['button_name']}")
            flash("Force Join deleted.")
            return redirect(url_for("admin_force_join"))

        if action == "toggle":
            new_status = 0 if channel["active"] else 1
            db_execute(
                "UPDATE force_join_channels SET active=? WHERE id=?",
                (new_status, channel_id)
            )
            admin_log(f"{'Enabled' if new_status else 'Disabled'} force join #{channel_id}")
            flash("Force Join status changed.")
            return redirect(url_for("admin_force_join_edit", channel_id=channel_id))

        button_name = request.form.get("button_name", "").strip()
        join_url = request.form.get("join_url", "").strip()
        check_chat = request.form.get("check_chat", "").strip()
        try:
            sort_order = int(request.form.get("sort_order", channel["sort_order"]))
        except Exception:
            sort_order = channel["sort_order"]

        if not button_name or not re.match(r"^https?://", join_url, re.I):
            flash("Button name and valid join URL are required.")
            return redirect(url_for("admin_force_join_edit", channel_id=channel_id))

        if not check_chat:
            check_chat = derive_check_chat(join_url)

        if not check_chat:
            flash("Check Chat ID / @username is required.")
            return redirect(url_for("admin_force_join_edit", channel_id=channel_id))

        db_execute(
            """UPDATE force_join_channels
               SET button_name=?,join_url=?,check_chat=?,sort_order=?
               WHERE id=?""",
            (button_name, join_url, check_chat, sort_order, channel_id)
        )
        admin_log(f"Updated force join #{channel_id} {button_name}")
        flash("Force Join updated.")
        return redirect(url_for("admin_force_join_edit", channel_id=channel_id))

    channel = db_execute(
        "SELECT * FROM force_join_channels WHERE id=?",
        (channel_id,),
        fetchone=True
    )

    body = """
    <div class="top">
      <div><h1>🔒 Manage Force Join #{{channel.id}}</h1></div>
    </div>
    <div class="card">
      <form method="post">
        <label>Button Name</label>
        <input name="button_name" value="{{channel.button_name}}" required>

        <label>Join Link</label>
        <input name="join_url" value="{{channel.join_url}}" required>

        <label>Check Chat ID / @username</label>
        <input name="check_chat" value="{{channel.check_chat}}" required>

        <label>Sort Order</label>
        <input name="sort_order" type="number" value="{{channel.sort_order}}">

        <div class="actions" style="margin-top:16px">
          <button class="btn success" name="action" value="save">Save</button>
          <button class="btn {{'danger' if channel.active else 'success'}}" name="action" value="toggle">
            {{'Turn OFF' if channel.active else 'Turn ON'}}
          </button>
          <button class="btn danger" name="action" value="delete"
                  onclick="return confirm('Delete this Force Join entry?')">Delete</button>
        </div>
      </form>
    </div>
    """
    return render_page("Manage Force Join", body, channel=channel)


@webapp.route("/admin/usdt-sell", methods=["GET", "POST"])
@login_required
def admin_usdt_sell():
    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "remove_admin":
            set_setting("usdt_sell_admin_username", "")
            admin_log("Removed USDT Sell admin contact")
            flash("USDT Sell admin contact removed.")
            return redirect(url_for("admin_usdt_sell"))

        username = request.form.get("admin_username", "").strip().lstrip("@")
        rate_raw = request.form.get("rate", "125").strip()
        enabled = "1" if request.form.get("enabled") == "1" else "0"

        try:
            rate = float(rate_raw)
            if rate <= 0:
                raise ValueError
        except Exception:
            flash("Enter a valid USDT sell rate.")
            return redirect(url_for("admin_usdt_sell"))

        if username and not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            flash("Invalid Telegram username.")
            return redirect(url_for("admin_usdt_sell"))

        set_setting("usdt_sell_admin_username", username)
        set_setting("usdt_sell_rate", f"{rate:g}")
        set_setting("usdt_sell_enabled", enabled)
        admin_log(
            f"Updated USDT Sell settings: admin=@{username or '-'}, rate={rate:g}, enabled={enabled}"
        )
        flash("USDT Sell settings saved.")
        return redirect(url_for("admin_usdt_sell"))

    username = get_setting("usdt_sell_admin_username", "Ariyan_Ahamed_Ari").strip().lstrip("@")
    rate = get_setting("usdt_sell_rate", "125")
    enabled = get_setting("usdt_sell_enabled", "1") in {"1", "true", "yes", "on"}

    body = """
    <div class="top">
      <div>
        <h1>USDT Sell</h1>
        <div class="muted">Manage the user-panel USDT Sell contact and rate</div>
      </div>
    </div>

    <div class="card">
      <form method="post">
        <label>Service Status</label>
        <select name="enabled">
          <option value="1" {{'selected' if enabled else ''}}>ON</option>
          <option value="0" {{'selected' if not enabled else ''}}>OFF</option>
        </select>

        <label>Admin Telegram Username</label>
        <input
          name="admin_username"
          value="{{username}}"
          placeholder="Ariyan_Ahamed_Ari"
        >
        <div class="muted" style="margin-top:6px">
          The Telegram inline button will open this username. Leave it blank or use Remove Admin to hide the contact button.
        </div>

        <label>USDT Sell Rate</label>
        <input
          name="rate"
          type="number"
          min="0.01"
          step="0.01"
          value="{{rate}}"
        >
        <div class="muted" style="margin-top:6px">
          Example: 125 means 1 USDT = 125 BDT.
        </div>

        <div class="actions" style="margin-top:16px">
          <button class="btn success" name="action" value="save">Save</button>
          <button
            class="btn danger"
            name="action"
            value="remove_admin"
            onclick="return confirm('Remove the USDT Sell admin contact?')"
          >Remove Admin</button>
        </div>
      </form>
    </div>
    """
    return render_page(
        "USDT Sell",
        body,
        username=username,
        rate=rate,
        enabled=enabled
    )


@webapp.route("/admin/button-emojis", methods=["GET", "POST"])
@login_required
def admin_button_emojis():
    if request.method == "POST":
        button_key = request.form.get("button_key", "").strip()
        label = request.form.get("label", "").strip() or button_key
        action = request.form.get("action", "save")

        if not button_key:
            flash("Button key is missing.")
            return redirect(url_for("admin_button_emojis"))

        try:
            emoji_id = "" if action == "clear" else request.form.get("emoji_id", "").strip()
            save_button_emoji(button_key, label, emoji_id)
            admin_log(
                f"{'Cleared' if not emoji_id else 'Updated'} custom emoji for button {button_key}"
            )
            flash("Button emoji updated.")
        except ValueError as exc:
            flash(str(exc))

        return redirect(url_for("admin_button_emojis"))

    rows = dynamic_button_emoji_rows()

    body = """
    <div class="top">
      <div>
        <h1>Button Emojis</h1>
        <div class="muted">
          Replace Telegram button icons using Premium Custom Emoji IDs.
          Leave an ID empty to show text only.
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>How it works</h2>
      <p class="muted">
        Enter the Telegram Custom Emoji ID for any button and press Save.
        The next time that keyboard is shown, the premium emoji will appear before the button text.
        Use Clear to remove the custom emoji without changing the button.
      </p>
    </div>

    <div class="tablewrap">
      <table>
        <tr>
          <th>Group</th>
          <th>Button</th>
          <th>Button Key</th>
          <th>Custom Emoji</th>
        </tr>
        {% for key,label,emoji_id,group in rows %}
        <tr>
          <td>{{group}}</td>
          <td><b>{{label}}</b></td>
          <td><code>{{key}}</code></td>
          <td style="min-width:360px">
            <form method="post" class="actions">
              <input type="hidden" name="button_key" value="{{key}}">
              <input type="hidden" name="label" value="{{label}}">
              <input
                name="emoji_id"
                value="{{emoji_id}}"
                inputmode="numeric"
                placeholder="Premium Custom Emoji ID"
                style="min-width:230px;max-width:330px"
              >
              <button class="btn success" name="action" value="save">Save</button>
              <button class="btn danger" name="action" value="clear">Clear</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </table>
    </div>
    """
    return render_page("Button Emojis", body, rows=rows)



@webapp.route("/admin/message-emojis", methods=["GET", "POST"])
@login_required
def admin_message_emojis():
    if request.method == "POST":
        emoji_key = request.form.get("emoji_key", "").strip()
        label = request.form.get("label", "").strip() or emoji_key
        fallback = request.form.get("fallback", "⭐").strip() or "⭐"
        action = request.form.get("action", "save")

        if not emoji_key:
            flash("Message emoji key is missing.")
            return redirect(url_for("admin_message_emojis"))

        try:
            emoji_id = "" if action == "clear" else request.form.get("emoji_id", "").strip()
            save_message_emoji(emoji_key, label, emoji_id, fallback)
            admin_log(
                f"{'Cleared' if not emoji_id else 'Updated'} message custom emoji {emoji_key}"
            )
            flash("Message emoji updated.")
        except ValueError as exc:
            flash(str(exc))

        return redirect(url_for("admin_message_emojis"))

    rows = message_emoji_rows()

    body = """
    <div class="top">
      <div>
        <h1>Message Emojis</h1>
        <div class="muted">
          Set Premium Custom Emoji IDs for Telegram message text.
          These are separate from button emojis.
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>Premium Emoji in SMS / Bot Messages</h2>
      <p class="muted">
        Paste a Telegram Custom Emoji ID and press Save.
        Messages using that slot will render the premium emoji through Telegram's custom emoji entity.
        If the ID is blank, no free emoji is added by the bot for that slot.
      </p>
    </div>

    <div class="tablewrap">
      <table>
        <tr>
          <th>Message Slot</th>
          <th>Key</th>
          <th>Premium Custom Emoji</th>
        </tr>
        {% for key,label,emoji_id,fallback in rows %}
        <tr>
          <td><b>{{label}}</b></td>
          <td><code>{{key}}</code></td>
          <td style="min-width:460px">
            <form method="post" class="actions">
              <input type="hidden" name="emoji_key" value="{{key}}">
              <input type="hidden" name="label" value="{{label}}">
              <input
                name="emoji_id"
                value="{{emoji_id}}"
                inputmode="numeric"
                placeholder="Premium Custom Emoji ID"
                style="min-width:220px;max-width:300px"
              >
              <input
                name="fallback"
                value="{{fallback}}"
                maxlength="8"
                title="Fallback emoji"
                style="max-width:82px"
              >
              <button class="btn success" name="action" value="save">Save</button>
              <button class="btn danger" name="action" value="clear">Clear</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </table>
    </div>
    """
    return render_page("Message Emojis", body, rows=rows)



@webapp.route("/admin/message-templates")
@login_required
def admin_message_templates():
    rows = message_template_rows()
    body = """
    <div class="top">
      <div>
        <h1>Message Templates</h1>
        <div class="muted">
          Edit bot messages and insert as many Premium Custom Emojis as you want, anywhere in the text.
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>Emoji Syntax</h2>
      <p class="muted">
        Named emoji slot:
        <code>[[emoji_key:order_success]]</code>
      </p>
      <p class="muted">
        Direct Custom Emoji ID:
        <code>[[emoji:5368324170671202286|⭐]]</code>
      </p>
      <p class="muted">
        You can repeat these placeholders unlimited times and place them at the beginning,
        middle or end of any line.
      </p>
    </div>

    <div class="cards">
      {% for t in rows %}
      <a class="card" href="{{url_for('admin_message_template_edit', template_key=t.key)}}">
        <div class="stat-label">{{t.key}}</div>
        <div style="font-size:17px;font-weight:800;margin-top:7px">{{t.label}}</div>
        <div class="muted" style="margin-top:8px">Tap to edit message</div>
      </a>
      {% endfor %}
    </div>
    """
    return render_page("Message Templates", body, rows=rows)


@webapp.route("/admin/message-templates/<template_key>", methods=["GET", "POST"])
@login_required
def admin_message_template_edit(template_key):
    info = MESSAGE_TEMPLATE_DEFINITIONS.get(template_key)
    if not info:
        return "Template not found", 404

    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "reset":
            save_message_template(template_key, info["label"], info["body"])
            admin_log(f"Reset message template {template_key}")
            flash("Template reset to default.")
        else:
            body_value = request.form.get("body", "")
            save_message_template(template_key, info["label"], body_value)
            admin_log(f"Updated message template {template_key}")
            flash("Message template saved.")
        return redirect(url_for("admin_message_template_edit", template_key=template_key))

    row = db_execute(
        "SELECT * FROM message_templates WHERE template_key=?",
        (template_key,),
        fetchone=True
    )
    template_body = row["body"] if row else info["body"]

    emoji_rows = message_emoji_rows()

    body = """
    <div class="top">
      <div>
        <h1>{{info.label}}</h1>
        <div class="muted">Template key: <code>{{template_key}}</code></div>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <h2>Insert Premium Emojis Anywhere</h2>
      <p class="muted">
        Example:
        <code>[[emoji_key:success]] Hello [[emoji_key:product]] World [[emoji_key:success]]</code>
      </p>
      <p class="muted">
        Or paste a direct ID:
        <code>[[emoji:5368324170671202286|⭐]]</code>
      </p>

      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
        {% for key,label,emoji_id,fallback in emoji_rows %}
        <button type="button" class="btn ghost"
                onclick="insertToken('[[emoji_key:{{key}}]]')">
          {{label}}
        </button>
        {% endfor %}
      </div>
    </div>

    <div class="card">
      <form method="post">
        <label>Message Body</label>
        <textarea id="messageBody" name="body" rows="18" style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace">{{template_body}}</textarea>

        <div class="actions" style="margin-top:14px">
          <button class="btn success" name="action" value="save">Save Template</button>
          <button class="btn danger" name="action" value="reset"
                  onclick="return confirm('Reset this template to default?')">Reset Default</button>
        </div>
      </form>
    </div>

    <script>
    function insertToken(token){
      const el = document.getElementById('messageBody');
      if(!el) return;
      const start = el.selectionStart || 0;
      const end = el.selectionEnd || 0;
      const before = el.value.substring(0,start);
      const after = el.value.substring(end);
      el.value = before + token + after;
      const pos = start + token.length;
      el.focus();
      el.setSelectionRange(pos,pos);
    }
    </script>
    """
    return render_page(
        "Edit Message Template",
        body,
        info=info,
        template_key=template_key,
        template_body=template_body,
        emoji_rows=emoji_rows
    )


@webapp.route("/admin/broadcast", methods=["GET", "POST"])
@login_required
def admin_broadcast():
    if request.method == "POST":
        text = request.form.get("message", "").strip()
        if not text:
            flash("Message is empty.")
            return redirect(url_for("admin_broadcast"))

        users = db_execute("SELECT telegram_id FROM users WHERE banned=0", fetchall=True)
        ok = 0
        fail = 0
        for u in users:
            if tg_api_send_message(u["telegram_id"], html.escape(text)):
                ok += 1
            else:
                fail += 1
            time.sleep(0.04)
        admin_log(f"Broadcast sent: success={ok}, failed={fail}")
        flash(f"Broadcast finished. Success: {ok}, Failed: {fail}")
        return redirect(url_for("admin_broadcast"))

    body = """
    <div class="top"><div><h1>📢 Broadcast</h1><div class="muted">Send a Telegram message to all active users</div></div></div>
    <div class="card"><form method="post">
      <label>Message</label><textarea name="message" rows="8" required></textarea>
      <button class="btn success" style="margin-top:14px">Send Broadcast</button>
    </form></div>
    """
    return render_page("Broadcast", body)


@webapp.route("/admin/logs")
@login_required
def admin_logs():
    logs = db_execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT 500", fetchall=True)
    body = """
    <div class="top"><div><h1>📝 Admin Logs</h1></div></div>
    <div class="tablewrap"><table><tr><th>ID</th><th>Admin</th><th>Action</th><th>Date</th></tr>
    {% for x in logs %}<tr><td>#{{x.id}}</td><td>{{x.admin_username}}</td><td>{{x.action}}</td><td>{{x.created_at}}</td></tr>{% endfor %}
    </table></div>
    """
    return render_page("Logs", body, logs=logs)


# =========================================================
# ADMIN PASSWORD CHANGE
# =========================================================

@webapp.route("/admin/password", methods=["POST"])
@login_required
def admin_password():
    # Kept for backward compatibility with older links/forms.
    return redirect(url_for("admin_account"))

# =========================================================
# RUN
# =========================================================

def run_admin_web():
    # Flask threaded server. For large production deployments, put it behind
    # Nginx/Cloudflare and use a production WSGI server.
    webapp.run(host=ADMIN_HOST, port=ADMIN_PORT, debug=False, use_reloader=False, threaded=True)


def build_bot():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Set it first, e.g.:\n"
            "Linux/Termux: export BOT_TOKEN='YOUR_TOKEN'\n"
            "Windows CMD: set BOT_TOKEN=YOUR_TOKEN"
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))

    app.add_handler(CallbackQueryHandler(force_join_check_callback, pattern=r"^force_join_check$"))

    app.add_handler(CallbackQueryHandler(category_callback, pattern=r"^cat:"))
    app.add_handler(CallbackQueryHandler(product_categories_callback, pattern=r"^product_categories$"))
    app.add_handler(CallbackQueryHandler(product_callback, pattern=r"^prod:\d+$"))
    app.add_handler(CallbackQueryHandler(order_confirm_callback, pattern=r"^order_confirm$"))

    app.add_handler(CallbackQueryHandler(profile_callback, pattern=r"^profile_"))

    app.add_handler(CallbackQueryHandler(deposit_method_callback, pattern=r"^dep_method:"))
    app.add_handler(CallbackQueryHandler(binance_currency_callback, pattern=r"^binance_currency:"))
    app.add_handler(CallbackQueryHandler(deposit_methods_callback, pattern=r"^deposit_methods$"))
    app.add_handler(CallbackQueryHandler(paid_callback, pattern=r"^deposit_paid$"))
    app.add_handler(CallbackQueryHandler(screenshot_prompt_callback, pattern=r"^deposit_screenshot$"))

    app.add_handler(CallbackQueryHandler(support_cancel_callback, pattern=r"^support_cancel$"))
    app.add_handler(CallbackQueryHandler(usdt_sell_cancel_callback, pattern=r"^usdt_sell_cancel$"))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^set_language:(bn|en)$"))

    app.add_handler(MessageHandler(filters.PHOTO, photo_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    return app


def main():
    init_db()

    print("=" * 60)
    print("Will Be Earn Shop")
    print(f"Database : {DB_PATH}")
    print(f"Admin    : http://{ADMIN_HOST}:{ADMIN_PORT}/admin")
    print(f"Login    : {DEFAULT_ADMIN_USER}")
    if os.getenv("ADMIN_PASSWORD") is None:
        print("WARNING  : default admin password is admin123 - change it!")
    print("=" * 60)

    t = threading.Thread(target=run_admin_web, daemon=True)
    t.start()

    bot = build_bot()
    bot.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
