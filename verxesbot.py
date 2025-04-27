import os
import random
import datetime
import asyncio
import re
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext

# === CONFIGURATION ===
TOKEN = os.environ.get("BOT_TOKEN")  # <-- Corrected here
ADMIN_ID = 5784227087
DATABASE_DIR = "database"
ACCESS_FILE = "access.json"
USER_DROPS_DIR = "userdrops"

DATABASE_FILES = {filename[:-4]: filename for filename in os.listdir(DATABASE_DIR) if filename.endswith('.txt')}
ACCESS_KEYS = {}
USER_ACCESS = {}
LAST_GENERATE = {}
COOLDOWN_SECONDS = 10

# === LOAD/SAVE ACCESS ===
def load_access():
    global USER_ACCESS
    if os.path.exists(ACCESS_FILE):
        with open(ACCESS_FILE, "r") as f:
            data = json.load(f)
            USER_ACCESS = {int(k): (v if v is None else float(v)) for k, v in data.items()}

def save_access():
    with open(ACCESS_FILE, "w") as f:
        json.dump(USER_ACCESS, f)

# === BANNER ===
def banner():
    return "🌀 *VerxesHub*\n───────────────\n"

# === START COMMAND ===
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        banner() + "🚀 *Welcome to VerxesHub!*\n\n🔑 Use `/key <your_access_key>` to unlock tools.\n📂 Use `/generate` after unlocking.\n\n🧠 Use `/help` for all commands.",
        parse_mode="Markdown"
    )

# === HELP COMMAND ===
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        banner() + """🧠 *Help Menu*

🚀 `/start` - Welcome message
🔑 `/key <access_key>` - Unlock access
📂 `/generate` - Open database menu
🛡️ `/listaccess` - Admin: View users
❌ `/revoke <user_id>` - Admin: Revoke user
🎯 `/genkey <time>` - Admin: Generate key
📤 `/uploadfile` - Admin: Upload new database files""",
        parse_mode="Markdown"
    )

