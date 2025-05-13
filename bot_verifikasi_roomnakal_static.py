from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import json
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
import re

BOT_TOKEN = '8025954540:AAEvhFpIeRR0eoGmNV_rqaG0ZVLWL1q6lSU'
ADMIN_CHAT_ID = '7629527598'
GROUP_LOBBY_ID = -1002556752525

ROOM_LINKS = {
    "kolpri": "https://t.me/+rkHKJheanU9iZDQy",
    "trakteer": "https://t.me/+3rN7KnkeGPY3ODli",
    "global": "https://t.me/+IKQNWyU2_HRhM2Qy"
}


# Data storage
class BotData:

    def __init__(self):
        self.warn_count = {}
        self.verified_users = set()
        self.daily_stats = {'violations': {}, 'member_count': 0}
        self.load_data()

    def save_data(self):
        data = {
            'warn_count': self.warn_count,
            'verified_users': list(self.verified_users),
            'daily_stats': self.daily_stats
        }
        with open('bot_data.json', 'w') as f:
            json.dump(data, f)

    def load_data(self):
        try:
            with open('bot_data.json', 'r') as f:
                data = json.load(f)
                self.warn_count = data.get('warn_count', {})
                self.verified_users = set(data.get('verified_users', []))
                self.daily_stats = data.get('daily_stats', {
                    'violations': {},
                    'member_count': 0
                })
        except FileNotFoundError:
            pass

    def record_violation(self, user_id, violation_type):
        today = str(date.today())
        if today not in self.daily_stats['violations']:
            self.daily_stats['violations'][today] = []
        self.daily_stats['violations'][today].append({
            'user_id':
            user_id,
            'type':
            violation_type,
            'timestamp':
            datetime.now().isoformat()
        })
        self.save_data()


bot_data = BotData()


def load_blocked_words():
    with open("blocked_words.txt", "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f if line.strip()]


# Moved to message handler to reload on each message


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(update.effective_chat.id,
                                               update.effective_user.id)
    return member.status in [
        ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
    ]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = ("🚨 *RULES RoomNakal 18+* 🚨\n\n"
             "1. 18+ only\n"
             "2. Tidak share promosi tanpa izin\n"
             "3. Jangan hina member/admin\n"
             "4. Dilarang sebar konten privat\n"
             "5. Admin bisa kick kapan saja\n\n"
             "*Klik tombol jika kamu setuju & ingin masuk VIP.*")
    buttons = [[InlineKeyboardButton("✅ Saya Setuju", callback_data='agree')]]
    await update.message.reply_text(rules,
                                    parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=InlineKeyboardMarkup(buttons))


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return

    today = str(date.today())
    violations_today = len(bot_data.daily_stats['violations'].get(today, []))
    verified_count = len(bot_data.verified_users)

    stats_message = (f"📊 Statistik Hari Ini ({today})\n"
                     f"👥 Total Member Terverifikasi: {verified_count}\n"
                     f"⚠️ Pelanggaran Hari Ini: {violations_today}\n")
    await update.message.reply_text(stats_message)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.full_name
    bot_data.verified_users.add(user_id)
    bot_data.save_data()

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID,
                                   text=f"✅ @{username} klik 'Setuju'")
    await query.answer()

    try:
        # Validate links first
        for room_name, link in ROOM_LINKS.items():
            try:
                chat = await context.bot.get_chat(link.split('/')[-1])
                if not chat:
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"⚠️ Warning: Invalid link for room {room_name}")
            except Exception as e:
                print(f"Error checking {room_name}: {str(e)}")
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⚠️ Error with {room_name} link: {str(e)}")

        links = [[InlineKeyboardButton("🎟 KOLPRI", url=ROOM_LINKS["kolpri"])],
                 [
                     InlineKeyboardButton("🎁 Trakteer",
                                          url=ROOM_LINKS["trakteer"])
                 ],
                 [InlineKeyboardButton("🌐 Global", url=ROOM_LINKS["global"])]]

        await query.message.reply_text(
            "✅ Pilih Room VIP:\n\n"
            "Note: Jika link tidak berfungsi, mohon hubungi admin.",
            reply_markup=InlineKeyboardMarkup(links))

    except Exception as e:
        print(f"Error in button_handler: {str(e)}")
        await query.message.reply_text(
            "⚠️ Terjadi kesalahan. Mohon hubungi admin.")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.new_chat_members:
        return

    # Reload blocked words on each message
    blocked_words = load_blocked_words()
    user_id = msg.from_user.id

    if msg.chat.id == GROUP_LOBBY_ID:
        # Link filter
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        if re.search(url_pattern, msg.text
                     or '') and not await is_admin(update, context):
            await msg.delete()
            bot_data.record_violation(user_id, 'link_sharing')
            admin_notification = f"🔗 User @{msg.from_user.username} mencoba share link"
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID,
                                           text=admin_notification)
            return

        # Kata terlarang filter
        if msg.text and any(word in msg.text.lower()
                            for word in blocked_words):
            if not await is_admin(update, context):
                blocked_word = next(word for word in blocked_words
                                    if word in msg.text.lower())
                await msg.delete()
                bot_data.warn_count[str(user_id)] = bot_data.warn_count.get(
                    str(user_id), 0) + 1
                bot_data.record_violation(user_id, 'blocked_word')

                admin_notification = (
                    f"🚨 Laporan Pelanggaran:\n"
                    f"User: {msg.from_user.first_name} (@{msg.from_user.username})\n"
                    f"Kata terlarang: '{blocked_word}'\n"
                    f"Peringatan: {bot_data.warn_count[str(user_id)]}/3")
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID,
                                               text=admin_notification)

                if bot_data.warn_count[str(user_id)] >= 3:
                    await context.bot.ban_chat_member(chat_id=GROUP_LOBBY_ID,
                                                      user_id=user_id)
                    ban_notification = f"🚫 {msg.from_user.first_name} (@{msg.from_user.username}) telah dibanned karena 3x pelanggaran!"
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID, text=f"👮‍♂️ {ban_notification}")
                bot_data.save_data()


