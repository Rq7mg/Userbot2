import os
import json
import asyncio
import random
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# ----------------- ENV -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# ----------------- GLOBAL -----------------
LOGIN_STATE = {}   # user_id: step
TEMP_CLIENT = {}   # user_id: {"client":..., "phone":...}
STOP_FLAGS = {}    # user_id: stop durumu

# ----------------- JSON UTILS -----------------
def load_json(name, default):
    if not os.path.exists(name):
        with open(name, "w") as f:
            json.dump(default, f)
    with open(name) as f:
        return json.load(f)

def save_json(name, data):
    with open(name, "w") as f:
        json.dump(data, f)

# ----------------- AUTH -----------------
def is_premium(uid):
    data = load_json("authorized.json", {"users":[]})
    return uid == OWNER_ID or uid in data["users"]

# ----------------- TELEGRAM CLIENT -----------------
def get_client(uid):
    sessions = load_json("sessions.json", {})
    if str(uid) not in sessions:
        return None
    return TelegramClient(StringSession(sessions[str(uid)]), API_ID, API_HASH)

def save_session(uid, client):
    sessions = load_json("sessions.json", {})
    sessions[str(uid)] = client.session.save()
    save_json("sessions.json", sessions)

def cleanup(uid):
    LOGIN_STATE.pop(uid, None)
    TEMP_CLIENT.pop(uid, None)

# ----------------- LOGIN -----------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_premium(uid):
        await update.message.reply_text("⛔ Premium değilsiniz.")
        return
    LOGIN_STATE[uid] = "phone"
    await update.message.reply_text("📱 Telefon numaranızı girin (+90...)")

async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in LOGIN_STATE:
        return
    text = update.message.text.strip()
    step = LOGIN_STATE[uid]
    if step == "phone":
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        asyncio.create_task(async_login_phone(update, uid, client, text))
    elif step == "code":
        data = TEMP_CLIENT[uid]
        asyncio.create_task(async_login_code(update, uid, data, text))
    elif step == "password":
        data = TEMP_CLIENT[uid]
        asyncio.create_task(async_login_password(update, uid, data, text))

async def async_login_phone(update, uid, client, phone):
    try:
        await client.connect()
        await client.send_code_request(phone)
        TEMP_CLIENT[uid] = {"client": client, "phone": phone}
        LOGIN_STATE[uid] = "code"
        await update.message.reply_text("📩 Telegram kodunu girin")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {e}")

async def async_login_code(update, uid, data, code):
    try:
        await data["client"].sign_in(data["phone"], code)
        save_session(uid, data["client"])
        cleanup(uid)
        await update.message.reply_text("✅ Hesap bağlandı")
    except SessionPasswordNeededError:
        LOGIN_STATE[uid] = "password"
        await update.message.reply_text("🔐 2FA şifresini girin")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {e}")

async def async_login_password(update, uid, data, password):
    try:
        await data["client"].sign_in(password=password)
        save_session(uid, data["client"])
        cleanup(uid)
        await update.message.reply_text("✅ Hesap bağlandı")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {e}")

# ----------------- ETIKETLEME -----------------
GOOD_MORNING = ["Günaydın ☀️"]
GOOD_NIGHT = ["İyi geceler 🌙"]

async def tag_all(uid, chat_id, text=None, type_msg=None):
    STOP_FLAGS[uid] = False
    client = get_client(uid)
    if not client:
        return
    await client.start()
    try:
        async for user in client.iter_participants(chat_id):
            if STOP_FLAGS.get(uid):
                break
            mention = f"@{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"
            if type_msg == "gn":
                msg = random.choice(GOOD_MORNING) + " " + mention
            elif type_msg == "ig":
                msg = random.choice(GOOD_NIGHT) + " " + mention
            else:
                msg = text + " " + mention
            await client.send_message(chat_id, msg, parse_mode="md")
            await asyncio.sleep(6)
    except Exception as e:
        print(f"Tag error: {e}")

# ----------------- KOMUTLAR -----------------
async def gn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    asyncio.create_task(tag_all(uid, chat_id, type_msg="gn"))

async def ig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    asyncio.create_task(tag_all(uid, chat_id, type_msg="ig"))

async def t(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    msg = " ".join(context.args)
    if msg:
        asyncio.create_task(tag_all(uid, chat_id, text=msg))
    else:
        await update.message.reply_text("❌ .t mesaj")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    STOP_FLAGS[uid] = True
    await update.message.reply_text("⛔ İşlem durduruldu")

async def pre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("⛔ Sadece owner kullanabilir")
        return
    if not context.args:
        await update.message.reply_text("❌ Kullanım: .pre USER_ID")
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Geçersiz ID")
        return
    data = load_json("authorized.json", {"users":[]})
    if target in data["users"]:
        await update.message.reply_text("ℹ️ Bu kullanıcı zaten premium.")
        return
    data["users"].append(target)
    save_json("authorized.json", data)
    await update.message.reply_text(f"✅ {target} premium yapıldı")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Userbot hazır. .login ile hesap bağlayabilirsiniz.")

# ----------------- MAIN -----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Telegram komutları
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("gn", gn))
    app.add_handler(CommandHandler("ig", ig))
    app.add_handler(CommandHandler("t", t))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("pre", pre))

    # Mesaj bazlı login
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login))

    print("Userbot başlatıldı...")
    app.run_polling()

if __name__ == "__main__":
    main()
