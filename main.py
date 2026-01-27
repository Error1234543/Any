import os
import time
import base64
import io
import requests
import telebot
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from PIL import Image

# ================= LOAD ENV =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
PORT = int(os.getenv("PORT", 10000))

# ================= BOT & APP =================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ================= GEMINI URL =================
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# ================= COOLDOWN =================
user_last_time = {}

def can_ask(user_id, gap=8):
    now = time.time()
    if user_id in user_last_time and now - user_last_time[user_id] < gap:
        return False
    user_last_time[user_id] = now
    return True

# ================= GEMINI ASK =================
def ask_gemini(prompt_text, image_base64=None):
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
            f"{prompt_text}"
        )
    })

    payload = {"contents": [{"parts": parts}]}

    r = requests.post(GEMINI_URL, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    if "candidates" not in data:
        raise Exception(data)

    return data["candidates"][0]["content"]["parts"][-1]["text"]

# ================= START =================
@bot.message_handler(commands=["start"])
def start(msg):
    bot.reply_to(
        msg,
        "👋 <b>NEET / JEE Doubt Solver Bot</b>\n\n"
        "📝 Text doubt bhejo\n"
        "📸 Image doubt bhejo\n"
        "📸➕📝 Image ke sath text bhi bhej sakte ho\n\n"
        "🌐 Gujarati | Hindi | English\n"
        "✅ Same language me answer milega\n\n"
        "✍️ Ab apna question bhejo 👇"
    )

# ================= TEXT DOUBT =================
@bot.message_handler(content_types=["text"])
def text_doubt(msg):
    if not can_ask(msg.from_user.id):
        bot.reply_to(msg, "⏳ Thoda ruk kar dobara bhejo.")
        return

    try:
        bot.send_chat_action(msg.chat.id, "typing")
        ans = ask_gemini(f"Question:\n{msg.text}")
        bot.reply_to(msg, ans)
    except Exception as e:
        print("TEXT ERROR:", e)
        bot.reply_to(msg, "⚠️ Abhi server busy hai, thoda baad try karo.")

# ================= IMAGE DOUBT =================
@bot.message_handler(content_types=["photo"])
def image_doubt(msg):
    if not can_ask(msg.from_user.id):
        bot.reply_to(msg, "⏳ Thoda ruk kar dobara bhejo.")
        return

    try:
        bot.send_chat_action(msg.chat.id, "typing")

        file_id = msg.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)

        # ---- Resize + JPEG force ----
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        image.thumbnail((1024, 1024))

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

        caption = msg.caption or "Solve the question shown in the image."

        ans = ask_gemini(
            f"Question (image based):\n{caption}",
            image_base64=image_base64
        )

        bot.reply_to(msg, ans)

    except Exception as e:
        print("IMAGE ERROR:", e)
        bot.reply_to(
            msg,
            "⚠️ Image read nahi ho pa rahi.\n"
            "Clear photo bhejo ya thoda baad try karo."
        )

# ================= FLASK =================
@app.route("/")
def home():
    return "Bot is running!"

def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=PORT)