# 📦 Установка
# pip install aiogram python-dotenv groq

import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from groq import AsyncGroq

# ================== ENV ==================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ================== ЛОГИ ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== API ==================
client = AsyncGroq(api_key=GROQ_API_KEY)

# ================== ПАМЯТЬ ==================
chat_histories = {}
user_locks = {}

# ================== ХАРАКТЕР ==================
SYSTEM_PROMPT = (
    "Ты — Smiling Demon, язвительный, саркастичный и немного токсичный ИИ. "
    "Всегда отвечаешь ТОЛЬКО на русском языке. "
    "Никакого английского. "
    "Никаких ссылок и рекламы. "
    "Стиль: умный, уставший, с чувством превосходства. "
    "Лёгкий троллинг, ирония и колкости допустимы. "
    "Ответы короткие: 2-4 предложения."
)

# ================== TELEGRAM ==================
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ================== АНИМАЦИЯ ==================
async def typing_animation(chat_id):
    while True:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(3)

# ================== /start ==================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    chat_histories[message.chat.id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    await message.answer("Smiling Demon здесь. Постарайся не тратить моё время.")

# ================== ОБРАБОТКА ==================
@dp.message()
async def handle_message(message: Message):
    if not message.text or message.text.startswith('/'):
        return

    chat_id = message.chat.id

    # ===== анти-спам =====
    if user_locks.get(chat_id):
        await message.reply("Терпение. Я уже думаю.")
        return

    user_locks[chat_id] = True

    # ===== логика групп =====
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

    # ===== память =====
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    chat_histories[chat_id].append({"role": "user", "content": text})

    if len(chat_histories[chat_id]) > 11:
        chat_histories[chat_id] = (
            [chat_histories[chat_id][0]] + chat_histories[chat_id][-10:]
        )

    typing_task = asyncio.create_task(typing_animation(chat_id))

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=chat_histories[chat_id],
            temperature=0.7,
            max_tokens=150,
        )

        answer = response.choices[0].message.content

        if not answer:
            raise ValueError("Пустой ответ")

        chat_histories[chat_id].append(
            {"role": "assistant", "content": answer}
        )

        await message.reply(answer)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.reply("Даже я иногда молчу.")

    finally:
        typing_task.cancel()
        user_locks[chat_id] = False

# ================== ЗАПУСК ==================
async def main():
    logger.info("Demon is alive 😈")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())


# ================== requirements.txt ==================
# aiogram
# python-dotenv
# groq


# ================== .env ==================
# TELEGRAM_TOKEN=...
# GROQ_API_KEY=...


# ================== ВАЖНО ДЛЯ ГРУПП ==================
# BotFather:
# /setprivacy -> Disable


# ================== ЗАПУСК ==================
# python bot.py



# ================== requirements.txt ==================
# aiogram
# python-dotenv
# groq


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


