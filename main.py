# main.py
import json
import telebot
from telebot import types
from datetime import datetime
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

bot = telebot.TeleBot(BOT_TOKEN)

DATA_FILE = "users_v5.json"

def load_users():
    try:
        with open(DATA_FILE, "r") as file:
            content = file.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        print("users_v5.json missing or corrupted, creating new file.")
        save_users({})
        return {}

def save_users(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)

def get_user_info(message):
    return {
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "username": message.from_user.username,
        "language": message.from_user.language_code,
        "is_bot": message.from_user.is_bot,
    }

def log_interaction(user_id, message_text, user_info):
    users = load_users()

    if user_id not in users:
        users[user_id] = {
            "user_info": user_info,
            "interaction_count": 0,
            "messages": []
        }

    users[user_id]["interaction_count"] += 1
    users[user_id]["messages"].append({
        "message": message_text,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    save_users(users)

def get_user_data():
    try:
        return load_users()
    except:
        return {}

def notify_admin(message, answer_text):
    if ADMIN_USER_ID:
        try:
            admin = int(ADMIN_USER_ID)
            bot.send_message(
                admin,
                f"User: @{message.from_user.username} ({message.from_user.id})\n"
                f"Message: {message.text}\n\n"
                f"Bot reply: {answer_text}"
            )
        except:
            pass

@bot.message_handler(commands=['start'])
def send_welcome(message):
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

try:
    from keep_alive import keep_alive
except:
    def keep_alive():
        print("keep_alive skipped (file missing).")

if __name__ == "__main__":
    print("Bot is starting...")

    try:
        keep_alive()
    except Exception as e:
        print("keep_alive error:", e)

    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print("Bot crashed:", e)
