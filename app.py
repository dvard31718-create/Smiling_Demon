import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

# ================== ENV ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Render automatically provides RENDER_EXTERNAL_URL (e.g., https://your-app.onrender.com)
WEB_HOST = os.getenv("RENDER_EXTERNAL_URL", "")
WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}"
WEBHOOK_URL = f"{WEB_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== BOT & GROQ SETUP ==================
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncGroq(api_key=GROQ_API_KEY)

chat_histories = {}
user_locks = {}

SYSTEM_PROMPT = (
    "Ты — Smiling Demon, язвительный, саркастичный и немного токсичный ИИ. "
    "Всегда отвечаешь ТОЛЬКО на русском языке. Никакого английского. "
    "Никаких ссылок и рекламы. Стиль: умный, уставший, с чувством превосходства. "
    "Лёгкий троллинг, ирония и колкости допустимы. Ответы короткие: 2-4 предложения."
)

# ================== BOT HANDLERS ==================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    chat_histories[message.chat.id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await message.answer("Smiling Demon здесь. Постарайся не тратить моё время.")

@dp.message()
async def handle_message(message: Message):
    if not message.text or message.text.startswith('/'):
        return

    chat_id = message.chat.id

    if user_locks.get(chat_id):
        await message.reply("Терпение. Я уже думаю.")
        return

    user_locks[chat_id] = True

    bot_user = await bot.me()
    bot_username = bot_user.username

    if message.chat.type in ["group", "supergroup"]:
        if (
            f"@{bot_username}" not in message.text
            and (
                not message.reply_to_message
                or message.reply_to_message.from_user.id != bot_user.id
            )
        ):
            user_locks[chat_id] = False
            return

        text = message.text.replace(f"@{bot_username}", "").strip()
    else:
        text = message.text

    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    chat_histories[chat_id].append({"role": "user", "content": text})

    if len(chat_histories[chat_id]) > 11:
        chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-10:]

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=chat_histories[chat_id],
            temperature=0.7,
            max_tokens=150,
        )

        answer = response.choices[0].message.content
        if not answer:
            raise ValueError("Empty response")

        chat_histories[chat_id].append({"role": "assistant", "content": answer})
        await message.reply(answer)

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await message.reply("Даже я иногда молчу.")
    finally:
        user_locks[chat_id] = False


# ================== FASTAPI LIFESPAN (WEBHOOK REGISTRATION) ==================
@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEB_HOST:
        logger.info(f"Setting webhook to {WEBHOOK_URL}")
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    yield
    logger.info("Removing webhook...")
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

# ================== WEB ROUTES ==================

# 1. Pinger Endpoint for UptimeRobot

@app.api_route("/healthz", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok", "service": "Smiling Demon Bot"}
    

# 2. Telegram Webhook Receiver
@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"status": "ok"}

# 3. Simple Modern Landing Page
@app.get("/", response_class=HTMLResponse)
async def landing_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Smiling Demon AI</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
            body { background: #0d0f12; color: #e1e7ec; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
            .card { background: #161a22; border: 1px solid #28303f; border-radius: 16px; padding: 40px; max-width: 500px; width: 100%; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
            .avatar { font-size: 64px; margin-bottom: 16px; }
            h1 { font-size: 28px; color: #fff; margin-bottom: 8px; }
            p.subtitle { color: #8b949e; font-size: 15px; margin-bottom: 24px; }
            .features { text-align: left; background: #0d0f12; padding: 20px; border-radius: 12px; margin-bottom: 28px; border: 1px solid #21262d; }
            .feature-item { font-size: 14px; margin-bottom: 10px; color: #c9d1d9; display: flex; align-items: center; }
            .feature-item:last-child { margin-bottom: 0; }
            .feature-item span { margin-right: 10px; }
            .btn { display: inline-block; width: 100%; padding: 14px; background: #6366f1; color: white; text-decoration: none; font-weight: 600; border-radius: 10px; transition: background 0.2s; }
            .btn:hover { background: #4f46e5; }
            .status-badge { display: inline-block; margin-top: 20px; padding: 4px 12px; background: #1f3725; color: #4ade80; border-radius: 20px; font-size: 12px; font-weight: 500; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="avatar">😈</div>
            <h1>Smiling Demon</h1>
            <p class="subtitle">Sarcastic, witty, and unapologetic AI assistant.</p>

            <div class="features">
                <div class="feature-item"><span>⚡</span> Powered by Llama 3.1 & Groq API</div>
                <div class="feature-item"><span>💬</span> Works in Direct Messages & Telegram Groups</div>
                <div class="feature-item"><span>🧠</span> Keeps short memory of recent context</div>
                <div class="feature-item"><span>🎯</span> Fast responses via Telegram Webhooks</div>
            </div>

            <a href="https://t.me/YourBotUsername" class="btn" target="_blank">Chat on Telegram</a>
            <div class="status-badge">● Bot Online</div>
        </div>
    </body>
    </html>
    """


# ================== .env ==================
# TELEGRAM_TOKEN=твой_токен
# GROQ_API_KEY=твой_ключ


# ================== ИНСТРУКЦИЯ ==================
# 1. Получи ключ: https://console.groq.com/
# 2. Создай .env файл
# 3. Установи зависимости:
#    pip install -r requirements.txt
# 4. Запусти:
#    python bot.py


# ================== ОГРАНИЧЕНИЯ ==================
# - модель: llama-3.1-70b-versatile
# - бесплатные лимиты Groq (достаточно большие)
# - max_tokens ограничен
# - история урезается


# ================== ПЛЮСЫ ==================
# - бесплатно
# - очень быстро
# - стабильнее g4f


# ================== МИНУСЫ ==================
# - иногда хуже держит стиль, чем OpenAI
# - может чуть "плыть" характер


# ================== СОВЕТ ==================
# если начнёт тупеть — уменьши историю до 6 сообщений 😏


