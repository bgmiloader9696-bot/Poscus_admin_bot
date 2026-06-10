#!/usr/bin/env python3
# POSCUS PREDICTER - FINAL COMPLETE BOT (Admin Real Ping, Others Fake)

import requests
import json
import time
import logging
import random
import warnings
import os
from datetime import datetime, timedelta
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=UserWarning, module="telegram")
warnings.filterwarnings("ignore", category=PTBUserWarning)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.ERROR)

# ==============================================
# CONFIG - Use environment variables
# ==============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8992304126:AAGups0z9tf4Hl1lTCHtj7X8qqMlwjT9o64")
SERVER_URL = os.environ.get("SERVER_URL", "https://poscus-predicter.onrender.com")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "VC5SA9AT0H2010")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "6548871396").split(",")]
# ==============================================

HEADERS_ADMIN = {"Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN}

# Conversation states
ASK_DEVICE, ASK_NAME, ASK_EXPIRY = range(3)
ASK_DEL_KEY = 10
ASK_RESELLER_ID, ASK_RESELLER_NAME, ASK_RESELLER_TOKENS = range(20, 23)
ASK_RESELLER_TOKEN = 30
ASK_RESELLER_ADD_KEY, ASK_RESELLER_ADD_NAME, ASK_RESELLER_ADD_EXPIRY = range(31, 34)
ASK_RESELLER_DEL_KEY = 40
ASK_RESELLER_CHECK_KEY = 50
ASK_ADD_TOKENS_RID, ASK_ADD_TOKENS_AMOUNT = range(60, 62)

def is_admin(uid): 
    return uid in ADMIN_IDS

def api_get(path, headers=None):
    try:
        r = requests.get(SERVER_URL + path, headers=headers or HEADERS_ADMIN, timeout=30)
        return r.json()
    except:
        return {"error": "Connection failed"}

def api_post(path, data, headers=None):
    try:
        r = requests.post(SERVER_URL + path, headers=headers or HEADERS_ADMIN, json=data, timeout=30)
        return r.json()
    except:
        return {"error": "Connection failed"}

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
    if not exp: 
        return "♾️ Lifetime"
    today = datetime.now().strftime("%Y-%m-%d")
    if exp < today: 
        return f"⏰ Expired"
    diff = (datetime.strptime(exp, "%Y-%m-%d") - datetime.now()).days
    if diff <= 3: 
        return f"⚠️ {diff}d left"
    return f"✅ {exp}"

# ==================== PING FUNCTION ====================
async def ping_server(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # Check if user is admin
    if is_admin(uid):
        # REAL PING FOR ADMIN
        s = time.time()
        try:
            r = requests.get(SERVER_URL + "/api/ping", timeout=10)
            ms = int((time.time() - s) * 1000)
            
            if r.status_code == 200:
                status = "🟢 Online"
            else:
                status = "🟡 Partial"
            
            text = f"🏓 *Pong! (Real)*\n\n• Server URL: `{SERVER_URL}`\n• Response Time: `{ms}ms`\n• Server Status: `{status}`"
        except:
            ms = int((time.time() - s) * 1000)
            text = f"🏓 *Pong! (Real)*\n\n• Server URL: `{SERVER_URL}`\n• Response Time: `{ms}ms`\n• Server Status: `🔴 Offline`"
    else:
        # FAKE PING FOR NORMAL USER & RESELLER (20-30ms)
        fake_ping = random.randint(20, 30)
        
        # Still check if server is actually online for status
        try:
            r = requests.get(SERVER_URL + "/api/ping", timeout=5)
            if r.status_code == 200:
                status = "🟢 Online"
            else:
                status = "🟡 Partial"
        except:
            status = "🔴 Offline"
        
        text = f"🏓 *Pong!*\n\n• Server URL: `{SERVER_URL}`\n• Response Time: `{fake_ping}ms`\n• Server Status: `{status}`"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ==================== MARKOV KEYBOARDS ====================
def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 All Keys", "📱 Devices"],
        ["➕ Add Device", "🗑️ Delete Key"],
        ["👥 Resellers", "➕ Add Reseller"],
        ["💰 Add Tokens", "📊 Stats"],
        ["🌐 Ping Server", "🔑 Reseller Mode"],
        ["📋 My Keys", "🏠 Main Menu"]
    ], resize_keyboard=True)

