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

# ================== ENV CONFIGURATION ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Extract and validate base URL from Render
raw_host = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
if raw_host and not raw_host.startswith("http"):
    WEB_HOST = f"https://{raw_host}"
else:
    WEB_HOST = raw_host

WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}"
WEBHOOK_URL = f"{WEB_HOST}{WEBHOOK_PATH}" if WEB_HOST else ""

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== SETUP & INITIALIZATION ==================
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncGroq(api_key=GROQ_API_KEY)

# Priority list of models to try sequentially if limits are exceeded
FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
]

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
    logger.info(f"Received /start from user ID: {message.from_user.id}")
    chat_histories[message.chat.id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await message.answer("Smiling Demon здесь. Постарайся не тратить моё время.")

@dp.message()
async def handle_message(message: Message):
    if not message.text or message.text.startswith('/'):
        return

    chat_id = message.chat.id
    logger.info(f"Incoming message from chat {chat_id}: {message.text[:30]}...")

    if user_locks.get(chat_id):
        await message.reply("Терпение. Я уже думаю.")
        return

    user_locks[chat_id] = True

    try:
        bot_user = await bot.me()
        bot_username = bot_user.username

        # Filter messages in group chats
        if message.chat.type in ["group", "supergroup"]:
            if (
                f"@{bot_username}" not in message.text
                and (
                    not message.reply_to_message
                    or message.reply_to_message.from_user.id != bot_user.id
                )
            ):
                return

            text = message.text.replace(f"@{bot_username}", "").strip()
        else:
            text = message.text

        if chat_id not in chat_histories:
            chat_histories[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

        chat_histories[chat_id].append({"role": "user", "content": text})

        # Keep system prompt + last 14 turns
        if len(chat_histories[chat_id]) > 15:
            chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-14:]

        answer = None

        # Sequential model fallback loop
        for model in FALLBACK_MODELS:
            try:
                logger.info(f"Requesting completion using model: {model}")
                response = await client.chat.completions.create(
                    model=model,
                    messages=chat_histories[chat_id],
                    temperature=0.8,
                    max_tokens=200,
                )

                candidate_answer = response.choices[0].message.content
                if candidate_answer:
                    answer = candidate_answer
                    logger.info(f"Successfully generated response with model: {model}")
                    break
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}. Attempting fallback...")

        if answer:
            chat_histories[chat_id].append({"role": "assistant", "content": answer})
            await message.reply(answer)
        else:
            logger.error("All fallback models failed to return a response.")
            await message.reply("Даже я иногда молчу.")

    finally:
        user_locks[chat_id] = False


# ================== FASTAPI LIFESPAN ==================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== STARTING SERVER ===")
    if WEB_HOST:
        try:
            logger.info(f"Setting webhook URL to: {WEBHOOK_URL}")
            res = await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
            logger.info(f"Webhook setting response: {res}")
        except Exception as e:
            logger.error(f"Failed to set webhook on startup: {e}")
    else:
        logger.error("RENDER_EXTERNAL_URL is not set! Webhook could not be auto-configured.")
    
    yield
    logger.info("=== SHUTTING DOWN SERVER ===")


app = FastAPI(lifespan=lifespan)

# ================== WEB ROUTES ==================
@app.api_route("/healthz", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok", "service": "Smiling Demon Bot"}

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"Error handling update in webhook: {e}", exc_info=True)
    
    # Always return HTTP 200 OK so Telegram keeps the webhook active
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    return """
    <!DOCTYPE html>
    <html lang="ru">
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
            <p class="subtitle">Саркастичный и язвительный ИИ-помощник.</p>

            <div class="features">
                <div class="feature-item"><span>⚡</span> Автопереключение моделей при лимитах (Fallback)</div>
                <div class="feature-item"><span>💬</span> Поддержка личных сообщений и групп Telegram</div>
                <div class="feature-item"><span>🧠</span> Память диалога в реальном времени</div>
                <div class="feature-item"><span>🎯</span> Мгновенный отклик через Webhook</div>
            </div>

            <a href="https://t.me/" class="btn" target="_blank">Открыть в Telegram</a>
            <div class="status-badge">● Bot Online</div>
        </div>
    </body>
    </html>
    """
