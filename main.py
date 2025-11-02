import os
import json
import sqlite3
import base64
import requests
import telebot
from flask import Flask
import logging

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OWNER_ID = int(os.getenv("OWNER_ID", "7447651332"))
PORT = int(os.getenv("PORT", 8000))

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("❌ Missing BOT_TOKEN or GEMINI_API_KEY environment variables!")

# basic logging
logging.basicConfig(level=logging.INFO)

# Delete webhook if active
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

bot = telebot.TeleBot(BOT_TOKEN)
AUTH_DB = "auth.db"

# ===== AUTH (sqlite) =====
def init_auth_db():
    conn = sqlite3.connect(AUTH_DB)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS owners (user_id INTEGER PRIMARY KEY)"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS allowed_users (user_id INTEGER PRIMARY KEY)"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS allowed_groups (chat_id INTEGER PRIMARY KEY)"""
    )
    # Ensure owner is present
    cur.execute("INSERT OR IGNORE INTO owners(user_id) VALUES(?)", (OWNER_ID,))
    cur.execute("INSERT OR IGNORE INTO allowed_users(user_id) VALUES(?)", (OWNER_ID,))
    conn.commit()
    conn.close()


init_auth_db()

# (auth.json file-based storage removed; using `auth.db` sqlite for persistence)

def add_allowed_user_db(user_id: int) -> bool:
    conn = sqlite3.connect(AUTH_DB)
    cur = conn.cursor()
    try:
        cur.execute("INSERT OR IGNORE INTO allowed_users(user_id) VALUES(?)", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def remove_allowed_user_db(user_id: int) -> bool:
    conn = sqlite3.connect(AUTH_DB)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM allowed_users WHERE user_id=?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def is_owner(user_id: int) -> bool:
    conn = sqlite3.connect(AUTH_DB)
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM owners WHERE user_id=?", (user_id,))
        return cur.fetchone() is not None
    finally:
        conn.close()


def is_allowed(user_id: int, chat_id: int) -> bool:
    conn = sqlite3.connect(AUTH_DB)
    cur = conn.cursor()
    try:
        # check owners
        cur.execute("SELECT 1 FROM owners WHERE user_id=?", (user_id,))
        if cur.fetchone():
            return True
        # check allowed users
        cur.execute("SELECT 1 FROM allowed_users WHERE user_id=?", (user_id,))
        if cur.fetchone():
            return True
        # check allowed groups
        cur.execute("SELECT 1 FROM allowed_groups WHERE chat_id=?", (chat_id,))
        return cur.fetchone() is not None
    finally:
        conn.close()

# ===== GEMINI REQUEST =====
def ask_gemini(prompt, image_bytes=None):
    try:
        # NOTE: some API keys / projects may not support the same model names or the
        # generateContent method. If you see a 404 saying the model/method isn't
        # supported, call `list_models()` to inspect available models for your key.
        # Use configured Gemini model (default: gemini-2.0-flash). You can override
        # by setting GEMINI_MODEL in your environment.
        url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

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
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "⚠️ No response from Gemini.")
        )
        return text.strip()

    except requests.exceptions.HTTPError as e:
        # If the model or method isn't supported the API often returns 404 and
        # suggests calling ListModels. In that case, try to fetch available
        # models for the provided API key and return a friendly message.
        try:
            status = e.response.status_code
        except Exception:
            status = None


        if status == 404:
            # Provide helpful guidance: show available models and suggest checking
            # the GEMINI_MODEL env var (maybe your project/key doesn't support
            # the requested model/method).
            try:
                models_info = list_models(GEMINI_API_KEY)
                return (
                    "❌ Gemini HTTP Error 404: the requested model or method isn't supported for this API key.\n"
                    f"Requested model: {GEMINI_MODEL}\n"
                    "Available models (from ListModels):\n" + models_info +
                    "\n\nTip: set GEMINI_MODEL env var to one of the listed models (for example, 'gemini-2.0-flash') and redeploy.\n"
                    "If this persists, ensure the API key/project has access to the Gemini model family and the generateContent API."
                )
            except Exception as ex:
                return f"❌ Gemini HTTP Error 404 and failed to list models: {ex}\nRaw: {e.response.text}"

        return f"❌ Gemini HTTP Error: {status} - {e.response.text}"
    except Exception as e:
        return f"❌ Gemini Error: {e}"


def list_models(api_key: str) -> str:
    """Call the Generative Language API models list endpoint and return a
    human-readable summary. This helps diagnose which models and methods are
    available for the provided API key or project.
    """
    url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    data = res.json()
    models = data.get("models") or data.get("model") or []
    out_lines = []
    for m in models:
        name = m.get("name") or m.get("model") or str(m)
        description = m.get("description") or ""
        out_lines.append(f"- {name}: {description}")
    if not out_lines:
        return "(no models returned)"
    return "\n".join(out_lines)

# ===== COMMANDS =====
@bot.message_handler(commands=["start"])
def start(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.reply_to(
        msg,
        "🤖 **Hello!** I'm your NEET/JEE AI Doubt Solver.\n\n"
        "📸 Send an image of your question or\n"
        "💬 Type your question — I'll explain step-by-step using Gemini AI.",
    )

@bot.message_handler(commands=["add"])
def add_user(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Only owner can use this command.")
    try:
        uid = int(msg.text.split()[1])
        added = add_allowed_user_db(uid)
        if added:
            bot.reply_to(msg, f"✅ Added user ID {uid}.")
        else:
            bot.reply_to(msg, "⚠️ User already allowed.")
    except Exception:
        bot.reply_to(msg, "⚠️ Usage: /add <user_id>")

@bot.message_handler(commands=["remove"])
def remove_user(msg):
    if not is_owner(msg.from_user.id):
        return bot.reply_to(msg, "🚫 Only owner can use this command.")
    try:
        uid = int(msg.text.split()[1])
        removed = remove_allowed_user_db(uid)
        if removed:
            bot.reply_to(msg, f"✅ Removed user ID {uid}.")
        else:
            bot.reply_to(msg, "⚠️ User not found.")
    except Exception:
        bot.reply_to(msg, "⚠️ Usage: /remove <user_id>")

# ===== TEXT & IMAGE HANDLERS =====
@bot.message_handler(content_types=["text"])
def text_query(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, "typing")
    ans = ask_gemini(msg.text)
    bot.reply_to(msg, ans[:4000])

@bot.message_handler(content_types=["photo"])
def image_query(msg):
    if not is_allowed(msg.from_user.id, msg.chat.id):
        return bot.reply_to(msg, "🚫 Not authorized.")
    bot.send_chat_action(msg.chat.id, "typing")
    file_info = bot.get_file(msg.photo[-1].file_id)
    img = bot.download_file(file_info.file_path)
    ans = ask_gemini("Solve this NEET/JEE question step-by-step:", image_bytes=img)
    bot.reply_to(msg, ans[:4000])

# ===== FLASK HEALTH CHECK =====
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is alive and polling!", 200

if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: bot.infinity_polling(skip_pending=True, timeout=60)).start()
    app.run(host="0.0.0.0", port=PORT)