# === GENERATE KEY ===
async def generate_key(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text(banner() + "❌ *Admin only!*", parse_mode="Markdown")
        return
    if len(context.args) == 0:
        await update.message.reply_text(banner() + "⚠️ *Usage: `/genkey <time>`*", parse_mode="Markdown")
        return
    duration_text = context.args[0]
    if duration_text.lower() == "lifetime":
        expires_at = None
        expiry_text = "Lifetime"
    else:
        match = re.match(r"(\d+)([smhd])", duration_text)
        if not match:
            await update.message.reply_text(banner() + "⚠️ *Invalid format!*", parse_mode="Markdown")
            return
        value, unit = int(match[1]), match[2]
        time_multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        expires_at = (datetime.datetime.now() + datetime.timedelta(seconds=value * time_multipliers[unit])).timestamp()
        expiry_text = f"{value}{unit}"
    key = str(random.randint(100000, 999999))
    ACCESS_KEYS[key] = {"expires_at": expires_at}
    await update.message.reply_text(banner() + f"🎯 *Key Generated:* `{key}`\n📅 Valid for: {expiry_text}", parse_mode="Markdown")

# === ENTER KEY ===
async def enter_key(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        await update.message.reply_text(banner() + "⚠️ *Usage: `/key <access_key>`*", parse_mode="Markdown")
        return
    key = context.args[0]
    user_id = update.message.from_user.id
    if key in ACCESS_KEYS:
        key_data = ACCESS_KEYS[key]
        if key_data["expires_at"] and key_data["expires_at"] < datetime.datetime.now().timestamp():
            del ACCESS_KEYS[key]
            await update.message.reply_text(banner() + "❌ *Key expired!*", parse_mode="Markdown")
            return
        USER_ACCESS[user_id] = key_data["expires_at"]
        save_access()
        del ACCESS_KEYS[key]
        await update.message.reply_text(banner() + "✅ *Access granted!*", parse_mode="Markdown")
    else:
        await update.message.reply_text(banner() + "❌ *Invalid or used key!*", parse_mode="Markdown")

# === CHECK ACCESS ===
def has_access(user_id):
    if user_id not in USER_ACCESS:
        return False
    if USER_ACCESS[user_id] is None:
        return True
    return USER_ACCESS[user_id] > datetime.datetime.now().timestamp()

# === GENERATE MENU ===
async def generate_menu(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not has_access(user_id):
        await update.message.reply_text(banner() + "🔒 *Access denied! Use `/key <access_key>` first.*", parse_mode="Markdown")
        return
    keyboard = [[InlineKeyboardButton(f"📂 {db}", callback_data=f"generate:{db}")] for db in DATABASE_FILES.keys()]
    await update.message.reply_text(banner() + "📂 *Select a Database:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# === GENERATE FILE ===
async def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    if query.data.startswith("generate:"):
        now = datetime.datetime.now().timestamp()
        if user_id in LAST_GENERATE and (now - LAST_GENERATE[user_id]) < COOLDOWN_SECONDS:
            await query.answer("⏳ Please wait before generating again.", show_alert=True)
            return
        LAST_GENERATE[user_id] = now
        _, category = query.data.split(":")
        file_path = os.path.join(DATABASE_DIR, DATABASE_FILES.get(category, ""))
        if not os.path.exists(file_path):
            await query.message.edit_text(banner() + f"❌ *Database `{category}` not found!*", parse_mode="Markdown")
            return
        await query.message.edit_text(banner() + "🔄 *Connecting to the database...*", parse_mode="Markdown")
        await asyncio.sleep(2)
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        selected = random.sample(lines, min(100, len(lines)))
        drop_file = os.path.join(USER_DROPS_DIR, f"{user_id}_{category}.txt")
        with open(drop_file, "w", encoding="utf-8") as f:
            f.writelines(selected)
        await query.message.reply_document(InputFile(drop_file), caption=banner() + f"✅ *Here is your `{category}` drop!*", parse_mode="Markdown")

# === ADMIN UPLOAD DATABASE FILE ===
async def uploadfile(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text(banner() + "❌ *Admin only!*", parse_mode="Markdown")
        return
    if update.message.document:
        file = await update.message.document.get_file()
        filename = update.message.document.file_name
        save_path = os.path.join(DATABASE_DIR, filename)
        await file.download_to_drive(save_path)
        await update.message.reply_text(banner() + f"✅ *Uploaded:* `{filename}`", parse_mode="Markdown")
        DATABASE_FILES[filename[:-4]] = filename

# === REVOKE ACCESS ===
async def revoke_access(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text(banner() + "❌ *Admin only!*", parse_mode="Markdown")
        return
    if len(context.args) == 0:
        await update.message.reply_text(banner() + "⚠️ *Usage: `/revoke <user_id>`*", parse_mode="Markdown")
        return
    user_id = int(context.args[0])
    if user_id in USER_ACCESS:
        del USER_ACCESS[user_id]
        save_access()
        await update.message.reply_text(banner() + f"✅ *Access revoked for* `{user_id}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(banner() + f"❌ *User `{user_id}` not found!*", parse_mode="Markdown")

# === LIST ACCESS ===
async def list_access(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text(banner() + "❌ *Admin only!*", parse_mode="Markdown")
        return
    text = banner() + "📋 *Active Users:*\n\n"
    if not USER_ACCESS:
        text += "🚫 No users found."
    else:
        for uid, exp in USER_ACCESS.items():
            exp_text = "♾️ Lifetime" if exp is None else datetime.datetime.fromtimestamp(exp).strftime('%Y-%m-%d %H:%M:%S')
            text += f"👤 `{uid}` ➔ {exp_text}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# === MAIN ===
def main():
    load_access()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("genkey", generate_key))
    app.add_handler(CommandHandler("key", enter_key))
    app.add_handler(CommandHandler("generate", generate_menu))
    app.add_handler(CommandHandler("listaccess", list_access))
    app.add_handler(CommandHandler("revoke", revoke_access))
    app.add_handler(CommandHandler("uploadfile", uploadfile))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, uploadfile))
    app.run_polling()

if __name__ == "__main__":
    main()
