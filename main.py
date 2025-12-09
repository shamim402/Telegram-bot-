#!/usr/bin/env python3
# main.py — V5.0 Full Production Bot (Polling + Replit DB + Backups + Referral + ForceSub + Admin)

import os
import time
import random
import json
import threading
from datetime import datetime, timedelta

try:
    from replit import db
except Exception:
    db = None  # fallback; code will still attempt file backups

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN") or ""            # set in Replit Secrets
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)  # set in Replit Secrets
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME") or None  # optional: e.g. @yourchannel

if not TOKEN:
    raise SystemExit("Error: TOKEN not set in environment. Add in Replit Secrets.")
if not ADMIN_ID:
    raise SystemExit("Error: ADMIN_ID not set in environment. Add your numeric id in Replit Secrets.")

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# Earning links (rotate)
EARNING_LINKS = [
    "https://earningguidebd01.blogspot.com/p/earn-money-now.html?m=1",
    "https://skbd355.42web.io",
    "https://smarttechtoolsbd.blogspot.com",
    "https://otieu.com/4/10235751"
]

# Limits & settings
COOLDOWN_SECONDS = 24 * 60 * 60        # 24 hours cooldown for /earn
SPAM_WINDOW_SECONDS = 10               # small window for spam check
SPAM_MAX_REQUESTS = 3                  # max /earn attempts in window
DAILY_BONUS_POINTS = 10
REFERRAL_BONUS_POINTS = 15

DB_KEY = "v5_users"   # primary db key

# Backup settings
BACKUP_DIR = "backups"
BACKUP_INTERVAL_HOURS = 24  # create backup every 24 hours

# ---------------- Utilities: DB wrapper ----------------
def _db_exists():
    return db is not None

def _load_all_users():
    if _db_exists():
        if DB_KEY in db:
            try:
                return dict(db[DB_KEY])
            except Exception:
                return dict(db[DB_KEY])
        else:
            db[DB_KEY] = {}
            return {}
    else:
        # fallback to file
        try:
            with open("users_v5.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

def _save_all_users(users: dict):
    if _db_exists():
        db[DB_KEY] = users
    else:
        with open("users_v5.json", "w") as f:
            json.dump(users, f, indent=2)

def ensure_user(uid_int):
    users = _load_all_users()
    uid = str(uid_int)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if uid not in users:
        users[uid] = {
            "first_seen": today,
            "last_active": today,
            "requests": [],       # timestamps for spam control
            "last_earn_ts": 0,
            "points": 0,
            "referrer": None,
            "referrals": 0,
            "last_claim": "",
            "streak": 0,
            "blocked": False
        }
        _save_all_users(users)
    return users

def save_activity(uid_int):
    users = _load_all_users()
    uid = str(uid_int)
    if uid not in users:
        ensure_user(uid_int)
    users[uid]["last_active"] = datetime.utcnow().strftime("%Y-%m-%d")
    _save_all_users(users)

def record_request(uid_int):
    users = _load_all_users()
    uid = str(uid_int)
    now_ts = int(time.time())
    if uid not in users:
        ensure_user(uid_int)
    reqs = users[uid].get("requests", [])
    cutoff = now_ts - SPAM_WINDOW_SECONDS
    reqs = [t for t in reqs if t >= cutoff]
    reqs.append(now_ts)
    users[uid]["requests"] = reqs
    users[uid]["last_active"] = datetime.utcnow().strftime("%Y-%m-%d")
    _save_all_users(users)
    return len(reqs)

def can_use_earn(uid_int):
    users = _load_all_users()
    uid = str(uid_int)
    if uid not in users:
        return True, 0
    last = users[uid].get("last_earn_ts", 0)
    elapsed = int(time.time()) - int(last)
    if elapsed >= COOLDOWN_SECONDS:
        return True, 0
    return False, COOLDOWN_SECONDS - elapsed

def set_earn_ts(uid_int):
    users = _load_all_users()
    uid = str(uid_int)
    if uid not in users:
        ensure_user(uid_int)
    users[uid]["last_earn_ts"] = int(time.time())
    _save_all_users(users)

def add_points(uid_int, pts):
    users = _load_all_users()
    uid = str(uid_int)
    if uid not in users:
        ensure_user(uid_int)
    users[uid]["points"] = users[uid].get("points", 0) + int(pts)
    _save_all_users(users)

def handle_referral(new_uid_int, ref_code):
    users = _load_all_users()
    new_uid = str(new_uid_int)
    ref_uid = str(ref_code)
    if new_uid == ref_uid:
        return False
    if ref_uid in users and users[new_uid].get("referrer") is None:
        users[new_uid]["referrer"] = ref_uid
        users[ref_uid]["referrals"] = users[ref_uid].get("referrals", 0) + 1
        users[ref_uid]["points"] = users[ref_uid].get("points", 0) + REFERRAL_BONUS_POINTS
        _save_all_users(users)
        return True
    return False

def block_user(uid_int):
    users = _load_all_users()
    uid = str(uid_int)
    if uid in users:
        users[uid]["blocked"] = True
        _save_all_users(users)

def unblock_user(uid_int):
    users = _load_all_users()
    uid = str(uid_int)
    if uid in users:
        users[uid]["blocked"] = False
        _save_all_users(users)

# ---------------- Force-subscribe check (optional) ----------------
def is_subscribed(uid_int):
    if not CHANNEL_USERNAME:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, uid_int)
        return member.status in ("member", "creator", "administrator")
    except Exception:
        return False