if __name__ == "__main__":
    print("🚀 Bot sedang berjalan...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))

    
# Fungsi kirim statistik
async def send_daily_stats():
    today = str(date.today())
    pelanggaran = bot_data.daily_stats['violations'].get(today, [])
    kata = sum(1 for v in pelanggaran if v['type'] == 'blocked_word')
    link = sum(1 for v in pelanggaran if v['type'] == 'link_sharing')
    verified_today = sum(1 for v in pelanggaran if v['type'] == 'verified')
    aktif_hari_ini = len(set(bot_data.daily_stats.get("active_today", [])))

    aktivitas = bot_data.daily_stats.get('activity', {})
    top_3_jam = sorted(aktivitas.items(), key=lambda x: x[1], reverse=True)[:3]
    jam_list = "\\n".join([f"• {jam.zfill(2)}.00 WIB" for jam, _ in top_3_jam]) or "• Tidak ada data"

    msg = f"""📊 Statistik Hari Ini ({today})

👥 Total Member Terverifikasi: {len(bot_data.verified_users)}
🔐 Terverifikasi Hari Ini: {verified_today}
🟢 Member Aktif Hari Ini: {aktif_hari_ini}

⚠️ Pelanggaran Hari Ini: {len(pelanggaran)}
• Kata Terlarang: {kata}
• Share Link: {link}

🕒 Aktivitas Tertinggi Hari Ini:
{jam_list}"""

    await app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)

    bot_data.daily_stats['violations'][today] = []
    bot_data.daily_stats['activity'] = {}
    bot_data.daily_stats['active_today'] = set()
    bot_data.save_data()

# ✅ Scheduler hanya sekali
scheduler = AsyncIOScheduler(timezone=timezone("Asia/Jakarta"))
scheduler.add_job(send_daily_stats, "cron", hour=0, minute=0)
scheduler.start()

app.run_polling()
