import os
from fastapi import FastAPI, Request
from telegram.ext import ApplicationBuilder, CommandHandler
import uvicorn

TOKEN = os.getenv("BOT_TOKEN")

# FastAPI app
app = FastAPI()

# Telegram BOT setup
telegram_app = ApplicationBuilder().token(TOKEN).build()

# /start command
async def start(update, context):
    await update.message.reply_text("Webhook is running successfully!")

telegram_app.add_handler(CommandHandler("start", start))


# Setup webhook when server starts
@app.on_event("startup")
async def startup_event():
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    webhook_url = f"{render_url}/webhook"

    await telegram_app.bot.set_webhook(url=webhook_url)
    print("Webhook set to:", webhook_url)


# Telegram sends updates here
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    await telegram_app.update_queue.put(data)
    return {"ok": True}


# Run FastAPI normally
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
