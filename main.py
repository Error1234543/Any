import os
import requests
import telebot
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
)

def ask_gemini(question):
    payload = {
        "contents": [{
            "parts": [{
                "text": f"""
You are an expert NEET/JEE teacher.
Answer in the SAME language as the question.
Explain step by step.
Question:
{question}
"""
            }]
        }]
    }
    r = requests.post(GEMINI_URL, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(
        msg,
        "👋 NEET/JEE Doubt Solver Bot\n"
        "Gujarati / Hindi / English me question bhejo"
    )

@bot.message_handler(content_types=['text'])
def solve(msg):
    try:
        bot.send_chat_action(msg.chat.id, "typing")
        ans = ask_gemini(msg.text)
        bot.reply_to(msg, ans)
    except Exception:
        bot.reply_to(msg, "⚠️ Abhi server busy hai, thoda baad try karo.")

@app.route("/")
def home():
    return "Bot is running!"

def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=PORT)