def get_reseller_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 My Keys", "➕ Add Key"],
        ["🗑️ Delete Key", "🔍 Check Key"],
        ["📊 My Stats", "🚪 Logout"],
        ["🌐 Ping Server", "🏠 Main Menu"]
    ], resize_keyboard=True)

def get_normal_keyboard():
    return ReplyKeyboardMarkup([
        ["🔑 Reseller Login"],
        ["🌐 Ping Server"]
    ], resize_keyboard=True)

# Reseller Expiry Keyboard - NO LIFETIME OPTION
def get_reseller_expiry_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1H (1 token)", callback_data="exp_1h"), InlineKeyboardButton("2H (2 token)", callback_data="exp_2h"), InlineKeyboardButton("3H (3 token)", callback_data="exp_3h")],
        [InlineKeyboardButton("4H (4 token)", callback_data="exp_4h"), InlineKeyboardButton("5H (5 token)", callback_data="exp_5h"), InlineKeyboardButton("6H (6 token)", callback_data="exp_6h")],
        [InlineKeyboardButton("12H (10 token)", callback_data="exp_12h"), InlineKeyboardButton("1D (15 token)", callback_data="exp_1d"), InlineKeyboardButton("3D (25 token)", callback_data="exp_3d")],
        [InlineKeyboardButton("7D (40 token)", callback_data="exp_7d"), InlineKeyboardButton("15D (60 token)", callback_data="exp_15d"), InlineKeyboardButton("30D (100 token)", callback_data="exp_30d")],
        [InlineKeyboardButton("60D (150 token)", callback_data="exp_60d")]
    ])

# Admin Expiry Keyboard - HAS LIFETIME OPTION
def get_admin_expiry_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1H (1 token)", callback_data="exp_1h"), InlineKeyboardButton("2H (2 token)", callback_data="exp_2h"), InlineKeyboardButton("3H (3 token)", callback_data="exp_3h")],
        [InlineKeyboardButton("4H (4 token)", callback_data="exp_4h"), InlineKeyboardButton("5H (5 token)", callback_data="exp_5h"), InlineKeyboardButton("6H (6 token)", callback_data="exp_6h")],
        [InlineKeyboardButton("12H (10 token)", callback_data="exp_12h"), InlineKeyboardButton("1D (15 token)", callback_data="exp_1d"), InlineKeyboardButton("3D (25 token)", callback_data="exp_3d")],
        [InlineKeyboardButton("7D (40 token)", callback_data="exp_7d"), InlineKeyboardButton("15D (60 token)", callback_data="exp_15d"), InlineKeyboardButton("30D (100 token)", callback_data="exp_30d")],
        [InlineKeyboardButton("60D (150 token)", callback_data="exp_60d"), InlineKeyboardButton("♾️ Lifetime", callback_data="exp_life")]
    ])

