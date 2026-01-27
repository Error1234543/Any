import os
import io
import base64
import requests
import telebot
from flask import Flask
from threading import Thread
from PIL import Image

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

GEMINI_MODEL = "gemini-2.0-flash"

# ================== BOT ==================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# ================== GEMINI ==================
def ask_gemini(text, image_b64=None):
    parts = []

    if image_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_b64
            }
        })

    parts.append({
        "text": (
            "You are an expert NEET/JEE teacher.\n"
            "Answer in the SAME language as the question.\n"
            "Explain step by step, simple and clear.\n\n"
            f"{text}"
        )
    })

    payload = {"contents": [{"parts": parts}]}

    r = requests.post(GEMINI_URL, json=payload, timeout=45)

    if r.status_code != 200:
        return "⚠️ Abhi thoda load hai. 10 second baad try karo."

    data = r.json()
    if "candidates" not in data:
        return "⚠️ Question thoda clear bhejo."

    return data["candidates"][0]["content"]["parts"][-1]["text"]

# ================== START ==================
@bot.message_handler(commands=["start"])
def start(msg):
    bot.reply_to(
        msg,
        "👋 <b>NEET / JEE Doubt Solver</b>\n\n"
        "📝 Text question bhejo\n"
        "📸 Image question bhejo\n"
        "📸➕📝 Image ke sath text bhi bhej sakte ho\n\n"
        "Gujarati | Hindi | English\n"
        "Same language me answer milega ✅"
    )

# ================== TEXT ==================
@bot.message_handler(content_types=["text"])
def text_doubt(msg):
    bot.send_chat_action(msg.chat.id, "typing")
    ans = ask_gemini(f"Question:\n{msg.text}")
    bot.reply_to(msg, ans)

# ================== IMAGE ==================
@bot.message_handler(content_types=["photo"])
def image_doubt(msg):
    bot.send_chat_action(msg.chat.id, "typing")

    try:
        file_id = msg.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)

        # SIMPLE + SAFE image handling
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        image.thumbnail((800, 800))

        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=80)
        image_b64 = base64.b64encode(buf.getvalue()).decode()

        caption = msg.caption or "Solve the question shown in the image."

        ans = ask_gemini(
            f"Question (from image):\n{caption}",
            image_b64
        )

        bot.reply_to(msg, ans)

    except:
        bot.reply_to(
            msg,
            "⚠️ Image clear nahi hai.\n"
            "Straight photo bhejo (crop mat karo)."
        )

# ================== FLASK ==================
@app.route("/")
def home():
    return "Bot running"

def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=PORT)