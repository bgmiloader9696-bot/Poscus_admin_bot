#!/usr/bin/env python3
# POSCUS PREDICTER - COMPLETE BOT

import requests
import json
import time
import logging
import random
import warnings
import os
import secrets
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=UserWarning, module="telegram")
warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# Flask app for port binding
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({"status": "running", "bot": "POSCUS PREDICTER"})

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy"})

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

logging.basicConfig(level=logging.ERROR)

# ==============================================
# CONFIG
# ==============================================
BOT_TOKEN = "8992304126:AAGups0z9tf4Hl1lTCHtj7X8qqMlwjT9o64"
SERVER_URL = "https://poscus-predicter.onrender.com"
ADMIN_TOKEN = "VC5SA9AT0H2010"
ADMIN_IDS = [6548871396]
# ==============================================

HEADERS_ADMIN = {"Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN}

# Conversation states
ASK_DEVICE, ASK_NAME, ASK_EXPIRY = range(3)
ASK_DEL_DEVICE = 10
ASK_RESELLER_NAME, ASK_RESELLER_TELEGRAM_ID, ASK_RESELLER_TOKENS = range(20, 23)
ASK_RESELLER_TOKEN = 30
ASK_RESELLER_DEL_DEVICE = 40
ASK_RESELLER_CHECK_DEVICE = 50
ASK_ADD_TOKENS_RID, ASK_ADD_TOKENS_AMOUNT = range(60, 62)
ASK_RESELLER_DEVICE, ASK_RESELLER_DEVICE_NAME, ASK_RESELLER_DEVICE_EXPIRY = range(70, 73)
ASK_DEL_RESELLER = 80

def is_admin(uid): 
    return uid in ADMIN_IDS

def generate_reseller_token():
    return secrets.token_hex(16).upper()

def api_get(path, headers=None):
    try:
        r = requests.get(SERVER_URL + path, headers=headers or HEADERS_ADMIN, timeout=30)
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}

def api_post(path, data, headers=None):
    try:
        r = requests.post(SERVER_URL + path, headers=headers or HEADERS_ADMIN, json=data, timeout=30)
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}", "msg": r.text}
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}

def expiry_from_choice(choice):
    now = datetime.now()
    map_ = {
        "1h": now + timedelta(hours=1), "2h": now + timedelta(hours=2), "3h": now + timedelta(hours=3),
        "4h": now + timedelta(hours=4), "5h": now + timedelta(hours=5), "6h": now + timedelta(hours=6),
        "12h": now + timedelta(hours=12), "1d": now + timedelta(days=1), "3d": now + timedelta(days=3),
        "7d": now + timedelta(days=7), "15d": now + timedelta(days=15), "30d": now + timedelta(days=30),
        "60d": now + timedelta(days=60)
    }
    dt = map_.get(choice)
    return dt.strftime("%Y-%m-%d") if dt else ""

def get_token_cost(choice):
    cost_map = {
        "1h": 1, "2h": 2, "3h": 3, "4h": 4, "5h": 5, "6h": 6,
        "12h": 10, "1d": 15, "3d": 25, "7d": 40,
        "15d": 60, "30d": 100, "60d": 150
    }
    return cost_map.get(choice, 1)

def fmt_expiry(exp):
    if not exp or exp == "lifetime":
        return "♾️ Lifetime"
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        if exp < today:
            return f"⏰ Expired"
        diff = (datetime.strptime(exp, "%Y-%m-%d") - datetime.now()).days
        if diff <= 3:
            return f"⚠️ {diff}d left"
        return f"✅ {diff}d left"
    except:
        return f"📅 {exp}"