# ==================== START ====================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if is_admin(uid):
        ctx.user_data['role'] = 'admin'
        await update.message.reply_text(
            "🔮 *POSCUS PREDICTER BOT*\n━━━━━━━━━━━━━━━\n👑 *Admin Panel Ready!*",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
    elif ctx.user_data.get('reseller_token'):
        ctx.user_data['role'] = 'reseller'
        await update.message.reply_text(
            "🔮 *POSCUS PREDICTER BOT*\n━━━━━━━━━━━━━━━\n🤝 *Reseller Panel Ready!*\n\n⚠️ *Note:* Lifetime keys are NOT allowed for resellers!",
            parse_mode="Markdown",
            reply_markup=get_reseller_keyboard()
        )
    else:
        ctx.user_data['role'] = 'normal'
        await update.message.reply_text(
            "🔮 *POSCUS PREDICTER BOT*\n━━━━━━━━━━━━━━━\n🤝 *Welcome!*",
            parse_mode="Markdown",
            reply_markup=get_normal_keyboard()
        )

# ==================== TEXT HANDLER ====================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    
    if is_admin(uid) or ctx.user_data.get('role') == 'admin':
        if text == "📋 All Keys":
            await show_all_keys(update, ctx)
        elif text == "📱 Devices":
            await show_all_devices(update, ctx)
        elif text == "➕ Add Device":
            await add_device_start(update, ctx)
        elif text == "🗑️ Delete Key":
            await delete_key_start(update, ctx)
        elif text == "👥 Resellers":
            await show_resellers(update, ctx)
        elif text == "➕ Add Reseller":
            await add_reseller_start(update, ctx)
        elif text == "💰 Add Tokens":
            await add_tokens_start(update, ctx)
        elif text == "📊 Stats":
            await show_stats(update, ctx)
        elif text == "🌐 Ping Server":
            await ping_server(update, ctx)
        elif text == "🔑 Reseller Mode":
            await reseller_login_prompt(update, ctx)
        elif text == "📋 My Keys":
            await reseller_my_keys(update, ctx)
        elif text == "🏠 Main Menu":
            await update.message.reply_text("🏠 *Main Menu*", parse_mode="Markdown", reply_markup=get_admin_keyboard())
    
    elif ctx.user_data.get('reseller_token'):
        if text == "📋 My Keys":
            await reseller_my_keys(update, ctx)
        elif text == "➕ Add Key":
            await reseller_add_key_start(update, ctx)
        elif text == "🗑️ Delete Key":
            await reseller_delete_key_start(update, ctx)
        elif text == "🔍 Check Key":
            await reseller_check_key_start(update, ctx)
        elif text == "📊 My Stats":
            await reseller_my_stats(update, ctx)
        elif text == "🌐 Ping Server":
            await ping_server(update, ctx)
        elif text == "🚪 Logout":
            ctx.user_data.pop('reseller_token', None)
            ctx.user_data.pop('reseller_id', None)
            ctx.user_data['role'] = 'normal'
            await update.message.reply_text("✅ *Logged out!*", parse_mode="Markdown", reply_markup=get_normal_keyboard())
        elif text == "🏠 Main Menu":
            await update.message.reply_text("🏠 *Main Menu*", parse_mode="Markdown", reply_markup=get_reseller_keyboard())
    
    else:
        if text == "🔑 Reseller Login":
            await reseller_login_prompt(update, ctx)
        elif text == "🌐 Ping Server":
            await ping_server(update, ctx)

# ==================== ADMIN FUNCTIONS ====================
async def show_all_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keys = api_get("/api/admin/keys")
    if "error" in keys:
        await update.message.reply_text(f"❌ {keys['error']}")
        return
    if not keys:
        await update.message.reply_text("📭 No keys found.")
        return
    
    lines = [f"📋 *ALL KEYS* (Total: {len(keys)})\n━━━━━━━━━━━━━━━"]
    for k, v in list(keys.items())[-20:]:
        status = "✅" if v.get("active") else "❌"
        exp = fmt_expiry(v.get("expiry", ""))
        owner = v.get('owner', 'admin')
        lines.append(f"{status} `{k}` | 👤 {v.get('name','—')} | {exp} | 👑 {owner}")
    
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

async def show_all_devices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keys = api_get("/api/admin/keys")
    if "error" in keys:
        await update.message.reply_text(f"❌ {keys['error']}")
        return
    devs = {k: v for k, v in keys.items() if v.get("device", "").strip()}
    if not devs:
        await update.message.reply_text("📭 No devices bound.")
        return
    
    lines = [f"📱 *DEVICES* (Total: {len(devs)})\n━━━━━━━━━━━━━━━"]
    for k, v in list(devs.items())[-20:]:
        lines.append(f"📱 `{v['device']}` | 👤 {v.get('name','—')} | {fmt_expiry(v.get('expiry',''))}")
    
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

async def add_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 *Add Device*\n\nSend Device ID:\n_Example: USER001_", parse_mode="Markdown")
    return ASK_DEVICE

async def add_device_get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['new_device'] = update.message.text.strip().upper()
    await update.message.reply_text(f"✅ Device: `{ctx.user_data['new_device']}`\n\nSend Name:", parse_mode="Markdown")
    return ASK_NAME

async def add_device_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['new_name'] = update.message.text.strip()
    await update.message.reply_text("⏳ *Select Expiry:*", parse_mode="Markdown", reply_markup=get_admin_expiry_keyboard())
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
        text = f"✅ *Added!*\n📱 `{ctx.user_data['new_device']}`\n👤 {ctx.user_data['new_name']}\n⏳ {fmt_expiry(expiry)}"
    else:
        text = f"❌ Failed: {result.get('msg', 'Error')}"
    
    await query.edit_message_text(text, parse_mode="Markdown")
    return ConversationHandler.END

async def delete_key_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑️ *Delete Key*\n\nSend Key ID to delete:", parse_mode="Markdown")
    return ASK_DEL_KEY

async def delete_key_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    
    keys = api_get("/api/admin/keys")
    if key in keys:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = api_post("/api/admin/key/update", {"key": key, "expiry": yesterday, "active": False})
        
        if result.get("ok"):
            await update.message.reply_text(f"✅ Key `{key}` has been expired/deleted!", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Failed: {result.get('msg', 'Error')}")
    else:
        await update.message.reply_text(f"❌ Key `{key}` not found!", parse_mode="Markdown")
    
    return ConversationHandler.END

async def show_resellers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    res = api_get("/api/admin/resellers")
    if "error" in res:
        await update.message.reply_text(f"❌ {res['error']}")
        return
    if not res:
        await update.message.reply_text("📭 No resellers.")
        return
    
    lines = ["👥 *RESELLERS*\n━━━━━━━━━━━━━━━"]
    for rid, v in res.items():
        status = "✅" if v.get("active") else "❌"
        tokens = v.get('tokens', 0)
        token_display = "♾️ Unlimited" if tokens == -1 else tokens
        lines.append(f"{status} `{rid}`\n👤 {v.get('name','—')}\n🎫 Tokens: {token_display}\n🔑 `{v.get('token','')}`")
    
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

async def add_reseller_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 *Add Reseller*\n\nSend *Reseller ID*:\n_Example: RESELLER1_", parse_mode="Markdown")
    return ASK_RESELLER_ID

async def add_reseller_get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['res_id'] = update.message.text.strip().upper()
    await update.message.reply_text(f"✅ ID: `{ctx.user_data['res_id']}`\n\nSend *Name*:", parse_mode="Markdown")
    return ASK_RESELLER_NAME

async def add_reseller_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['res_name'] = update.message.text.strip()
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Enter Number", callback_data="token_number"), InlineKeyboardButton("♾️ Unlimited", callback_data="token_unlimited")]
    ])
    
    await update.message.reply_text(
        f"✅ Reseller: `{ctx.user_data['res_id']}`\n👤 Name: `{ctx.user_data['res_name']}`\n\n*How many tokens?*\n\n📌 Number → Enter specific number\n📌 Unlimited → No limit",
        parse_mode="Markdown",
        reply_markup=kb
    )
    return ASK_RESELLER_TOKENS

