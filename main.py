import os
import base64
import requests
import telebot
import time
from flask import Flask
from threading import Thread, Lock
from dotenv import load_dotenv

# ===== LOAD ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
PORT = int(os.getenv("PORT", 8000))

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("Missing BOT_TOKEN or GEMINI_API_KEY")

# ===== BOT =====
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", timeout=10)
bot = telebot.TeleBot(BOT_TOKEN)

# ===== LOCK (free safe) =====
gemini_lock = Lock()

# ===== GEMINI =====
def ask_gemini(prompt, image_bytes=None):
    with gemini_lock:
        try:
            time.sleep(3)

            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            )

            parts = []

            if image_bytes:
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(image_bytes).decode()
                    }
                })

            parts.append({
                "text": (
                    "Answer in the SAME language as the question. "
                    "Be clear and concise.\n\n"
                    + prompt
                )
            })

            payload = {"contents": [{"parts": parts}]}

            r = requests.post(url, json=payload, timeout=60)
            r.raise_for_status()

            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

        except Exception as e:
            return f"Error: {e}"

# ===== TEXT =====
@bot.message_handler(content_types=["text"])
def handle_text(msg):
    ans = ask_gemini(msg.text)
    bot.reply_to(msg, ans[:4000])

# ===== IMAGE =====
@bot.message_handler(content_types=["photo"])
def handle_image(msg):
    file_info = bot.get_file(msg.photo[-1].file_id)
    img = bot.download_file(file_info.file_path)

    ans = ask_gemini(
        "Solve the given question.",
        image_bytes=img
    )
    bot.reply_to(msg, ans[:4000])

# ===== HEALTH =====
app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200

# ===== RUN =====
if __name__ == "__main__":
    Thread(
        target=lambda: bot.infinity_polling(skip_pending=True),
        daemon=True
    ).start()

    app.run(host="0.0.0.0", port=PORT)