# ==================== PING FUNCTION ====================
async def ping_server(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if is_admin(uid):
        s = time.time()
        try:
            r = requests.get(SERVER_URL + "/api/ping", timeout=10)
            ms = int((time.time() - s) * 1000)
            if r.status_code == 200:
                status = "🟢 Online"
            else:
                status = "🟡 Partial"
            text = f"🏓 Pong! (Real)\n\nServer: {SERVER_URL}\nResponse: {ms}ms\nStatus: {status}"
        except:
            ms = int((time.time() - s) * 1000)
            text = f"🏓 Pong! (Real)\n\nServer: {SERVER_URL}\nResponse: {ms}ms\nStatus: 🔴 Offline"
    else:
        fake_ping = random.randint(20, 30)
        try:
            r = requests.get(SERVER_URL + "/api/ping", timeout=5)
            if r.status_code == 200:
                status = "🟢 Online"
            else:
                status = "🟡 Partial"
        except:
            status = "🔴 Offline"
        text = f"🏓 Pong!\n\nServer: {SERVER_URL}\nResponse: {fake_ping}ms\nStatus: {status}"
    
    await update.message.reply_text(text)

# ==================== KEYBOARDS ====================
def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 All Devices", "➕ Add Device"],
        ["🗑️ Delete Device", "👥 Resellers"],
        ["➕ Add Reseller", "🗑️ Delete Reseller"],
        ["💰 Add Tokens", "📊 Stats"],
        ["🌐 Ping Server", "🏠 Main Menu"]
    ], resize_keyboard=True)

def get_reseller_keyboard():
    return ReplyKeyboardMarkup([
        ["📱 My Devices", "➕ Add Device"],
        ["🗑️ Delete Device", "🔍 Check Device"],
        ["💰 My Balance", "🌐 Ping Server"],
        ["🚪 Logout", "🏠 Main Menu"]
    ], resize_keyboard=True)

def get_normal_keyboard():
    return ReplyKeyboardMarkup([
        ["🔑 Reseller Login"],
        ["🌐 Ping Server"]
    ], resize_keyboard=True)

def get_reseller_expiry_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 Hour (1 token)", callback_data="exp_1h"), InlineKeyboardButton("2 Hours (2)", callback_data="exp_2h"), InlineKeyboardButton("3 Hours (3)", callback_data="exp_3h")],
        [InlineKeyboardButton("4 Hours (4)", callback_data="exp_4h"), InlineKeyboardButton("5 Hours (5)", callback_data="exp_5h"), InlineKeyboardButton("6 Hours (6)", callback_data="exp_6h")],
        [InlineKeyboardButton("12 Hours (10)", callback_data="exp_12h"), InlineKeyboardButton("1 Day (15)", callback_data="exp_1d"), InlineKeyboardButton("3 Days (25)", callback_data="exp_3d")],
        [InlineKeyboardButton("7 Days (40)", callback_data="exp_7d"), InlineKeyboardButton("15 Days (60)", callback_data="exp_15d"), InlineKeyboardButton("30 Days (100)", callback_data="exp_30d")],
        [InlineKeyboardButton("60 Days (150)", callback_data="exp_60d")]
    ])

def get_admin_expiry_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 Hour", callback_data="exp_1h"), InlineKeyboardButton("2 Hours", callback_data="exp_2h"), InlineKeyboardButton("3 Hours", callback_data="exp_3h")],
        [InlineKeyboardButton("4 Hours", callback_data="exp_4h"), InlineKeyboardButton("5 Hours", callback_data="exp_5h"), InlineKeyboardButton("6 Hours", callback_data="exp_6h")],
        [InlineKeyboardButton("12 Hours", callback_data="exp_12h"), InlineKeyboardButton("1 Day", callback_data="exp_1d"), InlineKeyboardButton("3 Days", callback_data="exp_3d")],
        [InlineKeyboardButton("7 Days", callback_data="exp_7d"), InlineKeyboardButton("15 Days", callback_data="exp_15d"), InlineKeyboardButton("30 Days", callback_data="exp_30d")],
        [InlineKeyboardButton("60 Days", callback_data="exp_60d"), InlineKeyboardButton("♾️ LIFETIME", callback_data="exp_life")]
    ])

# ==================== WELCOME MESSAGES ====================

