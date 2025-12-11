import os
from fastapi import FastAPI, Request
from telegram.ext import ApplicationBuilder, CommandHandler

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + "/webhook"

app = FastAPI()

# ---------------- TELEGRAM HANDLERS ---------------- #
async def start(update, context):
    await update.message.reply_text("Bot is running with webhook! 🚀")

# Build telegram app
telegram_app = ApplicationBuilder().token(TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))


# ---------------- STARTUP: SET WEBHOOK ---------------- #
@app.on_event("startup")
async def on_startup():
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    print("Webhook set to:", WEBHOOK_URL)


# ---------------- WEBHOOK ROUTE ---------------- #
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    await telegram_app.update_queue.put(data)
    return {"ok": True}


# ---------------- RUN FASTAPI ---------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