async def add_reseller_token_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "token_number":
        await query.edit_message_text("🔢 *Enter Token Amount*\n\nSend a number (e.g., `10`, `50`, `100`):\n*Note:* 1 token = 1 key", parse_mode="Markdown")
        return ASK_RESELLER_TOKENS
    else:
        result = api_post("/api/admin/reseller/add", {
            "reseller_id": ctx.user_data['res_id'],
            "name": ctx.user_data['res_name'],
            "tokens": -1
        })
        
        if result.get("ok"):
            text = f"✅ *Reseller Added!*\n\n🆔 ID: `{ctx.user_data['res_id']}`\n👤 Name: `{ctx.user_data['res_name']}`\n🎫 Tokens: `♾️ Unlimited`\n🔑 Token: `{result.get('token', '')}`"
        else:
            text = f"❌ Failed: {result.get('msg', 'Error')}"
        
        await query.edit_message_text(text, parse_mode="Markdown")
        return ConversationHandler.END

async def add_reseller_get_tokens(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token_text = update.message.text.strip()
    
    if token_text.lower() == "unlimited":
        tokens = -1
    else:
        try:
            tokens = int(token_text)
        except:
            await update.message.reply_text("❌ Send a valid number or 'unlimited'!")
            return ASK_RESELLER_TOKENS
    
    result = api_post("/api/admin/reseller/add", {
        "reseller_id": ctx.user_data['res_id'],
        "name": ctx.user_data['res_name'],
        "tokens": tokens
    })
    
    if result.get("ok"):
        token_display = "♾️ Unlimited" if tokens == -1 else tokens
        text = f"✅ *Reseller Added!*\n\n🆔 ID: `{ctx.user_data['res_id']}`\n👤 Name: `{ctx.user_data['res_name']}`\n🎫 Tokens: `{token_display}`\n🔑 Token: `{result.get('token', '')}`"
    else:
        text = f"❌ Failed: {result.get('msg', 'Error')}"
    
    await update.message.reply_text(text, parse_mode="Markdown")
    return ConversationHandler.END

async def add_tokens_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 *Add Tokens*\n\nSend Reseller ID:", parse_mode="Markdown")
    return ASK_ADD_TOKENS_RID

async def add_tokens_get_rid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['token_rid'] = update.message.text.strip().upper()
    await update.message.reply_text(f"✅ Reseller: `{ctx.user_data['token_rid']}`\n\nHow many tokens to add?", parse_mode="Markdown")
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
        await update.message.reply_text(f"✅ Added `{amount}` tokens to `{ctx.user_data['token_rid']}`!", parse_mode="Markdown")
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
    devices = sum(1 for v in keys.values() if v.get("device", "").strip())
    
    text = f"📊 *STATS*\n━━━━━━━━━━━━━━━\n🔑 Total: `{total}`\n✅ Active: `{active}`\n⏰ Expired: `{expired}`\n📱 Devices: `{devices}`"
    await update.message.reply_text(text, parse_mode="Markdown")

# ==================== RESELLER FUNCTIONS ====================
async def reseller_login_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔑 *Reseller Login*\n\nSend your Token:", parse_mode="Markdown")
    return ASK_RESELLER_TOKEN

async def reseller_login_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    res = api_get("/api/admin/resellers")
    
    if "error" in res:
        await update.message.reply_text("❌ Server error!")
        return ConversationHandler.END
    
    for rid, data in res.items():
        if data.get('token') == token and data.get('active'):
            ctx.user_data['reseller_token'] = token
            ctx.user_data['reseller_id'] = rid
            ctx.user_data['reseller_name'] = data.get('name')
            ctx.user_data['role'] = 'reseller'
            
            tokens = data.get('tokens', 0)
            used = data.get('used_tokens', 0)
            tokens_left = "♾️ Unlimited" if tokens == -1 else tokens - used
            
            await update.message.reply_text(
                f"✅ *Logged in!*\n👤 {data.get('name')}\n🆔 {rid}\n🎫 Tokens: `{tokens_left}`\n\nUse buttons below.\n⚠️ *Note:* Lifetime keys NOT allowed!",
                parse_mode="Markdown",
                reply_markup=get_reseller_keyboard()
            )
            return ConversationHandler.END
    
    await update.message.reply_text("❌ *Invalid Token!*", parse_mode="Markdown")
    return ConversationHandler.END

async def reseller_my_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("📭 No keys found.")
        return
    
    lines = [f"📋 *MY KEYS* (Total: {len(keys)})\n━━━━━━━━━━━━━━━"]
    for k, v in list(keys.items())[-20:]:
        lines.append(f"🔑 `{k}` | 👤 {v.get('name','—')} | {fmt_expiry(v.get('expiry',''))}")
    
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

async def reseller_add_key_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("➕ *Add Key*\n\nSend Key ID:\n*Note:* Lifetime keys are NOT allowed!", parse_mode="Markdown")
    return ASK_RESELLER_ADD_KEY

async def reseller_add_key_get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['res_new_key'] = update.message.text.strip().upper()
    await update.message.reply_text(f"✅ Key: `{ctx.user_data['res_new_key']}`\n\nSend Name:", parse_mode="Markdown")
    return ASK_RESELLER_ADD_NAME

async def reseller_add_key_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['res_new_name'] = update.message.text.strip()
    await update.message.reply_text("⏳ *Select Expiry (No Lifetime option):*", parse_mode="Markdown", reply_markup=get_reseller_expiry_keyboard())
    return ASK_RESELLER_ADD_EXPIRY

async def reseller_add_key_get_expiry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.replace("exp_", "")
    
    # Check if choice is lifetime (should not happen but just in case)
    if choice == "life":
        await query.edit_message_text("❌ *Resellers cannot create Lifetime keys!*", parse_mode="Markdown")
        return ConversationHandler.END
    
    cost = get_token_cost(choice)
    expiry = expiry_from_choice(choice)
    
    token = ctx.user_data.get('reseller_token')
    headers = {"X-Reseller-Token": token}
    stats = api_get("/api/reseller/stats", headers=headers)
    
    tokens_left = stats.get('tokens_left', 0)
    
    if tokens_left < cost and tokens_left != -1:
        await query.edit_message_text(f"❌ *Insufficient Tokens!*\n\nRequired: `{cost}`\nYou have: `{tokens_left}`", parse_mode="Markdown")
        return ConversationHandler.END
    
    result = api_post("/api/reseller/key/add", {
        "key": ctx.user_data['res_new_key'],
        "name": ctx.user_data['res_new_name'],
        "expiry": expiry,
        "token_cost": cost
    }, headers=headers)
    
    if result.get("ok"):
        text = f"✅ *Key Added!*\n\n🔑 `{ctx.user_data['res_new_key']}`\n👤 {ctx.user_data['res_new_name']}\n⏳ {fmt_expiry(expiry)}\n💰 Cost: `{cost}` tokens\n🎫 Left: `{result.get('tokens_left', '?')}`"
    else:
        text = f"❌ {result.get('msg', 'Error')}"
    
    await query.edit_message_text(text, parse_mode="Markdown")
    return ConversationHandler.END

async def reseller_delete_key_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑️ *Delete Key*\n\nSend Key ID to delete:", parse_mode="Markdown")
    return ASK_RESELLER_DEL_KEY

async def reseller_delete_key_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    token = ctx.user_data.get('reseller_token')
    headers = {"X-Reseller-Token": token}
    
    result = api_post("/api/reseller/key/delete", {"key": key}, headers=headers)
    
    if result.get("ok"):
        await update.message.reply_text(f"✅ Deleted `{key}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ {result.get('msg', 'Error')}")
    
    return ConversationHandler.END

async def reseller_check_key_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 *Check Key*\n\nSend Key ID to check:", parse_mode="Markdown")
    return ASK_RESELLER_CHECK_KEY

async def reseller_check_key_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    keys = api_get("/api/admin/keys")
    
    if key in keys:
        v = keys[key]
        text = f"🔍 *Key Info*\n━━━━━━━━━━━━━━━\n🔑 `{key}`\n👤 {v.get('name','—')}\n⏳ {fmt_expiry(v.get('expiry',''))}\n👑 Owner: {v.get('owner', 'unknown')}"
    else:
        text = f"❌ Key `{key}` not found!"
    
    await update.message.reply_text(text, parse_mode="Markdown")
    return ConversationHandler.END

async def reseller_my_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    token = ctx.user_data.get('reseller_token')
    headers = {"X-Reseller-Token": token}
    stats = api_get("/api/reseller/stats", headers=headers)
    
    if "error" in stats:
        await update.message.reply_text(f"❌ {stats['error']}")
        return
    
    tokens_display = "♾️ Unlimited" if stats.get('tokens_left') == -1 else stats.get('tokens_left', 0)
    
    text = f"📊 *MY STATS*\n━━━━━━━━━━━━━━━\n👤 Name: {stats.get('name', '—')}\n🆔 ID: {stats.get('reseller_id', '—')}\n🎫 Tokens Left: `{tokens_display}`\n🔑 Keys Used: `{stats.get('total_used', 0)}`"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# ==================== MAIN ====================
def main():
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
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🗑️ Delete Key$"), delete_key_start)],
        states={ASK_DEL_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_key_confirm)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^➕ Add Reseller$"), add_reseller_start)],
        states={
            ASK_RESELLER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reseller_get_id)],
            ASK_RESELLER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reseller_get_name)],
            ASK_RESELLER_TOKENS: [CallbackQueryHandler(add_reseller_token_choice, pattern="^token_"), MessageHandler(filters.TEXT & ~filters.COMMAND, add_reseller_get_tokens)],
        },
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
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🔑 Reseller Mode$"), reseller_login_prompt), MessageHandler(filters.TEXT & filters.Regex("^🔑 Reseller Login$"), reseller_login_prompt)],
        states={ASK_RESELLER_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_login_verify)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^➕ Add Key$"), reseller_add_key_start)],
        states={
            ASK_RESELLER_ADD_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_add_key_get_id)],
            ASK_RESELLER_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_add_key_get_name)],
            ASK_RESELLER_ADD_EXPIRY: [CallbackQueryHandler(reseller_add_key_get_expiry, pattern="^exp_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🗑️ Delete Key$"), reseller_delete_key_start)],
        states={ASK_RESELLER_DEL_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_delete_key_confirm)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("^🔍 Check Key$"), reseller_check_key_start)],
        states={ASK_RESELLER_CHECK_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_check_key_confirm)]},
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