# ADMIN WELCOME
async def admin_welcome(update: Update):
    keys = api_get("/api/admin/keys")
    resellers = api_get("/api/admin/resellers")
    
    total_devices = len(keys) if isinstance(keys, dict) else 0
    total_resellers = len(resellers) if isinstance(resellers, dict) else 0
    
    msg = f"""🔮 POSCUS PREDICTER BOT
━━━━━━━━━━━━━━━
👑 ADMIN PANEL

✅ Server Connected
✅ Total Devices: {total_devices}
✅ Active Resellers: {total_resellers}

Use buttons below to manage system."""
    
    await update.message.reply_text(msg)

# RESELLER WELCOME
async def reseller_welcome(update: Update, token, name, tokens_left, device_count):
    if tokens_left == -1:
        balance_display = "♾️ Unlimited"
    else:
        balance_display = f"{tokens_left} tokens"
    
    msg = f"""🔮 POSCUS PREDICTER BOT
━━━━━━━━━━━━━━━
🤝 RESELLER PANEL

👤 Name: {name}
💰 Balance: {balance_display}
📱 Your Devices: {device_count}

⚠️ Lifetime keys NOT allowed!
Use buttons below to manage devices."""
    
    await update.message.reply_text(msg)

# NORMAL USER WELCOME
async def normal_welcome(update: Update):
    msg = """🔮 POSCUS PREDICTER BOT
━━━━━━━━━━━━━━━
Welcome!

🔑 Reseller Login - Access your panel
🌐 Ping Server - Check connection

Contact admin for reseller account."""
    
    await update.message.reply_text(msg)

# ==================== START ====================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if is_admin(uid):
        ctx.user_data['role'] = 'admin'
        await admin_welcome(update)
        await update.message.reply_text(
            "Use buttons below:",
            reply_markup=get_admin_keyboard()
        )
    elif ctx.user_data.get('reseller_token'):
        ctx.user_data['role'] = 'reseller'
        headers = {"X-Reseller-Token": ctx.user_data['reseller_token']}
        stats = api_get("/api/reseller/stats", headers=headers)
        
        if "error" in stats:
            await update.message.reply_text(f"❌ Error: {stats['error']}")
            return
        
        tokens_left = stats.get('tokens_left', 0)
        name = stats.get('name', 'Reseller')
        
        # Get device count
        keys = api_get("/api/reseller/keys", headers=headers)
        device_count = len(keys) if isinstance(keys, dict) else 0
        
        await reseller_welcome(update, ctx.user_data['reseller_token'], name, tokens_left, device_count)
        await update.message.reply_text(
            "Use buttons below:",
            reply_markup=get_reseller_keyboard()
        )
    else:
        ctx.user_data['role'] = 'normal'
        await normal_welcome(update)
        await update.message.reply_text(
            "Use buttons below:",
            reply_markup=get_normal_keyboard()
        )

# ==================== TEXT HANDLER ====================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    
    if is_admin(uid) or ctx.user_data.get('role') == 'admin':
        if text == "📋 All Devices":
            await show_all_devices(update, ctx)
        elif text == "➕ Add Device":
            await add_device_start(update, ctx)
        elif text == "🗑️ Delete Device":
            await delete_device_start(update, ctx)
        elif text == "👥 Resellers":
            await show_resellers(update, ctx)
        elif text == "➕ Add Reseller":
            await add_reseller_start(update, ctx)
        elif text == "🗑️ Delete Reseller":
            await delete_reseller_start(update, ctx)
        elif text == "💰 Add Tokens":
            await add_tokens_start(update, ctx)
        elif text == "📊 Stats":
            await show_stats(update, ctx)
        elif text == "🌐 Ping Server":
            await ping_server(update, ctx)
        elif text == "🏠 Main Menu":
            await admin_welcome(update)
            await update.message.reply_text("Main Menu:", reply_markup=get_admin_keyboard())
    
    elif ctx.user_data.get('reseller_token'):
        if text == "📱 My Devices":
            await reseller_my_devices(update, ctx)
        elif text == "➕ Add Device":
            await reseller_add_device_start(update, ctx)
        elif text == "🗑️ Delete Device":
            await reseller_delete_device_start(update, ctx)
        elif text == "🔍 Check Device":
            await reseller_check_device_start(update, ctx)
        elif text == "💰 My Balance":
            await reseller_my_balance(update, ctx)
        elif text == "🌐 Ping Server":
            await ping_server(update, ctx)
        elif text == "🚪 Logout":
            ctx.user_data.pop('reseller_token', None)
            ctx.user_data.pop('reseller_id', None)
            ctx.user_data['role'] = 'normal'
            await normal_welcome(update)
            await update.message.reply_text("Logged out!", reply_markup=get_normal_keyboard())
        elif text == "🏠 Main Menu":
            await reseller_welcome(update, None, None, None, None)
            await update.message.reply_text("Main Menu:", reply_markup=get_reseller_keyboard())
    
    else:
        if text == "🔑 Reseller Login":
            await reseller_login_prompt(update, ctx)
        elif text == "🌐 Ping Server":
            await ping_server(update, ctx)