# ---------------- Backup ----------------
def make_backup():
    users = _load_all_users()
    now = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = os.path.join(BACKUP_DIR, f"backup_{now}.json")
    with open(filename, "w") as f:
        json.dump(users, f, indent=2)
    # also save a compact latest backup in DB if available
    try:
        if _db_exists():
            db["last_backup"] = users
    except Exception:
        pass
    return filename

def _backup_worker():
    while True:
        try:
            make_backup()
        except Exception as e:
            print("Backup error:", e)
        time.sleep(BACKUP_INTERVAL_HOURS * 3600)

# start backup thread
backup_thread = threading.Thread(target=_backup_worker, daemon=True)
backup_thread.start()

# ---------------- Bot Commands ----------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    # check referral payload
    parts = message.text.strip().split()
    payload = None
    if len(parts) > 1:
        payload = parts[1]

    ensure_user(message.from_user.id)
    save_activity(message.from_user.id)

    if payload:
        try:
            handle_referral(message.from_user.id, payload)
        except Exception:
            pass

    if not is_subscribed(message.from_user.id):
        join_text = f"🔔 *Please join our channel first to use the bot*\n\nClick to join → {CHANNEL_USERNAME}"
        bot.send_message(message.chat.id, join_text, parse_mode="Markdown")
        return

    text = (
        f"👋 Hello *{message.from_user.first_name or 'Friend'}*!\n\n"
        "Welcome to the Monetag PRO Bot (V5.0).\n\n"
        "• Use /earn to get today's earning link (once per 24h).\n"
        "• Use /refer to get your invite link and earn bonus points.\n"
        "• Use /claim to claim daily bonus points.\n"
        "• Use /help for instructions."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")
    send_menu(message.chat.id)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    save_activity(message.from_user.id)
    help_text = (
        "🆘 *Help*\n\n"
        "/earn — Get your earning link (24h cooldown).\n"
        "/refer — Get your referral link.\n"
        "/claim — Claim daily bonus points.\n"
        "/stats — Admin analytics (private).\n"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['earn'])
def cmd_earn(message):
    uid = message.from_user.id
    ensure_user(uid)
    save_activity(uid)

    users = _load_all_users()
    if str(uid) in users and users[str(uid)].get("blocked", False):
        bot.send_message(message.chat.id, "❌ You are blocked.")
        return

    if not is_subscribed(uid):
        bot.send_message(message.chat.id, f"🔔 Please join our channel: {CHANNEL_USERNAME}")
        return

    recent = record_request(uid)
    if recent > SPAM_MAX_REQUESTS:
        bot.send_message(message.chat.id, "⚠️ Too many requests. Wait a bit and try again.")
        return

    allowed, remaining = can_use_earn(uid)
    if not allowed:
        hrs = remaining // 3600
        mins = (remaining % 3600) // 60
        bot.send_message(message.chat.id, f"⏳ You already used /earn. Try again after *{hrs}h {mins}m*.", parse_mode="Markdown")
        return

    final = random.choice(EARNING_LINKS)
    set_earn_ts(uid)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔗 Open Earning Link", url=final))
    kb.add(InlineKeyboardButton("📈 More Info", callback_data="more_info"))

    bot.send_message(message.chat.id, "💸 *Your earning link is ready!* Click the button below.", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    if call.data == "more_info":
        bot.answer_callback_query(call.id, "Opening details...")
        bot.send_message(call.message.chat.id, "ℹ️ Open the link and follow instructions. Contact admin for help.")
    else:
        try:
            bot.answer_callback_query(call.id)
        except:
            pass

@bot.message_handler(commands=['refer'])
def cmd_refer(message):
    uid = message.from_user.id
    ensure_user(uid)
    save_activity(uid)
    me = bot.get_me()
    bot_username = me.username
    ref_link = f"https://t.me/{bot_username}?start={uid}"
    users = _load_all_users()
    pts = users.get(str(uid), {}).get("points", 0)
    text = f"🔗 *Your referral link:*\n{ref_link}\n\nShare it — each valid referral gives *{REFERRAL_BONUS_POINTS} points*.\n\nYou have *{pts} points*."
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['claim'])
def cmd_claim(message):
    uid = message.from_user.id
    ensure_user(uid)
    save_activity(uid)
    users = _load_all_users()
    user = users.get(str(uid))
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if user.get("last_claim") == today:
        bot.send_message(message.chat.id, "❗ You already claimed today's bonus. Come back tomorrow.")
        return

    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    if user.get("last_claim") == yesterday:
        user["streak"] = user.get("streak", 0) + 1
    else:
        user["streak"] = 1

    user["last_claim"] = today
    user["points"] = user.get("points", 0) + DAILY_BONUS_POINTS
    users[str(uid)] = user
    _save_all_users(users)

    bot.send_message(message.chat.id, f"🎉 You claimed *{DAILY_BONUS_POINTS} points*! Current streak: *{user['streak']}* days.", parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if str(message.chat.type) != "private":
        return bot.send_message(message.chat.id, "📊 Run /stats in a private chat with the bot.")
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ You are not authorized to view stats.")

    users = _load_all_users()
    total = len(users)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    new_today = sum(1 for u in users.values() if u.get("first_seen") == today)
    active_24h = sum(1 for u in users.values() if u.get("last_active") in (today, yesterday))

    text = (
        f"📊 *Bot Analytics (Admin)*\n\n"
        f"👥 Total Users: *{total}*\n"
        f"🆕 New Today: *{new_today}*\n"
        f"🔥 Active (24h): *{active_24h}*\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ Admin only command.")
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "Usage:\n/broadcast Your message here")
    msg = parts[1]
    users = _load_all_users()
    count = 0
    bot.send_message(message.chat.id, f"📣 Broadcasting to {len(users)} users... (this may take some time)")
    for uid, info in users.items():
        try:
            bot.send_message(int(uid), msg, parse_mode="Markdown")
            count += 1
            time.sleep(0.08)
        except Exception:
            continue
    bot.send_message(message.chat.id, f"✅ Broadcast finished. Sent to {count} users.")

@bot.message_handler(commands=['block'])
def cmd_block(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ Admin only.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "Usage: /block <user_id>")
    try:
        uid = int(parts[1])
        block_user(uid)
        bot.send_message(message.chat.id, f"User {uid} blocked.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['unblock'])
def cmd_unblock(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ Admin only.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "Usage: /unblock <user_id>")
    try:
        uid = int(parts[1])
        unblock_user(uid)
        bot.send_message(message.chat.id, f"User {uid} unblocked.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['users'])
def cmd_users(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ Admin only.")
    users = _load_all_users()
    total = len(users)
    bot.send_message(message.chat.id, f"Total users: {total}")

# ---------------- Menu ----------------
def send_menu(chat_id):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("📘 Blog", url=EARNING_LINKS[0]),
        InlineKeyboardButton("🌐 Site", url=EARNING_LINKS[1])
    )
    kb.row(
        InlineKeyboardButton("📰 Blog2", url=EARNING_LINKS[2]),
        InlineKeyboardButton("💸 Fast Link", url=EARNING_LINKS[3])
    )
    bot.send_message(chat_id, "👇 Quick Links — click to open:", reply_markup=kb)

# ---------------- Start polling ----------------
if __name__ == "__main__":
    print("Starting V5.0 PRO bot...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("Stopping...")
    except Exception as e:
        print("Bot crashed:", e)