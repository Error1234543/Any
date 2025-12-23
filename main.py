import os
import base64
import requests
import telebot
import time
import logging
from flask import Flask
from threading import Thread, Lock
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
PORT = int(os.getenv("PORT", 8000))

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("❌ Missing BOT_TOKEN or GEMINI_API_KEY environment variables!")

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)

# ===== TELEGRAM BOT =====
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
bot = telebot.TeleBot(BOT_TOKEN)

# ===== GLOBAL LOCK (anti-429) =====
gemini_lock = Lock()

# ===== GEMINI REQUEST =====
def ask_gemini(prompt, image_bytes=None):
    with gemini_lock:  # 🚫 one request at a time
        try:
            time.sleep(4)  # ⏳ cooldown (VERY IMPORTANT)

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

            contents = [{"parts": []}]

            if image_bytes:
                b64 = base64.b64encode(image_bytes).decode("utf-8")
                contents[0]["parts"].append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64
                    }
                })

            contents[0]["parts"].append({"text": prompt})

            payload = {"contents": contents}

            res = requests.post(url, json=payload, timeout=60)
            res.raise_for_status()

            data = res.json()
            return (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "⚠️ No response from Gemini.")
                .strip()
            )

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            return f"❌ Gemini HTTP Error: {status}"
        except Exception as e:
            return f"❌ Gemini Error: {e}"

# ===== COMMANDS =====
@bot.message_handler(commands=["start"])
def start(msg):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "📢 Join our Telegram Channel",
            url="https://t.me/prakash8307"
        )
    )
    bot.reply_to(
        msg,
        "📘 *Send your doubt photo*\n"
        "💬 Or type your question\n\n"
        "⏳ One request at a time\n"
        "🚫 Adult content is strictly prohibited.",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ===== TEXT HANDLER =====
@bot.message_handler(content_types=["text"])
def text_query(msg):
    bot.send_chat_action(msg.chat.id, "typing")
    ans = ask_gemini(msg.text)
    bot.reply_to(msg, ans[:4000])

# ===== IMAGE HANDLER =====
@bot.message_handler(content_types=["photo"])
def image_query(msg):
    bot.send_chat_action(msg.chat.id, "typing")
    file_info = bot.get_file(msg.photo[-1].file_id)
    img = bot.download_file(file_info.file_path)
    ans = ask_gemini(
        "Solve this NEET/JEE question step-by-step:",
        image_bytes=img
    )
    bot.reply_to(msg, ans[:4000])

# ===== FLASK HEALTH CHECK =====
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is alive and polling!", 200

# ===== RUN =====
if __name__ == "__main__":
    Thread(
        target=lambda: bot.infinity_polling(skip_pending=True, timeout=60),
        daemon=True
    ).start()
    app.run(host="0.0.0.0", port=PORT)