# ==================== ADMIN FUNCTIONS ====================
async def show_all_devices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching devices...")
    
    keys = api_get("/api/admin/keys")
    if "error" in keys:
        await update.message.reply_text(f"❌ {keys['error']}")
        return
    
    devs = {k: v for k, v in keys.items() if v.get("device", "").strip()}
    if not devs:
        await update.message.reply_text("📭 No devices found.")
        return
    
    lines = [f"📱 ALL DEVICES (Total: {len(devs)})\n{'-'*30}"]
    for device_id, info in list(devs.items())[-20:]:
        owner = info.get('owner', 'admin')
        name = info.get('name', '—')
        expiry = fmt_expiry(info.get('expiry', ''))
        lines.append(f"📱 {device_id}\n   👤 {name} | {expiry} | 👑 {owner}\n")
    
    await update.message.reply_text("\n".join(lines))

async def add_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 Add Device\n\nSend Device ID:\nExample: USER001")
    return ASK_DEVICE

async def add_device_get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['new_device'] = update.message.text.strip()
    await update.message.reply_text(f"✅ Device ID: {ctx.user_data['new_device']}\n\nSend Name:")
    return ASK_NAME

async def add_device_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['new_name'] = update.message.text.strip()
    await update.message.reply_text("⏳ Select Expiry:", reply_markup=get_admin_expiry_keyboard())
    return ASK_EXPIRY

async def add_device_get_expiry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.replace("exp_", "")
    
    if choice == "life":
        expiry = ""
    else:
        expiry = expiry_from_choice(choice)
    
    result = api_post("/api/admin/key/add", {
        "key": ctx.user_data['new_device'],
        "name": ctx.user_data['new_name'],
        "expiry": expiry,
        "device": ctx.user_data['new_device'],
        "active": True
    })
    
    if result.get("ok"):
        text = f"✅ Device Added!\n\n📱 {ctx.user_data['new_device']}\n👤 {ctx.user_data['new_name']}\n⏳ {fmt_expiry(expiry)}"
    else:
        text = f"❌ Failed: {result.get('msg', 'Error')}"
    
    await query.edit_message_text(text)
    return ConversationHandler.END

async def delete_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑️ Delete Device\n\nSend Device ID:")
    return ASK_DEL_DEVICE

async def delete_device_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    device_id = update.message.text.strip()
    
    keys = api_get("/api/admin/keys")
    if device_id in keys:
        result = api_post("/api/admin/key/delete", {"key": device_id})
        
        if result.get("ok"):
            await update.message.reply_text(f"✅ Deleted {device_id}")
        else:
            await update.message.reply_text(f"❌ Failed: {result.get('msg', 'Error')}")
    else:
        await update.message.reply_text(f"❌ Device {device_id} not found!")
    
    return ConversationHandler.END

async def show_resellers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching resellers...")
    
    res = api_get("/api/admin/resellers")
    if "error" in res:
        await update.message.reply_text(f"❌ {res['error']}")
        return
    if not res:
        await update.message.reply_text("📭 No resellers.")
        return
    
    lines = ["👥 RESELLERS\n" + "-"*30]
    for rid, info in res.items():
        status = "✅" if info.get("active") else "❌"
        tokens = info.get('tokens', 0)
        used = info.get('used_tokens', 0)
        if tokens == -1:
            token_display = "♾️ Unlimited"
        else:
            token_display = f"{tokens} tokens ({tokens - used} left)"
        lines.append(f"{status} {rid}\n👤 {info.get('name','—')}\n🎫 {token_display}\n🔑 Token: {info.get('token','N/A')}\n")
    
    await update.message.reply_text("\n".join(lines))

