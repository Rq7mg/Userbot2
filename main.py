import os
import json
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message

# ------------------ ENV ------------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

# ------------------ GLOBAL ------------------
PREMIUM_USERS_FILE = "authorized.json"
SESSIONS_FILE = "sessions.json"
STOP_FLAGS = {}  # user_id: True/False
TEMP_CLIENTS = {}  # user_id: Client instance

# ------------------ UTIL ------------------
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

def is_premium(user_id):
    data = load_json(PREMIUM_USERS_FILE, {"users": []})
    return user_id == OWNER_ID or user_id in data.get("users", [])

# ------------------ OWNER COMMAND ------------------
async def pre(client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("⛔ Sadece owner kullanabilir.")
        return
    if not message.command or len(message.command) < 2:
        await message.reply("❌ Kullanım: /pre USER_ID")
        return
    try:
        uid = int(message.command[1])
    except:
        await message.reply("❌ Geçersiz ID")
        return
    data = load_json(PREMIUM_USERS_FILE, {"users": []})
    if uid in data.get("users", []):
        await message.reply(f"ℹ️ {uid} zaten premium.")
        return
    data["users"].append(uid)
    save_json(PREMIUM_USERS_FILE, data)
    await message.reply(f"✅ {uid} premium yapıldı.")

# ------------------ LOGIN ------------------
async def login(client, message: Message):
    uid = message.from_user.id
    if not is_premium(uid):
        await message.reply("⛔ Premium değilsiniz.")
        return
    # Kendi session oluşturacak, direkt soracak
    TEMP_CLIENTS[uid] = Client(f"session_{uid}", api_id=API_ID, api_hash=API_HASH)
    await TEMP_CLIENTS[uid].start()
    save_sessions()
    await message.reply("✅ Hesap login oldu ve session kaydedildi.")

def save_sessions():
    # Kaydedilen session isimlerini json'da sakla
    sessions = list(TEMP_CLIENTS.keys())
    save_json(SESSIONS_FILE, sessions)

# ------------------ ETIKETLEME ------------------
async def tag_all(uid, chat_id, text=""):
    STOP_FLAGS[uid] = False
    client = TEMP_CLIENTS.get(uid)
    if not client:
        return
    async for member in client.get_chat_members(chat_id):
        if STOP_FLAGS.get(uid):
            break
        mention = f"[{member.user.first_name}](tg://user?id={member.user.id})"
        msg = text + " " + mention if text else mention
        await client.send_message(chat_id, msg)
        await asyncio.sleep(6)

async def gn(client, message: Message):
    uid = message.from_user.id
    await tag_all(uid, message.chat.id, text="🌞 Günaydın")

async def ig(client, message: Message):
    uid = message.from_user.id
    await tag_all(uid, message.chat.id, text="🌙 İyi geceler")

async def t(client, message: Message):
    uid = message.from_user.id
    if len(message.command) < 2:
        await message.reply("❌ .t <mesaj>")
        return
    text = " ".join(message.command[1:])
    await tag_all(uid, message.chat.id, text=text)

async def stop(client, message: Message):
    uid = message.from_user.id
    STOP_FLAGS[uid] = True
    await message.reply("⛔ İşlem durduruldu.")

# ------------------ START ------------------
async def start(client, message: Message):
    uid = message.from_user.id
    if not is_premium(uid):
        await message.reply("⚠️ Premium değilsiniz.")
    else:
        await message.reply("✅ Userbot aktif.\nKomutlar: .gn .ig .t <mesaj> .stop /pre USER_ID /login")

# ------------------ APP ------------------
app = Client("main_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

app.add_handler(filters.command("start")(start))
app.add_handler(filters.command("login")(login))
app.add_handler(filters.command("pre")(pre))
app.add_handler(filters.command("gn")(gn))
app.add_handler(filters.command("ig")(ig))
app.add_handler(filters.command("t")(t))
app.add_handler(filters.command("stop")(stop))

# ------------------ RUN ------------------
print("Userbot başlatıldı...")
app.run()
