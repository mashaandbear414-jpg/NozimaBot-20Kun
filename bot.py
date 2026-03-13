import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json
import os
import time

# ===================== CONFIG =====================
BOT_TOKEN = "8678976682:AAESN5QkT-vmpzMXq2YAhl5uu_mzYzha9zI"

REQUIRED_CHANNEL = {
    "id": -1003605786561,
    "link": "https://t.me/+E2heG-34gDFiYzli",
    "name": "Ms diary Life 🌷"
}

ADMIN_IDS = [8088495045, 8533402137]

DATA_FILE = "data.json"

# ===================== STATES =====================
class CreateContest(StatesGroup):
    name = State()
    top_count = State()
    prizes = State()
    end_date = State()
    photo = State()
    channel_id = State()

# ===================== DATABASE =====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "contests": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id: int):
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"phone": None, "registered": False}
        save_data(data)
    return data["users"][uid]

def update_user(user_id: int, **kwargs):
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"phone": None, "registered": False}
    data["users"][uid].update(kwargs)
    save_data(data)

def get_active_contests():
    data = load_data()
    return {cid: c for cid, c in data["contests"].items() if c.get("active")}

def get_leaderboard(contest_id):
    data = load_data()
    contest = data["contests"].get(contest_id, {})
    participants = contest.get("participants", {})
    return sorted(participants.items(), key=lambda x: x[1].get("referrals", 0), reverse=True)

# ===================== KEYBOARDS =====================
def sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📢 {REQUIRED_CHANNEL['name']}", url=REQUIRED_CHANNEL["link"])],
        [InlineKeyboardButton(text="✅ A'zo bo'ldim", callback_data="check_sub")]
    ])

def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📲 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Konkurslar")],
            [KeyboardButton(text="⭐ Ballarim"), KeyboardButton(text="📊 Reyting")],
            [KeyboardButton(text="📋 Shartlar")],
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Konkurs yaratish")],
            [KeyboardButton(text="📋 Faol konkurslar")],
            [KeyboardButton(text="🏁 Konkursni yakunlash"), KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="👤 Foydalanuvchi menyusi")],
        ],
        resize_keyboard=True
    )

def skip_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ O'tkazib yuborish")]],
        resize_keyboard=True, one_time_keyboard=True
    )

MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# ===================== INIT =====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