# ==================== ADD RESELLER ====================
async def add_reseller_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Add Reseller\n\nSend Reseller Name:\nExample: John Doe")
    return ASK_RESELLER_NAME

async def add_reseller_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['res_name'] = update.message.text.strip()
    await update.message.reply_text(f"✅ Name: {ctx.user_data['res_name']}\n\nSend Telegram User ID:\nExample: 123456789")
    return ASK_RESELLER_TELEGRAM_ID

async def add_reseller_get_telegram_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Send valid Telegram User ID (numbers only)!")
        return ASK_RESELLER_TELEGRAM_ID
    
    ctx.user_data['res_telegram_id'] = telegram_id
    ctx.user_data['res_id'] = f"RES{telegram_id}"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Limited Tokens", callback_data="token_number"), 
         InlineKeyboardButton("♾️ Unlimited Tokens", callback_data="token_unlimited")]
    ])
    
    await update.message.reply_text(
        f"✅ Name: {ctx.user_data['res_name']}\n📱 TG ID: {telegram_id}\n🆔 Auto ID: RES{telegram_id}\n\nSelect Token Type:",
        reply_markup=kb
    )
    return ASK_RESELLER_TOKENS

async def add_reseller_token_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "token_number":
        await query.edit_message_text("🔢 Enter Token Amount\n\nSend number (e.g., 10, 50, 100):\nNote: 1 token = 1 device")
        return ASK_RESELLER_TOKENS
    else:
        token = generate_reseller_token()
        
        result = api_post("/api/admin/reseller/add", {
            "reseller_id": ctx.user_data['res_id'],
            "name": ctx.user_data['res_name'],
            "telegram_id": ctx.user_data['res_telegram_id'],
            "tokens": -1,
            "token": token,
            "active": True
        })
        
        if result.get("ok"):
            text = f"""✅ Reseller Added! (UNLIMITED)

━━━━━━━━━━━━━━━
ID: {ctx.user_data['res_id']}
Name: {ctx.user_data['res_name']}
Telegram ID: {ctx.user_data['res_telegram_id']}
Tokens: ♾️ Unlimited

━━━━━━━━━━━━━━━
LOGIN TOKEN: 
{token}

━━━━━━━━━━━━━━━
⚠️ Share this token with reseller!"""
        else:
            text = f"❌ Failed: {result.get('msg', 'Unknown error')}"
        
        await query.edit_message_text(text)
        return ConversationHandler.END

