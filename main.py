import os
from telegram.ext import ApplicationBuilder, CommandHandler
from fastapi import FastAPI
from threading import Thread
import uvicorn

TOKEN = os.getenv("BOT_TOKEN")

app = FastAPI()

# Telegram Bot Commands
async def start(update, context):
    await update.message.reply_text("Bot is running with webhook!")

# Create Telegram application
telegram_app = ApplicationBuilder().token(TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))

# Start webhook
@app.on_event("startup")
async def startup_event():
    webhook_url = os.getenv("RENDER_EXTERNAL_URL") + "/webhook"
    await telegram_app.bot.set_webhook(url=webhook_url)

@app.post("/webhook")
async def telegram_webhook(update: dict):
    await telegram_app.update_queue.put(update)
    return {"status": "ok"}

# Run bot in thread
def run_bot():
    telegram_app.run_polling()

Thread(target=run_bot).start()

# FastAPI server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
