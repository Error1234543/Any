import os
import base64
import requests
import telebot
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# ===== Load ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
PORT = int(os.getenv("PORT", 10000))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# ===== Gemini Request =====
def ask_gemini(text_prompt, image_base64=None):
    parts = []

    if image_base64:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_base64
            }
        })

    parts.append({
        "text": (
            "You are an expert NEET/JEE teacher.\n"
            "Answer in the SAME language as the question.\n"
            "Explain step by step, exam-oriented.\n\n"
            f"{text_prompt}"
        )
    })

    payload = {
        "contents": [{
            "parts": parts
        }]
    }

    r = requests.post(GEMINI_URL, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][-1]["text"]

# ===== START =====
@bot.message_handler(commands=["start"])
def start(msg):
    bot.reply_to(
        msg,
        "👋 NEET/JEE Doubt Solver Bot\n\n"
        "📩 Text doubt bhejo\n"
        "📸 Image doubt bhejo\n"
        "📸+📝 Image ke sath text bhi bhej sakte ho\n\n"
        "Main same language me answer dunga ✅"
    )

# ===== TEXT DOUBT =====
@bot.message_handler(content_types=["text"])
def text_doubt(msg):
    try:
        bot.send_chat_action(msg.chat.id, "typing")
        ans = ask_gemini(f"Question:\n{msg.text}")
        bot.reply_to(msg, ans)
    except:
        bot.reply_to(msg, "⚠️ Abhi server busy hai, thoda baad try karo.")

# ===== IMAGE / IMAGE + TEXT DOUBT =====
@bot.message_handler(content_types=["photo"])
def image_doubt(msg):
    try:
        bot.send_chat_action(msg.chat.id, "typing")

        # Get highest quality photo
        file_id = msg.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)

        image_base64 = base64.b64encode(file_bytes).decode("utf-8")

        caption = msg.caption if msg.caption else "Solve the question shown in the image."

        prompt = f"Question (image based):\n{caption}"

        ans = ask_gemini(prompt, image_base64=image_base64)
        bot.reply_to(msg, ans)

    except Exception as e:
        bot.reply_to(msg, "⚠️ Image read nahi ho pa rahi, clear photo bhejo.")

# ===== Flask Home =====
@app.route("/")
def home():
    return "Bot is running!"

def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=PORT)