async def add_reseller_get_tokens(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        tokens = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Send valid number!")
        return ASK_RESELLER_TOKENS
    
    token = generate_reseller_token()
    
    result = api_post("/api/admin/reseller/add", {
        "reseller_id": ctx.user_data['res_id'],
        "name": ctx.user_data['res_name'],
        "telegram_id": ctx.user_data['res_telegram_id'],
        "tokens": tokens,
        "token": token,
        "active": True
    })
    
    if result.get("ok"):
        text = f"""✅ Reseller Added! (LIMITED)

━━━━━━━━━━━━━━━
ID: {ctx.user_data['res_id']}
Name: {ctx.user_data['res_name']}
Telegram ID: {ctx.user_data['res_telegram_id']}
Tokens: {tokens} tokens

━━━━━━━━━━━━━━━
LOGIN TOKEN: 
{token}

━━━━━━━━━━━━━━━
⚠️ Share this token with reseller!"""
    else:
        text = f"❌ Failed: {result.get('msg', 'Unknown error')}"
    
    await update.message.reply_text(text)
    return ConversationHandler.END

async def delete_reseller_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑️ Delete Reseller\n\nSend Reseller ID:")
    return ASK_DEL_RESELLER

async def delete_reseller_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reseller_id = update.message.text.strip().upper()
    
    result = api_post("/api/admin/reseller/delete", {"reseller_id": reseller_id})
    
    if result.get("ok"):
        await update.message.reply_text(f"✅ Deleted reseller {reseller_id}!")
    else:
        await update.message.reply_text(f"❌ Failed: {result.get('msg', 'Error')}")
    
    return ConversationHandler.END

async def add_tokens_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 Add Tokens\n\nSend Reseller ID:")
    return ASK_ADD_TOKENS_RID

async def add_tokens_get_rid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['token_rid'] = update.message.text.strip().upper()
    await update.message.reply_text(f"✅ Reseller: {ctx.user_data['token_rid']}\n\nHow many tokens to add?")
    return ASK_ADD_TOKENS_AMOUNT

async def add_tokens_get_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Send valid number!")
        return ASK_ADD_TOKENS_AMOUNT
    
    result = api_post("/api/admin/reseller/tokens", {
        "reseller_id": ctx.user_data['token_rid'],
        "amount": amount
    })
    
    if result.get("ok"):
        await update.message.reply_text(f"✅ Added {amount} tokens to {ctx.user_data['token_rid']}!")
    else:
        await update.message.reply_text(f"❌ {result.get('msg', 'Error')}")
    
    return ConversationHandler.END

async def show_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keys = api_get("/api/admin/keys")
    if "error" in keys:
        await update.message.reply_text(f"❌ {keys['error']}")
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    total = len(keys)
    active = sum(1 for v in keys.values() if v.get("active") and (not v.get("expiry") or v["expiry"] >= today))
    expired = sum(1 for v in keys.values() if v.get("expiry") and v["expiry"] < today)
    lifetime = sum(1 for v in keys.values() if not v.get("expiry"))
    
    text = f"""📊 STATS
━━━━━━━━━━━━━━━
🔑 Total Devices: {total}
✅ Active: {active}
⏰ Expired: {expired}
♾️ Lifetime: {lifetime}"""
    
    await update.message.reply_text(text)

# ==================== RESELLER LOGIN ====================
async def reseller_login_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔑 Reseller Login\n\nSend your Token:")
    return ASK_RESELLER_TOKEN

async def reseller_login_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip().upper()
    
    await update.message.reply_text("🔄 Verifying...")
    
    res = api_get("/api/admin/resellers")
    
    if "error" in res:
        await update.message.reply_text(f"❌ Server Error: {res['error']}")
        return ConversationHandler.END
    
    for rid, data in res.items():
        if data.get('token') == token and data.get('active'):
            ctx.user_data['reseller_token'] = token
            ctx.user_data['reseller_id'] = rid
            ctx.user_data['reseller_name'] = data.get('name')
            ctx.user_data['role'] = 'reseller'
            
            tokens = data.get('tokens', 0)
            used = data.get('used_tokens', 0)
            
            if tokens == -1:
                token_display = "♾️ Unlimited"
                remaining = "No limit"
            else:
                token_display = f"{tokens} total"
                remaining = f"{tokens - used} tokens left"
            
            # Get device count
            headers = {"X-Reseller-Token": token}
            keys = api_get("/api/reseller/keys", headers=headers)
            device_count = len(keys) if isinstance(keys, dict) else 0
            
            await update.message.reply_text(
                f"✅ Login Successful!\n\n👤 Name: {data.get('name')}\n🆔 ID: {rid}\n💰 Balance: {token_display}\n💎 Remaining: {remaining}\n📱 Your Devices: {device_count}\n\n⚠️ Lifetime keys NOT allowed!",
                reply_markup=get_reseller_keyboard()
            )
            return ConversationHandler.END
    
    await update.message.reply_text("❌ Invalid Token!")
    return ConversationHandler.END

# ==================== RESELLER FUNCTIONS ====================
async def reseller_my_devices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token = ctx.user_data.get('reseller_token')
    if not token:
        await update.message.reply_text("❌ Login first!")
        return
    
    headers = {"X-Reseller-Token": token}
    keys = api_get("/api/reseller/keys", headers=headers)
    
    if "error" in keys:
        await update.message.reply_text(f"❌ {keys['error']}")
        return
    if not keys:
        await update.message.reply_text("📭 No devices found. Use 'Add Device' to create one!")
        return
    
    lines = [f"📱 MY DEVICES (Total: {len(keys)})\n{'-'*30}"]
    for device_id, info in list(keys.items())[-20:]:
        name = info.get('name', '—')
        expiry = fmt_expiry(info.get('expiry', ''))
        lines.append(f"📱 {device_id}\n   👤 {name} | {expiry}\n")
    
    await update.message.reply_text("\n".join(lines))

async def reseller_add_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("➕ Add Device\n\nSend Device ID:\nExample: USER001\n\n⚠️ Lifetime keys NOT allowed!")
    return ASK_RESELLER_DEVICE

async def reseller_add_device_get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['res_new_device'] = update.message.text.strip()
    await update.message.reply_text(f"✅ Device ID: {ctx.user_data['res_new_device']}\n\nSend Name:")
    return ASK_RESELLER_DEVICE_NAME

async def reseller_add_device_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['res_new_name'] = update.message.text.strip()
    await update.message.reply_text("⏳ Select Expiry (No Lifetime):", reply_markup=get_reseller_expiry_keyboard())
    return ASK_RESELLER_DEVICE_EXPIRY

async def reseller_add_device_get_expiry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.replace("exp_", "")
    
    cost = get_token_cost(choice)
    expiry = expiry_from_choice(choice)
    
    token = ctx.user_data.get('reseller_token')
    headers = {"X-Reseller-Token": token}
    
    await query.edit_message_text(f"🔄 Checking balance...\n\nCost: {cost} tokens")
    
    stats = api_get("/api/reseller/stats", headers=headers)
    
    if "error" in stats:
        await query.edit_message_text(f"❌ {stats['error']}")
        return ConversationHandler.END
    
    tokens_left = stats.get('tokens_left', 0)
    
    if tokens_left != -1 and tokens_left < cost:
        await query.edit_message_text(
            f"❌ Insufficient Balance!\n\nRequired: {cost} tokens\nAvailable: {tokens_left} tokens\n\nContact admin to add more tokens."
        )
        return ConversationHandler.END
    
    result = api_post("/api/reseller/key/add", {
        "key": ctx.user_data['res_new_device'],
        "name": ctx.user_data['res_new_name'],
        "expiry": expiry,
        "token_cost": cost
    }, headers=headers)
    
    if result.get("ok"):
        remaining = result.get('tokens_left', '?')
        if remaining == -1:
            remaining_display = "Unlimited"
        else:
            remaining_display = f"{remaining} tokens"
        
        text = f"✅ Device Added!\n\n📱 {ctx.user_data['res_new_device']}\n👤 {ctx.user_data['res_new_name']}\n⏳ {fmt_expiry(expiry)}\n💰 Cost: {cost} tokens\n🎫 Left: {remaining_display}"
    else:
        text = f"❌ Failed: {result.get('msg', 'Error')}"
    
    await query.edit_message_text(text)
    return ConversationHandler.END

async def reseller_delete_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑️ Delete Device\n\nSend Device ID:")
    return ASK_RESELLER_DEL_DEVICE

async def reseller_delete_device_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    device_id = update.message.text.strip()
    token = ctx.user_data.get('reseller_token')
    headers = {"X-Reseller-Token": token}
    
    result = api_post("/api/reseller/key/delete", {"key": device_id}, headers=headers)
    
    if result.get("ok"):
        await update.message.reply_text(f"✅ Deleted {device_id}")
    else:
        await update.message.reply_text(f"❌ {result.get('msg', 'Error')}")
    
    return ConversationHandler.END

async def reseller_check_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Check Device\n\nSend Device ID:")
    return ASK_RESELLER_CHECK_DEVICE

async def reseller_check_device_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    device_id = update.message.text.strip()
    token = ctx.user_data.get('reseller_token')
    headers = {"X-Reseller-Token": token}
    
    # Check if device belongs to this reseller
    keys = api_get("/api/reseller/keys", headers=headers)
    
    if device_id in keys:
        info = keys[device_id]
        name = info.get('name', '—')
        expiry = fmt_expiry(info.get('expiry', ''))
        active = "✅ Active" if info.get('active') else "❌ Inactive"
        
        text = f"🔍 Device Info\n{'-'*20}\n📱 {device_id}\n👤 Name: {name}\n⏳ {expiry}\n📊 Status: {active}"
    else:
        text = f"❌ Device {device_id} not found in your devices!"
    
    await update.message.reply_text(text)
    return ConversationHandler.END

async def reseller_my_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token = ctx.user_data.get('reseller_token')
    if not token:
        await update.message.reply_text("❌ Login first!")
        return
    
    headers = {"X-Reseller-Token": token}
    stats = api_get("/api/reseller/stats", headers=headers)
    
    if "error" in stats:
        await update.message.reply_text(f"❌ {stats['error']}")
        return
    
    name = stats.get('name', '—')
    reseller_id = stats.get('reseller_id', '—')
    tokens_left = stats.get('tokens_left', 0)
    total_used = stats.get('total_used', 0)
    total_tokens = stats.get('total_tokens', 0)
    
    if tokens_left == -1:
        balance_display = "♾️ Unlimited"
        type_display = "UNLIMITED"
        used_display = f"{total_used} devices created"
    else:
        balance_display = f"{tokens_left} tokens"
        type_display = "LIMITED"
        used_display = f"{total_used} tokens used out of {total_tokens}"
    
    text = f"""💰 MY BALANCE
━━━━━━━━━━━━━━━
👤 Name: {name}
🆔 ID: {reseller_id}
📊 Type: {type_display}
🎫 Available: {balance_display}
📈 Used: {used_display}"""
    
    await update.message.reply_text(text)

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled!")
    return ConversationHandler.END

# ==================== MAIN ====================
def main():
    # Start Flask server for port binding
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"✅ Flask server started on port {os.environ.get('PORT', 8080)}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Admin conversation handlers
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^➕ Add Device$"), add_device_start)],
        states={
            ASK_DEVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_device_get_id)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_device_get_name)],
            ASK_EXPIRY: [CallbackQueryHandler(add_device_get_expiry, pattern="^exp_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🗑️ Delete Device$"), delete_device_start)],
        states={ASK_DEL_DEVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_device_confirm)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^➕ Add Reseller$"), add_reseller_start)],
        states={
            ASK_RESELLER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reseller_get_name)],
            ASK_RESELLER_TELEGRAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reseller_get_telegram_id)],
            ASK_RESELLER_TOKENS: [CallbackQueryHandler(add_reseller_token_choice, pattern="^token_"), MessageHandler(filters.TEXT & ~filters.COMMAND, add_reseller_get_tokens)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🗑️ Delete Reseller$"), delete_reseller_start)],
        states={ASK_DEL_RESELLER: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_reseller_confirm)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^💰 Add Tokens$"), add_tokens_start)],
        states={
            ASK_ADD_TOKENS_RID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tokens_get_rid)],
            ASK_ADD_TOKENS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tokens_get_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    # Reseller conversation handlers
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🔑 Reseller Login$"), reseller_login_prompt)],
        states={ASK_RESELLER_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_login_verify)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^➕ Add Device$"), reseller_add_device_start)],
        states={
            ASK_RESELLER_DEVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_add_device_get_id)],
            ASK_RESELLER_DEVICE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_add_device_get_name)],
            ASK_RESELLER_DEVICE_EXPIRY: [CallbackQueryHandler(reseller_add_device_get_expiry, pattern="^exp_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🗑️ Delete Device$"), reseller_delete_device_start)],
        states={ASK_RESELLER_DEL_DEVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_delete_device_confirm)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🔍 Check Device$"), reseller_check_device_start)],
        states={ASK_RESELLER_CHECK_DEVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_check_device_confirm)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    # Message and command handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    
    print("🚀 POSCUS Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()