async def check_sub(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL["id"], user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False

async def finish_contest(contest_id: str):
    data = load_data()
    contest = data["contests"].get(contest_id)
    if not contest or not contest.get("active"):
        return

    contest["active"] = False
    data["contests"][contest_id] = contest
    save_data(data)

    top = get_leaderboard(contest_id)
    prizes = contest.get("prizes", [])
    top_count = contest.get("top_count", 3)
    name = contest.get("name", "Konkurs")

    text = f"🏁 <b>{name}</b> — Yakunlandi!\n\n🏆 G'oliblar:\n\n"

    for i in range(min(top_count, len(top))):
        uid, info = top[i]
        refs = info.get("referrals", 0)
        username = info.get("username", "")
        uname_display = f"@{username}" if username else info.get("name", f"ID:{uid}")
        prize = prizes[i] if i < len(prizes) else "—"
        text += f"{MEDALS[i]} <b>{i+1}-o'rin:</b> {uname_display}\n   👥 Referal: {refs}\n   🎁 Sovg'a: {prize}\n\n"

    if not top:
        text += "Ishtirokchilar bo'lmadi.\n"

    channel = contest.get("channel_id")
    if channel:
        try:
            await bot.send_message(channel, text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Channel send error: {e}")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass

async def scheduler():
    while True:
        await asyncio.sleep(30)
        try:
            contests = get_active_contests()
            now = datetime.now()
            for cid, contest in contests.items():
                end_str = contest.get("end_date")
                if end_str:
                    try:
                        end_dt = datetime.strptime(end_str, "%d.%m.%Y %H:%M")
                        if now >= end_dt:
                            await finish_contest(cid)
                    except Exception:
                        pass
        except Exception as e:
            logging.error(f"Scheduler error: {e}")

# ===================== START =====================
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("c_"):
        parts = args[1].split("_")
        if len(parts) == 3:
            contest_id = parts[1]
            ref_id = parts[2]
            user = get_user(user_id)
            if not user.get("registered"):
                update_user(user_id, pending_contest=contest_id, pending_ref=ref_id)
                await message.answer(
                    "🚀 Konkursda ishtirok etish uchun avval ro'yxatdan o'ting!\n\n"
                    "Quyidagi kanalga a'zo bo'ling:",
                    reply_markup=sub_keyboard()
                )
            else:
                await process_join(message, user_id, contest_id, ref_id)
            return

    user = get_user(user_id)
    if user.get("registered"):
        if user_id in ADMIN_IDS:
            await message.answer("👑 Admin panel:", reply_markup=admin_menu())
        else:
            await message.answer("Quyidagi menyudan kerakli bo'limni tanlang 👇", reply_markup=main_menu())
        return

    await message.answer(
        "🚀 Loyihada ishtirok etish uchun quyidagi kanalga a'zo bo'ling.\n"
        "Keyin \"✅ A'zo bo'ldim\" tugmasini bosing\n\n"
        "⚠️ Yopiq kanalga ulanish so'rovini yuborishingiz kifoya.",
        reply_markup=sub_keyboard()
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not await check_sub(user_id):
        await callback.answer("❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)
        return

    user = get_user(user_id)
    if user.get("registered"):
        pending = user.get("pending_contest")
        ref = user.get("pending_ref")
        if pending:
            update_user(user_id, pending_contest=None, pending_ref=None)
            await process_join(callback.message, user_id, pending, ref)
        else:
            if user_id in ADMIN_IDS:
                await callback.message.answer("👑 Admin panel:", reply_markup=admin_menu())
            else:
                await callback.message.answer("Quyidagi menyudan kerakli bo'limni tanlang 👇", reply_markup=main_menu())
        await callback.answer()
        return

    await callback.message.answer("📲 Raqamni yuborish tugmasini bosing!", reply_markup=phone_keyboard())
    await callback.answer()

@dp.message(F.contact)
async def contact_handler(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user.get("registered"):
        if user_id in ADMIN_IDS:
            await message.answer("👑 Admin panel:", reply_markup=admin_menu())
        else:
            await message.answer("Quyidagi menyudan kerakli bo'limni tanlang 👇", reply_markup=main_menu())
        return

    update_user(user_id,
        phone=message.contact.phone_number,
        registered=True,
        username=message.from_user.username or "",
        name=message.from_user.full_name or f"ID:{user_id}"
    )

    pending = user.get("pending_contest")
    ref = user.get("pending_ref")

    await message.answer(
        "🎉 Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang 👇",
        reply_markup=main_menu()
    )

    if pending:
        update_user(user_id, pending_contest=None, pending_ref=None)
        await process_join(message, user_id, pending, ref)

# ===================== JOIN CONTEST =====================
async def process_join(message, user_id: int, contest_id: str, ref_id: str = None):
    data = load_data()
    contest = data["contests"].get(contest_id)

    if not contest or not contest.get("active"):
        try:
            await bot.send_message(user_id, "❌ Bu konkurs topilmadi yoki yakunlangan.")
        except Exception:
            pass
        return

    uid = str(user_id)
    participants = contest.setdefault("participants", {})
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=c_{contest_id}_{user_id}"

    if uid in participants:
        try:
            await bot.send_message(
                user_id,
                f"✅ Siz allaqachon bu konkursda ishtirok etyapsiz!\n\n"
                f"⭐ Ballar: {participants[uid].get('referrals', 0)}\n\n"
                f"🔗 Sizning havolangiz:\n{ref_link}"
            )
        except Exception:
            pass
        return

    user_data = get_user(user_id)
    participants[uid] = {
        "referrals": 5,
        "ref_by": ref_id,
        "username": user_data.get("username", ""),
        "name": user_data.get("name", f"ID:{user_id}")
    }

    # +5 per referral and notify referrer
    if ref_id and ref_id in participants and ref_id != uid:
        participants[ref_id]["referrals"] = participants[ref_id].get("referrals", 0) + 5
        new_score = participants[ref_id]["referrals"]
        new_user_display = f"@{user_data.get('username')}" if user_data.get("username") else user_data.get("name", f"ID:{user_id}")
        try:
            await bot.send_message(
                int(ref_id),
                f"🎉 Sizning havolangiz orqali <b>{new_user_display}</b> konkursga qo'shildi!\n"
                f"⭐ Sizga <b>+5 ball</b> berildi!\n"
                f"📊 Jami ballaringiz: <b>{new_score}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    data["contests"][contest_id] = contest
    save_data(data)

    try:
        await bot.send_message(
            user_id,
            f"🎉 Siz <b>{contest.get('name')}</b>da ro'yxatdan o'tdingiz!\n\n"
            f"⭐ Sizga boshlang'ich <b>5 ball</b> berildi!\n\n"
            f"🔗 Sizning shaxsiy havolangiz:\n{ref_link}\n\n"
            f"Har bir taklif qilingan do'st uchun <b>+5 ball</b>!\n"
            f"Eng ko'p ball yig'gan g'olib bo'ladi! 🏆",
            parse_mode="HTML"
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("join_"))
async def join_cb(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    contest_id = callback.data.split("_")[1]
    user = get_user(user_id)

    if not user.get("registered"):
        update_user(user_id, pending_contest=contest_id, pending_ref=None)
        bot_info = await bot.get_me()
        link = f"https://t.me/{bot_info.username}?start=c_{contest_id}_0"
        await callback.answer("🚀 Ishtirok etish uchun botga o'ting!", show_alert=True)
        try:
            await bot.send_message(user_id, "🚀 Ishtirok etish uchun avval ro'yxatdan o'ting!", reply_markup=sub_keyboard())
        except Exception:
            pass
        return

    await process_join(None, user_id, contest_id, None)
    await callback.answer("✅ Muvaffaqiyatli!", show_alert=False)

# ===================== USER HANDLERS =====================
@dp.message(F.text == "🏆 Konkurslar")
async def contests_list(message: types.Message):
    user = get_user(message.from_user.id)
    if not user.get("registered"):
        await message.answer("Avval ro'yxatdan o'ting!", reply_markup=sub_keyboard())
        return
    contests = get_active_contests()
    if not contests:
        await message.answer("Hozircha faol konkurs yo'q.")
        return
    for cid, c in contests.items():
        count = len(c.get("participants", {}))
        text = (
            f"🏆 <b>{c.get('name')}</b>\n"
            f"📅 Tugash: {c.get('end_date', '—')}\n"
            f"👥 Ishtirokchilar: {count}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Ishtirok etish", callback_data=f"join_{cid}")]
        ])
        if c.get("photo"):
            await message.answer_photo(c["photo"], caption=text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.message(F.text == "⭐ Ballarim")
async def my_points(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user.get("registered"):
        await message.answer("Avval ro'yxatdan o'ting!")
        return
    data = load_data()
    uid = str(user_id)
    text = "⭐ <b>Sizning natijalaringiz:</b>\n\n"
    found = False
    for cid, contest in data["contests"].items():
        if uid in contest.get("participants", {}):
            found = True
            refs = contest["participants"][uid].get("referrals", 0)
            status = "🟢 Faol" if contest.get("active") else "🔴 Yakunlangan"
            text += f"🏆 <b>{contest.get('name')}</b> [{status}]\n   ⭐ Ballar: {refs}\n\n"
    if not found:
        text += "Siz hech qanday konkursda ishtirok etmadingiz."
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📊 Reyting")
async def rating(message: types.Message):
    contests = get_active_contests()
    if not contests:
        await message.answer("Hozircha faol konkurs yo'q.")
        return
    for cid, contest in contests.items():
        top = get_leaderboard(cid)[:10]
        text = f"📊 <b>{contest.get('name')} — Reyting</b>\n\n"
        for i, (uid, info) in enumerate(top):
            uname = f"@{info['username']}" if info.get("username") else info.get("name", f"ID:{uid}")
            balls = info.get("referrals", 0)
            text += f"{MEDALS[i]} {uname} — <b>{balls} ball</b>\n"
        if not top:
            text += "Hozircha ishtirokchilar yo'q."
        await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📋 Shartlar")
async def rules(message: types.Message):
    await message.answer(
        "📋 <b>Shartlar:</b>\n\n"
        "• 🚫 Nakrutka urganlar chetlatiladi\n"
        "• ✅ Konkurs tugaguncha eng ko'p ishtirokchi yig'gan g'olib bo'ladi\n"
        "• ⚖️ Barcha qarorlar administrator tomonidan qabul qilinadi",
        parse_mode="HTML"
    )

@dp.message(F.text == "🎁 Sovg'alar")
async def prizes(message: types.Message):
    contests = get_active_contests()
    if not contests:
        await message.answer("Hozircha faol konkurs yo'q.")
        return
    for cid, c in contests.items():
        text = f"🎁 <b>{c.get('name')} — Sovg'alar:</b>\n\n"
        for i, p in enumerate(c.get("prizes", [])):
            text += f"{MEDALS[i]} {i+1}-o'rin: {p}\n"
        await message.answer(text, parse_mode="HTML")

# ===================== ADMIN HANDLERS =====================
@dp.message(F.text.in_({"/admin", "/panel"}))
async def admin_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("👑 Admin panel:", reply_markup=admin_menu())

@dp.message(F.text == "👤 Foydalanuvchi menyusi")
async def user_mode(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Foydalanuvchi menyusi:", reply_markup=main_menu())

@dp.message(F.text == "📊 Statistika")
async def stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = load_data()
    total = sum(1 for u in data["users"].values() if u.get("registered"))
    active = sum(1 for c in data["contests"].values() if c.get("active"))
    await message.answer(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Ro'yxatdan o'tganlar: {total}\n"
        f"🏆 Jami konkurslar: {len(data['contests'])}\n"
        f"🟢 Faol konkurslar: {active}",
        parse_mode="HTML"
    )

@dp.message(F.text == "📋 Faol konkurslar")
async def active_list(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    contests = get_active_contests()
    if not contests:
        await message.answer("Hozircha faol konkurs yo'q.")
        return
    for cid, c in contests.items():
        count = len(c.get("participants", {}))
        text = (
            f"🏆 <b>{c.get('name')}</b>\n"
            f"🆔 ID: {cid}\n📅 Tugash: {c.get('end_date')}\n"
            f"👥 Ishtirokchilar: {count}\n🏅 Top: {c.get('top_count')}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏁 Yakunlash", callback_data=f"end_{cid}")]
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.message(F.text == "🏁 Konkursni yakunlash")
async def end_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    contests = get_active_contests()
    if not contests:
        await message.answer("Faol konkurslar yo'q.")
        return
    buttons = [[InlineKeyboardButton(text=f"🏁 {c.get('name')}", callback_data=f"end_{cid}")] for cid, c in contests.items()]
    await message.answer("Qaysi konkursni yakunlash?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("end_"))
async def end_cb(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q!")
        return
    contest_id = callback.data.split("_")[1]
    await finish_contest(contest_id)
    await callback.answer("✅ Konkurs yakunlandi!")
    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass

# ===================== CREATE CONTEST =====================
@dp.message(F.text == "➕ Konkurs yaratish")
async def create_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(CreateContest.name)
    await message.answer("📝 Konkurs nomini kiriting:", reply_markup=types.ReplyKeyboardRemove())

@dp.message(CreateContest.name)
async def step_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(CreateContest.top_count)
    await message.answer("🏅 Nechta o'rinli bo'ladi? (1 dan 10 gacha raqam kiriting):")

@dp.message(CreateContest.top_count)
async def step_top(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not (1 <= int(message.text) <= 10):
        await message.answer("❌ Iltimos, 1 dan 10 gacha son kiriting!")
        return
    count = int(message.text)
    await state.update_data(top_count=count, prizes=[], prize_num=1)
    await state.set_state(CreateContest.prizes)
    await message.answer(f"{MEDALS[0]} 1-o'rin uchun sovg'ani kiriting:")

@dp.message(CreateContest.prizes)
async def step_prizes(message: types.Message, state: FSMContext):
    d = await state.get_data()
    prizes = d.get("prizes", [])
    prizes.append(message.text.strip())
    num = d.get("prize_num", 1) + 1
    top_count = d.get("top_count", 1)
    await state.update_data(prizes=prizes, prize_num=num)
    if num <= top_count:
        await message.answer(f"{MEDALS[num-1]} {num}-o'rin uchun sovg'ani kiriting:")
    else:
        await state.set_state(CreateContest.end_date)
        await message.answer("📅 Konkurs tugash sanasini kiriting:\nFormat: 25.12.2025 18:00")

@dp.message(CreateContest.end_date)
async def step_date(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("❌ Format noto'g'ri! Misol: 25.12.2025 18:00")
        return
    await state.update_data(end_date=message.text.strip())
    await state.set_state(CreateContest.photo)
    await message.answer(
        "🖼 Konkurs rasmi kerakmi? Rasm yuboring yoki o'tkazib yuboring:",
        reply_markup=skip_keyboard()
    )

@dp.message(CreateContest.photo)
async def step_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo=message.photo[-1].file_id)
    else:
        await state.update_data(photo=None)
    await state.set_state(CreateContest.channel_id)
    await message.answer(
        "📢 Konkursni kanalga joylashtiramizmi?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Ha, kanalga joylash")],
                [KeyboardButton(text="❌ Yo'q, faqat botda")]
            ],
            resize_keyboard=True, one_time_keyboard=True
        )
    )

@dp.message(CreateContest.channel_id)
async def step_channel(message: types.Message, state: FSMContext):
    send_to_channel = message.text == "✅ Ha, kanalga joylash"
    d = await state.get_data()
    await state.clear()

    contest_id = str(int(time.time()))
    channel = REQUIRED_CHANNEL["id"] if send_to_channel else None

    contest = {
        "id": contest_id,
        "name": d["name"],
        "top_count": d["top_count"],
        "prizes": d["prizes"],
        "end_date": d["end_date"],
        "photo": d.get("photo"),
        "channel_id": channel,
        "active": True,
        "participants": {}
    }

    db = load_data()
    db["contests"][contest_id] = contest
    save_data(db)

    prizes_text = "\n".join([f"{MEDALS[i]} {i+1}-o'rin: {p}" for i, p in enumerate(d["prizes"])])
    post_text = (
        f"🏆 <b>{d['name']}</b>\n\n"
        f"🎁 Sovg'alar:\n{prizes_text}\n\n"
        f"📅 Tugash: {d['end_date']}\n\n"
        f"👇 Ishtirok etish uchun tugmani bosing!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Ishtirok etish", callback_data=f"join_{contest_id}")]
    ])

    if send_to_channel:
        try:
            if d.get("photo"):
                await bot.send_photo(channel, d["photo"], caption=post_text, parse_mode="HTML", reply_markup=kb)
            else:
                await bot.send_message(channel, post_text, parse_mode="HTML", reply_markup=kb)
            await message.answer(f"✅ Konkurs yaratildi va {REQUIRED_CHANNEL['name']} kanaliga joylashtirildi!", reply_markup=admin_menu())
        except Exception as e:
            await message.answer(f"✅ Konkurs yaratildi!\n⚠️ Kanalga yuborishda xato: {e}", reply_markup=admin_menu())
    else:
        if d.get("photo"):
            await message.answer_photo(d["photo"], caption=post_text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(post_text, parse_mode="HTML", reply_markup=kb)
        await message.answer("✅ Konkurs yaratildi!", reply_markup=admin_menu())

# ===================== ERROR HANDLER =====================
@dp.errors()
async def error_handler(event, exception):
    from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
    if isinstance(exception, (TelegramForbiddenError, TelegramBadRequest)):
        logging.warning(f"Telegram error: {exception}")
        return True
    logging.error(f"Unhandled error: {exception}")
    return False

# ===================== MAIN =====================
async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
