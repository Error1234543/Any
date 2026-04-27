import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
import google.generativeai as genai
from PIL import Image
import io

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Bot setup
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# START COMMAND
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "🚀 *Welcome to AI Doubt Solver Bot*\n\n"
        "📚 NEET/JEE Doubts Solve in seconds\n"
        "🖼 Send Image or Text Question\n\n"
        "⚡ Powered by sonic\n\n"
        "👉 Just send your question!",
        parse_mode="Markdown"
    )

# TEXT DOUBT SOLVER
@dp.message()
async def solve_text(message: Message):
    if message.text:
        await message.answer("⏳ Solving your doubt...")

        try:
            response = model.generate_content(
                f"Solve this question step by step for a NEET/JEE student:\n{message.text}"
            )

            await message.answer(response.text)

        except Exception as e:
            await message.answer(f"❌ Error: {e}")

# IMAGE DOUBT SOLVER
@dp.message(lambda msg: msg.photo)
async def solve_image(message: Message):
    await message.answer("🧠 Reading image and solving...")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_data = await bot.download_file(file.file_path)

        image = Image.open(io.BytesIO(file_data.read()))

        response = model.generate_content(
            [
                "Solve this question from the image step by step for NEET/JEE student:",
                image
            ]
        )

        await message.answer(response.text)

    except Exception as e:
        await message.answer(f"❌ Error: {e}")

# RUN BOT
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())