
import json
import telebot
from telebot import types
from datetime import datetime, timedelta
import os
import time
import random
import uuid
from threading import Thread
from flask import Flask

# ----------------- CONFIG -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

DATA_FILE = "users_v5.json"
WITHDRAW_REQUEST_FILE = "withdraws.json"

# ----------------- Helpers -----------------
def load_users():
    try:
        with open(DATA_FILE, "r") as file:
            content = file.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        # create blank
        save_users({})
        return {}

def save_users(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)

def load_withdraws():
    try:
        with open(WITHDRAW_REQUEST_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_withdraws(data):
    with open(WITHDRAW_REQUEST_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_info(message):
    return {
        "first_name": getattr(message.from_user, "first_name", None),
        "last_name": getattr(message.from_user, "last_name", None),
        "username": getattr(message.from_user, "username", None),
        "language": getattr(message.from_user, "language_code", None),
        "is_bot": getattr(message.from_user, "is_bot", False),
    }

def log_interaction(user_id, message_text, user_info):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "user_info": user_info,
            "interaction_count": 0,
            "messages": []
        }
    users[uid]["interaction_count"] += 1
    users[uid]["messages"].append({
        "message": message_text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_users(users)

def notify_admin(message, answer_text):
    if ADMIN_USER_ID:
        try:
            admin = int(ADMIN_USER_ID)
            bot.send_message(
                admin,
                f"User: @{getattr(message.from_user,'username',None)} ({message.from_user.id})\n"
                f"Message: {message.text}\n\n"
                f"Bot reply: {answer_text}"
            )
        except Exception:
            pass

# ----------------- Monetag links (your provided links) -----------------
MONETAG_LINKS = [
    "https://otieu.com/4/10235751",
    "https://otieu.com/4/10218900",
    "https://otieu.com/4/10177259"
]

# PRO settings
DAILY_BONUS_POINTS = 5
REFERRAL_BONUS_POINTS = 10
AUTO_BROADCAST_INTERVAL_MIN = 360  # default 6 hours
BROADCAST_ACTIVE_ONLY = True
MIN_WITHDRAW_POINTS = 100
WITHDRAW_CURRENCY = "USD"

# Ensure files exist
save_withdraws(load_withdraws())
save_users(load_users())

# Ensure user fields
def ensure_user_fields(users):
    changed = False
    for uid, u in users.items():
        if "points" not in u:
            u["points"] = 0; changed = True
        if "referrals" not in u:
            u["referrals"] = 0; changed = True
        if "referred_by" not in u:
            u["referred_by"] = None; changed = True
        if "last_claim" not in u:
            u["last_claim"] = None; changed = True
        if "active" not in u:
            u["active"] = True; changed = True
    if changed:
        save_users(users)

ensure_user_fields(load_users())

# ----------------- Basic Commands (start/help/profile) -----------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # referral handled in wrapper below (we also keep this as fallback)
    user_info = get_user_info(message)
    log_interaction(message.from_user.id, "Start Command Used", user_info)

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("👤 Profile"),
        types.KeyboardButton("ℹ️ Help"),
        types.KeyboardButton("⭐ Info"),
    )

    bot.send_message(
        message.chat.id,
        "🤖 *Welcome!*\n\nআমি একটি Telegram Bot.\n\nআপনি নিচের বোতাম থেকে যে কোন সেবা নিতে পারেন।",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    # ignore non-text messages
    if not hasattr(message, "text") or message.text is None:
        return
    user_info = get_user_info(message)
    log_interaction(message.from_user.id, message.text, user_info)

    if message.text == "👤 Profile":
        reply = (
            f"👤 *Your Profile*\n"
            f"Name: {message.from_user.first_name}\n"
            f"Username: @{message.from_user.username}\n"
            f"User ID: `{message.from_user.id}`"
        )
        bot.send_message(message.chat.id, reply, parse_mode="Markdown")
        notify_admin(message, reply)

    elif message.text == "ℹ️ Help":
        reply = "📘 *Help Menu*\n\nআপনার যেকোনো সমস্যার সমাধান দিতে আমি প্রস্তুত!"
        bot.send_message(message.chat.id, reply, parse_mode="Markdown")
        notify_admin(message, reply)

    elif message.text == "⭐ Info":
        reply = "⭐ This is your info panel!"
        bot.send_message(message.chat.id, reply, parse_mode="Markdown")
        notify_admin(message, reply)

    else:
        reply = "☑️ Your message has been saved!"
        bot.send_message(message.chat.id, reply)
        notify_admin(message, reply)

# ----------------- Referral handling (wrapper for /start) -----------------
def make_referral_link(user_id):
    try:
        username = bot.get_me().username
    except:
        username = "YourBotUsername"
    return f"https://t.me/{username}?start=ref{user_id}"

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.startswith("/start"))
def _referral_wrapper_start(message):
    raw = message.text or ""
    uid = str(message.from_user.id)
    users = load_users()
    if uid not in users:
        users[uid] = {"user_info": get_user_info(message), "interaction_count":0, "messages":[], "points":0, "referrals":0, "referred_by":None, "last_claim":None, "active":True}
    # detect referral token
    if raw.startswith("/start ref"):
        try:
            referrer_id = raw.split("ref",1)[1].strip()
            if referrer_id and referrer_id != str(message.from_user.id):
                udata = load_users()
                user_entry = udata.get(str(message.from_user.id), {})
                if user_entry.get("referred_by") is None:
                    if str(referrer_id) in udata:
                        udata[str(referrer_id)]["referrals"] = udata[str(referrer_id)].get("referrals",0) + 1
                        udata[str(referrer_id)]["points"] = udata[str(referrer_id)].get("points",0) + REFERRAL_BONUS_POINTS
                        udata[str(message.from_user.id)]["referred_by"] = str(referrer_id)
                        save_users(udata)
                        try:
                            bot.send_message(int(referrer_id), f"🎉 You earned {REFERRAL_BONUS_POINTS} points! New referral: @{message.from_user.username}")
                        except:
                            pass
        except Exception as e:
            print("referral parse error:", e)

    # call existing welcome behaviour
    try:
        send_welcome(message)
    except Exception as e:
        print("Error calling send_welcome:", e)

# ----------------- /refer command -----------------
@bot.message_handler(commands=['refer'])
def handle_refer(message):
    uid = str(message.from_user.id)
    users = load_users()
    if uid not in users:
        users[uid] = {"user_info": get_user_info(message), "interaction_count":0, "messages":[], "points":0, "referrals":0, "referred_by":None, "last_claim":None, "active":True}
        save_users(users)
    link = make_referral_link(uid)
    text = f"Share this referral link and earn {REFERRAL_BONUS_POINTS} points when someone joins using it:\n\n{link}"
    bot.send_message(message.chat.id, text)

# ----------------- /earn rotator -----------------
@bot.message_handler(commands=['earn'])
def handle_earn(message):
    uid = str(message.from_user.id)
    users = load_users()
    if uid not in users:
        users[uid] = {"user_info": get_user_info(message), "interaction_count":0, "messages":[], "points":0, "referrals":0, "referred_by":None, "last_claim":None, "active":True}
    n_show = min(4, len(MONETAG_LINKS))
    if n_show == 0:
        bot.send_message(message.chat.id, "Links not configured yet. Contact admin.")
        return
    chosen = random.sample(MONETAG_LINKS, n_show)
    kb = types.InlineKeyboardMarkup()
    for i,link in enumerate(chosen):
        kb.add(types.InlineKeyboardButton(f"Open Link #{i+1}", url=link))
    text = "👇 Get your earning links — click any (we show multiple links to increase CTR):"
    bot.send_message(message.chat.id, text, reply_markup=kb)
    users[uid]["active"] = True
    users[uid]["interaction_count"] = users[uid].get("interaction_count",0) + 1
    save_users(users)

# ----------------- /claim daily bonus -----------------
@bot.message_handler(commands=['claim'])
def handle_claim(message):
    uid = str(message.from_user.id)
    users = load_users()
    if uid not in users:
        users[uid] = {"user_info": get_user_info(message), "interaction_count":0, "messages":[], "points":0, "referrals":0, "referred_by":None, "last_claim":None, "active":True}
    last = users[uid].get("last_claim")
    now = datetime.utcnow()
    if last:
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
        except:
            last_dt = datetime.utcnow() - timedelta(days=2)
    else:
        last_dt = datetime.utcnow() - timedelta(days=2)
    if now - last_dt >= timedelta(days=1):
        users[uid]["points"] = users[uid].get("points",0) + DAILY_BONUS_POINTS
        users[uid]["last_claim"] = now.strftime("%Y-%m-%d %H:%M:%S")
        save_users(users)
        bot.send_message(message.chat.id, f"✅ You claimed {DAILY_BONUS_POINTS} points! Your total: {users[uid]['points']} points.")
    else:
        remaining = timedelta(days=1) - (now - last_dt)
        hours = int(remaining.total_seconds()//3600)
        minutes = int((remaining.total_seconds()%3600)//60)
        bot.send_message(message.chat.id, f"⏳ You already claimed. Try again after {hours}h {minutes}m.")

# ----------------- /stats for admin -----------------
@bot.message_handler(commands=['stats'])
def handle_stats(message):
    try:
        admin = int(ADMIN_USER_ID) if ADMIN_USER_ID else None
    except:
        admin = None
    if not admin or message.from_user.id != admin:
        return
    users = load_users()
    total_users = len(users)
    total_points = sum(u.get("points",0) for u in users.values())
    total_referrals = sum(u.get("referrals",0) for u in users.values())
    bot.send_message(message.chat.id, f"Users: {total_users}\nPoints: {total_points}\nReferrals: {total_referrals}")

# ----------------- Broadcast thread -----------------
def broadcast_links_loop():
    while True:
        try:
            users = load_users()
            targets = []
            for uid, u in users.items():
                if BROADCAST_ACTIVE_ONLY:
                    if u.get("active", True):
                        targets.append(uid)
                else:
                    targets.append(uid)
            if targets:
                chosen = random.sample(MONETAG_LINKS, min(3, len(MONETAG_LINKS)))
                kb = types.InlineKeyboardMarkup()
                for i,link in enumerate(chosen):
                    kb.add(types.InlineKeyboardButton(f"Earn #{i+1}", url=link))
                text = "🔥 New earning links — click any to earn now!"
                for uid in targets:
                    try:
                        bot.send_message(int(uid), text, reply_markup=kb)
                        time.sleep(0.08)
                    except Exception:
                        try:
                            users = load_users()
                            users[uid]["active"] = False
                            save_users(users)
                        except:
                            pass
            time.sleep(AUTO_BROADCAST_INTERVAL_MIN * 60)
        except Exception as e:
            print("Broadcast loop error:", e)
            time.sleep(60)

def start_broadcast_thread():
    t = Thread(target=broadcast_links_loop, daemon=True)
    t.start()

# ----------------- Tasks (Dynamic) -----------------
TASKS = [
    {
        "id": "task_yt_watch",
        "title": "Watch a short YouTube video",
        "description": "Watch a recommended short YouTube video and press Claim after watching.",
        "reward": 3,
        "type": "visit",
        "url": "https://youtu.be/dQw4w9WgXcQ"
    },
    {
        "id": "task_visit_site",
        "title": "Visit our partner site",
        "description": "Open the partner site and come back to claim points.",
        "reward": 2,
        "type": "visit",
        "url": "https://example.com"
    },
    {
        "id": "task_share_bot",
        "title": "Share bot with friends",
        "description": "Share your referral link with friends and get reward when someone joins.",
        "reward": 5,
        "type": "share"
    }
]

@bot.message_handler(commands=['tasks'])
def list_tasks(message):
    text_lines = ["📋 Available Tasks:"]
    for t in TASKS:
        text_lines.append(f"\n*{t['title']}* — {t['description']}\nReward: {t['reward']} points\nCommand: /task_{t['id']}")
    bot.send_message(message.chat.id, "\n".join(text_lines), parse_mode="Markdown")

# dynamic task handlers
def _make_task_handler(task):
    def handler(message):
        uid = str(message.from_user.id)
        users = load_users()
        if uid not in users:
            users[uid] = {"user_info": get_user_info(message), "interaction_count":0, "messages":[], "points":0, "referrals":0, "referred_by":None, "last_claim":None, "active":True}
        if task["type"] == "visit":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Open Link", url=task.get("url", "https://example.com")))
            text = f"🔎 *{task['title']}*\n\n{task['description']}\n\nAfter visiting, execute /claimtask_{task['id']} to get your reward."
            bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)
        elif task["type"] == "share":
            link = make_referral_link(uid)
            share_text = f"আমি এই বট দিয়ে আয় করছি! চেষ্টা করে দেখো:\n{link}"
            bot.send_message(message.chat.id, f"Share this text with your friends:\n\n{share_text}\n\nWhen someone joins using your link you'll get points automatically.")
        else:
            bot.send_message(message.chat.id, "Task started. Follow instructions to claim reward.")
    return handler

for t in TASKS:
    cmd = f"task_{t['id']}"
    globals()[f"handler_{cmd}"] = _make_task_handler(t)
    bot.register_message_handler(globals()[f"handler_{cmd}"], commands=[cmd.replace("task_","task_")])

@bot.message_handler(func=lambda m: m.text and m.text.startswith("/claimtask_"))
def claim_task_endpoint(message):
    try:
        cmd = message.text.split("/claimtask_",1)[1].strip()
    except:
        bot.send_message(message.chat.id, "Invalid claim command.")
        return
    task = next((x for x in TASKS if x["id"]==cmd), None)
    if not task:
        bot.send_message(message.chat.id, "Task not found.")
        return
    uid = str(message.from_user.id)
    users = load_users()
    if uid not in users:
        users[uid] = {"user_info": get_user_info(message), "interaction_count":0, "messages":[],"points":0, "referrals":0, "referred_by":None, "last_claim":None, "active":True}
    last_claims = users[uid].get("task_claims", {})
    now = datetime.utcnow()
    last_ts = last_claims.get(task["id"])
    if last_ts:
        try:
            last_dt = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
        except:
            last_dt = now - timedelta(days=1)
    else:
        last_dt = now - timedelta(days=1)
    if now - last_dt < timedelta(hours=1):
        bot.send_message(message.chat.id, "⏳ You can claim this task again after 1 hour.")
        return
    users[uid]["points"] = users[uid].get("points",0) + task.get("reward",0)
    last_claims[task["id"]] = now.strftime("%Y-%m-%d %H:%M:%S")
    users[uid]["task_claims"] = last_claims
    save_users(users)
    bot.send_message(message.chat.id, f"✅ Task claimed! You earned {task.get('reward',0)} points. Total: {users[uid]['points']} pts.")

# ----------------- Join & Earn -----------------
@bot.message_handler(commands=['joinearn'])
def join_earn_info(message):
    text = "To earn by joining our channels, use /joincheck <channel_username_without_@>\nExample: /joincheck examplechannel"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text and m.text.startswith("/joincheck "))
def join_check(message):
    try:
        parts = message.text.split()
        ch = parts[1].strip()
    except:
        bot.send_message(message.chat.id, "Use: /joincheck channelusername")
        return
    channel = ch if ch.startswith("@") else f"@{ch}"
    uid = message.from_user.id
    try:
        member = bot.get_chat_member(channel, uid)
        status = member.status
        if status in ["member", "creator", "administrator"]:
            users = load_users()
            suid = str(uid)
            if suid not in users:
                users[suid] = {"user_info": get_user_info(message), "interaction_count":0, "messages":[], "points":0, "referrals":0, "referred_by":None, "last_claim":None, "active":True}
            joins = users[suid].get("joins", [])
            if channel not in joins:
                users[suid]["points"] = users[suid].get("points",0) + 5
                joins.append(channel)
                users[suid]["joins"] = joins
                save_users(users)
                bot.send_message(message.chat.id, "✅ Verified join. You've been awarded 5 points.")
            else:
                bot.send_message(message.chat.id, "You have already been credited for joining this channel.")
        else:
            bot.send_message(message.chat.id, "❌ You are not a member of that channel. Please join first.")
    except Exception as e:
        bot.send_message(message.chat.id, "Could not verify membership. Make sure the channel username is correct and the bot is an admin in the channel if needed.")

# ----------------- Withdraw system -----------------
@bot.message_handler(commands=['balance'])
def cmd_balance(message):
    uid = str(message.from_user.id)
    users = load_users()
    pts = users.get(uid, {}).get("points", 0)
    bot.send_message(message.chat.id, f"💰 Your balance: {pts} points.\nMinimum withdraw: {MIN_WITHDRAW_POINTS} points.")

@bot.message_handler(commands=['withdraw'])
def cmd_withdraw(message):
    uid = str(message.from_user.id)
    users = load_users()
    pts = users.get(uid, {}).get("points", 0)
    if pts < MIN_WITHDRAW_POINTS:
        bot.send_message(message.chat.id, f"Minimum withdraw is {MIN_WITHDRAW_POINTS} points. Your balance: {pts} pts.")
        return
    bot.send_message(message.chat.id, "Send withdrawal details in one message in this format:\n\nMETHOD|ACCOUNT|AMOUNT\n\nExample:\nPayPal|me@example.com|100")
    # next-step handler
    @bot.message_handler(func=lambda m: m.text and "|" in m.text)
    def process_withdraw_request(m):
        if m.from_user.id != message.from_user.id:
            return
        try:
            method, account, amount = m.text.split("|")
            amount = int(amount.strip())
        except:
            bot.send_message(m.chat.id, "Invalid format. Try /withdraw again.")
            return
        uid2 = str(m.from_user.id)
        users2 = load_users()
        pts2 = users2.get(uid2, {}).get("points", 0)
        if amount > pts2:
            bot.send_message(m.chat.id, f"You don't have enough points. Your balance: {pts2}")
            return
        req = {
            "id": str(uuid.uuid4()),
            "user_id": uid2,
            "method": method.strip(),
            "account": account.strip(),
            "amount": amount,
            "status": "pending",
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
        ws = load_withdraws()
        ws.append(req)
        save_withdraws(ws)
        users2[uid2]["points"] = users2[uid2].get("points",0) - amount
        save_users(users2)
        bot.send_message(m.chat.id, "✅ Withdraw request created. Admin will review and process it.")
        try:
            if ADMIN_USER_ID:
                bot.send_message(int(ADMIN_USER_ID), f"New withdraw: {req}")
        except:
            pass

@bot.message_handler(commands=['mywithdraws'])
def my_withdraws(message):
    uid = str(message.from_user.id)
    ws = load_withdraws()
    my = [w for w in ws if w["user_id"]==uid]
    if not my:
        bot.send_message(message.chat.id, "No withdraw requests found.")
        return
    text = "Your withdraw requests:\n\n"
    for w in my:
        text += f"ID: {w['id']}\nAmount: {w['amount']}\nMethod: {w['method']}\nStatus: {w['status']}\n\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['withdraws'])
def list_withdraws(message):
    try:
        admin = int(ADMIN_USER_ID) if ADMIN_USER_ID else None
    except:
        admin = None
    if not admin or message.from_user.id != admin:
        return
    ws = load_withdraws()
    pending = [w for w in ws if w["status"]=="pending"]
    if not pending:
        bot.send_message(message.chat.id, "No pending withdraws.")
        return
    text = "Pending withdraws:\n\n"
    for w in pending:
        text += f"ID: {w['id']}\nUser: {w['user_id']}\nAmount: {w['amount']}\nMethod: {w['method']}\nAccount: {w['account']}\n\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['approve_withdraw'])
def approve_withdraw(message):
    try:
        admin = int(ADMIN_USER_ID) if ADMIN_USER_ID else None
    except:
        admin = None
    if not admin or message.from_user.id != admin:
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Use: /approve_withdraw <withdraw_id>")
        return
    wid = parts[1].strip()
    ws = load_withdraws()
    found = False
    for w in ws:
        if w["id"] == wid and w["status"]=="pending":
            w["status"] = "approved"
            w["processed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            found = True
            try:
                bot.send_message(int(w["user_id"]), f"Your withdraw {w['id']} for {w['amount']} has been approved by admin.")
            except:
                pass
            break
    if found:
        save_withdraws(ws)
        bot.send_message(message.chat.id, "Withdraw approved.")
    else:
        bot.send_message(message.chat.id, "Withdraw not found or already processed.")

# ----------------- Leaderboard & Share -----------------
@bot.message_handler(commands=['leaderboard'])
def leaderboard_cmd(message):
    users = load_users()
    ranked = sorted(users.items(), key=lambda x: x[1].get("points",0), reverse=True)[:10]
    text = "🏆 Top Earners:\n\n"
    for idx, (uid, info) in enumerate(ranked, start=1):
        uname = info.get("user_info",{}).get("username") or info.get("user_info",{}).get("first_name","User")
        pts = info.get("points",0)
        text += f"{idx}. @{uname} — {pts} pts\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['share'])
def share_cmd(message):
    uid = str(message.from_user.id)
    link = make_referral_link(uid)
    share_text = f"আমি এই বট দিয়ে আয় করছি! চেষ্টা করে দেখো: {link}"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Open Bot", url=link))
    bot.send_message(message.chat.id, f"Share this message with your friends:\n\n{share_text}", reply_markup=kb)

# ----------------- Keep-alive Flask server for Replit & UptimeRobot -----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is running successfully! 😎"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# ----------------- Startup -----------------
if __name__ == "__main__":
    print("Starting Monetag PRO Bot...")
    # start keep-alive web server
    try:
        keep_alive()
    except Exception as e:
        print("keep_alive error:", e)
    # start broadcast thread
    try:
        start_broadcast_thread()
    except Exception as e:
        print("broadcast thread error:", e)
    # begin polling
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("Stopping by user")
    except Exception as e:
        print("Bot crashed:", e)
