import asyncio
import logging
import sqlite3
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# ================== ENV ==================
load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN .env faylda topilmadi!")

# ================== SOZLAMALAR ==================
ADMIN_ID = 1787857253
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== SQLITE ==================
conn = sqlite3.connect("bot.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    file_id TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS channels (
    value TEXT PRIMARY KEY,
    type TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    confirmed INTEGER DEFAULT 0
)
""")

conn.commit()

# ================== STATE'LAR ==================
class AddMovie(StatesGroup):
    video = State()
    code = State()

class DeleteMovie(StatesGroup):
    code = State()

class ChannelManage(StatesGroup):
    add = State()
    remove = State()

class Broadcast(StatesGroup):
    message = State()

# ================== OBUNA TEKSHIRISH ==================
# ❗ HAR SAFAR REAL TELEGRAM KANALLAR TEKSHIRILADI
async def check_subscription(user_id):
    cur.execute("SELECT value FROM channels WHERE type='tg'")
    channels = cur.fetchall()

    if not channels:
        return True

    for (value,) in channels:
        try:
            chat_id = value if value.startswith("@") else f"@{value}"
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except:
            return False

    return True

# ================== OBUNA KEYBOARD ==================
def sub_keyboard():
    cur.execute("SELECT value, type FROM channels")
    kb = []

    for value, ch_type in cur.fetchall():
        if ch_type == "tg":
            url = f"https://t.me/{value.replace('@','')}"
        else:
            url = value

        kb.append([InlineKeyboardButton(text="📢 Obuna bo‘lish", url=url)])

    kb.append([InlineKeyboardButton(text="✅ Obuna bo‘ldim", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================== ADMIN MENU ==================
def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo‘shish", callback_data="add_movie")],
        [InlineKeyboardButton(text="❌ Kino o‘chirish", callback_data="del_movie")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton(text="📢 Kanal qo‘shish", callback_data="add_channel")],
        [InlineKeyboardButton(text="🗑 Kanal olib tashlash", callback_data="del_channel")],
        [InlineKeyboardButton(text="📨 Barchaga xabar", callback_data="broadcast")],
        [InlineKeyboardButton(text="💾 Bazani yuklab olish", callback_data="get_db")]
    ])

# ================== /START ==================
@dp.message(Command("start"))
async def start(message: types.Message):
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, confirmed) VALUES (?, 0)",
        (message.from_user.id,)
    )
    conn.commit()

    # ADMIN – o‘z paneli
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 ADMIN PANEL", reply_markup=admin_menu())
        return

    # ❗ USER – HAR SAFAR MAJBURIY OBUNA
    await message.answer(
        "❗ Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:",
        reply_markup=sub_keyboard()
    )


# ================== OBUNA BO‘LDIM ==================
# ❗ endi faqat xabarni yopadi
@dp.callback_query(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("✅ Endi kino kodini yuboring 🎬")

# ================== ADMIN: KINO QO‘SHISH ==================
@dp.callback_query(lambda c: c.data == "add_movie")
async def add_movie(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddMovie.video)
    await call.message.answer("🎥 Kinoni yuboring")

@dp.message(AddMovie.video)
async def save_video(message: types.Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AddMovie.code)
    await message.answer("🔢 Kino kodi:")

@dp.message(AddMovie.code)
async def save_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute(
        "INSERT OR REPLACE INTO movies VALUES (?, ?)",
        (message.text.strip(), data["file_id"])
    )
    conn.commit()
    await state.clear()
    await message.answer("✅ Kino saqlandi", reply_markup=admin_menu())

# ================== ADMIN: KINO O‘CHIRISH ==================
@dp.callback_query(lambda c: c.data == "del_movie")
async def del_movie(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(DeleteMovie.code)
    await call.message.answer("❌ Kino kodi:")

@dp.message(DeleteMovie.code)
async def delete_movie(message: types.Message, state: FSMContext):
    cur.execute("DELETE FROM movies WHERE code=?", (message.text.strip(),))
    conn.commit()
    await state.clear()
    await message.answer("🗑 Kino o‘chirildi", reply_markup=admin_menu())

# ================== ADMIN: STATISTIKA ==================
@dp.callback_query(lambda c: c.data == "stats")
async def stats(call: types.CallbackQuery):
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM movies")
    movies = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM channels")
    channels = cur.fetchone()[0]

    await call.message.answer(
        f"📊 STATISTIKA\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {movies}\n"
        f"📢 Majburiy kanallar: {channels}"
    )

# ================== ADMIN: KANAL QO‘SHISH ==================
@dp.callback_query(lambda c: c.data == "add_channel")
async def add_channel(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChannelManage.add)
    await call.message.answer("➕ @username (ochiq TG) yoki https:// link:")

@dp.message(ChannelManage.add)
async def save_channel(message: types.Message, state: FSMContext):
    text = message.text.strip()
    ch_type = "tg" if text.startswith("@") else "link"

    cur.execute("INSERT OR REPLACE INTO channels VALUES (?, ?)", (text, ch_type))
    conn.commit()

    await state.clear()
    await message.answer("✅ Kanal qo‘shildi", reply_markup=admin_menu())

# ================== ADMIN: KANAL O‘CHIRISH ==================
@dp.callback_query(lambda c: c.data == "del_channel")
async def del_channel(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChannelManage.remove)
    await call.message.answer("🗑 Kanal @username yoki link:")

@dp.message(ChannelManage.remove)
async def remove_channel(message: types.Message, state: FSMContext):
    cur.execute("DELETE FROM channels WHERE value=?", (message.text.strip(),))
    conn.commit()
    await state.clear()
    await message.answer("❌ Kanal olib tashlandi", reply_markup=admin_menu())

# ================== ADMIN: BARCHAGA XABAR ==================
@dp.callback_query(lambda c: c.data == "broadcast")
async def broadcast_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.message)
    await call.message.answer("📨 Xabar matni:")

@dp.message(Broadcast.message)
async def send_broadcast(message: types.Message, state: FSMContext):
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()

    for (uid,) in users:
        try:
            # TEXT
            if message.text:
                await bot.send_message(uid, message.text)

            # PHOTO
            elif message.photo:
                await bot.send_photo(
                    uid,
                    message.photo[-1].file_id,
                    caption=message.caption or ""
                )

            # VIDEO
            elif message.video:
                await bot.send_video(
                    uid,
                    message.video.file_id,
                    caption=message.caption or ""
                )

            # AUDIO
            elif message.audio:
                await bot.send_audio(
                    uid,
                    message.audio.file_id,
                    caption=message.caption or ""
                )

            # VOICE
            elif message.voice:
                await bot.send_voice(uid, message.voice.file_id)

            # VIDEO NOTE (dumaloq video)
            elif message.video_note:
                await bot.send_video_note(uid, message.video_note.file_id)

            # DOCUMENT
            elif message.document:
                await bot.send_document(
                    uid,
                    message.document.file_id,
                    caption=message.caption or ""
                )

            await asyncio.sleep(0.05)

        except:
            pass

    await state.clear()
    await message.answer("✅ Xabar barcha foydalanuvchilarga yuborildi", reply_markup=admin_menu())


# ================== ADMIN: DB YUKLAB OLISH ==================
@dp.callback_query(lambda c: c.data == "get_db")
async def get_db(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    await call.message.answer_document(
        types.FSInputFile("bot.db"),
        caption="💾 Bot ma'lumotlar bazasi"
    )

# ================== USER: KINO OLISH ==================
@dp.message()
async def get_movie(message: types.Message):
    # admin xabarlarini o'tkazamiz
    if message.from_user.id == ADMIN_ID:
        return

    # BUYRUQLARNI o'tkazamiz (/start va hokazo)
    if message.text.startswith("/"):
        return

    # 🔒 MAJBURIY OBUNA – HAR SAFAR
    if not await check_subscription(message.from_user.id):
        await message.answer(
            "❗ Kino olish uchun majburiy kanallarga obuna bo‘ling:",
            reply_markup=sub_keyboard()
        )
        return

    # 🎬 ENDI KINO QIDIRAMIZ
    cur.execute(
        "SELECT file_id FROM movies WHERE code=?",
        (message.text.strip(),)
    )
    movie = cur.fetchone()

    if movie:
        await message.answer_video(movie[0], caption="🎬 Yoqimli tomosha!")
    else:
        await message.answer("❌ Bunday kodli kino yo‘q")


# ================== RUN ==================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
