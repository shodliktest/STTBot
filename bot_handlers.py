import asyncio
import os
import re
import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import whisper
from deep_translator import GoogleTranslator

# MODULLAR
from config import BOT_TOKEN, ADMIN_ID
from database import update_user, update_stats, load_db
from utils import (
    get_uz_time, clean_text, delete_temp_files, 
    format_time_stamp, split_html_text
)
from keyboards import (
    get_main_menu, get_tr_kb, get_split_kb, get_format_kb, 
    get_admin_kb, get_contact_kb
)

try:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
except Exception as e:
    st.error(f"Token xatosi: {e}")
    st.stop()

# --- STATES ---
class UserStates(StatesGroup):
    waiting_for_contact_msg = State()

class AdminStates(StatesGroup):
    waiting_for_bc = State()

async_lock = asyncio.Lock()
waiting_users = 0
user_data = {}

@st.cache_resource
def load_whisper():
    return whisper.load_model("base")

model_local = load_whisper()

# --- 1. START VA ASOSIY HANDLERLAR ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    update_user(m.from_user)
    try:
        u_link = f"@{m.from_user.username}" if m.from_user.username else "Yo'q"
        msg = (
            f"🆕 <b>YANGI FOYDALANUVCHI:</b>\n"
            f"👤 Ism: {m.from_user.full_name}\n"
            f"🆔 ID: <code>{m.from_user.id}</code>\n"
            f"🔗 Link: {u_link}"
        )
        await bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
    except: pass

    welcome = (
        f"👋 <b>Assalomu alaykum, {m.from_user.first_name}!</b>\n\n"
        f"🎙 <b>Suxandon AI</b> botiga xush kelibsiz.\n"
        "Men audio materiallarni akademik darajada tahlil qilib beraman.\n\n"
        "🚀 <b>Ishni boshlash uchun audio yuboring!</b>"
    )
    await m.answer(welcome, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")

@dp.message(F.text == "ℹ️ Yordam")
async def help_h(m: types.Message):
    await m.answer(
        "📚 <b>BOTDAN FOYDALANISH YO'RIQNOMASI:</b>\n\n"
        "1. Audio yoki ovozli xabar yuboring.\n"
        "2. Kerakli tarjima tilini tanlang.\n"
        "3. Matn ko'rinishini belgilang.\n"
        "4. Natijani chatda yoki fayl ko'rinishida oling.\n\n"
        "✅ <b>Imkoniyatlar:</b> Akademik tarjima, Time Split va uzun xabarlarni qo'llab-quvvatlash.",
        parse_mode="HTML"
    )

@dp.message(F.text == "👨‍💻 Bog'lanish")
async def contact_h(m: types.Message):
    await m.answer("👨‍💻 Admin bilan bog'lanish uchun tugmani bosing:", reply_markup=get_contact_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "msg_to_admin")
async def feedback_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_contact_msg)
    await call.message.answer("📝 <b>Xabaringizni yozing:</b>", parse_mode="HTML")
    await call.answer()

@dp.message(UserStates.waiting_for_contact_msg)
async def feedback_process(m: types.Message, state: FSMContext):
    await state.clear()
    await bot.send_message(ADMIN_ID, f"📩 <b>MURОJAAT:</b>\n\n👤 {m.from_user.full_name} (ID: {m.from_user.id})\n📝 Xabar: {m.text}", parse_mode="HTML")
    await m.answer("✅ <b>Xabaringiz adminga yetkazildi!</b>", parse_mode="HTML")

# --- 2. AUDIO QABUL QILISH ---
@dp.message(F.audio | F.voice)
async def handle_audio(m: types.Message):
    fid = m.audio.file_id if m.audio else m.voice.file_id
    fsize = m.audio.file_size if m.audio else m.voice.file_size

    if fsize > 20 * 1024 * 1024:
        await m.answer("❌ <b>Xatolik:</b> Fayl hajmi juda katta (Max: 20MB).", parse_mode="HTML")
        return

    u_tag = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
    user_data[m.chat.id] = {'fid': fid, 'uname': u_tag, 'tr_lang': None, 'view': None}
    await m.answer("🌍 <b>Audio qabul qilindi.</b> Tarjima tilini tanlang:", reply_markup=get_tr_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tr_"))
async def tr_callback(call: types.CallbackQuery):
    user_data[call.message.chat.id]['tr_lang'] = call.data.replace("tr_", "")
    await call.message.edit_text("📄 <b>Matn ko'rinishini tanlang:</b>", reply_markup=get_split_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("v_"))
async def view_callback(call: types.CallbackQuery):
    user_data[call.message.chat.id]['view'] = call.data.replace("v_", "")
    await call.message.edit_text("💾 <b>Natija qaysi formatda bo'lsin?</b>", reply_markup=get_format_kb(), parse_mode="HTML")

# --- 3. ASOSIY PROTSESSOR (JONLI PROGRESS BAR VA SPLITTING) ---
@dp.callback_query(F.data.startswith("f_"))
async def process_final(call: types.CallbackQuery):
    global waiting_users
    chat_id = call.message.chat.id
    fmt = call.data.replace("f_", "")
    data = user_data.get(chat_id)
    
    if not data:
        await call.message.answer("❌ Ma'lumot topilmadi, iltimos audio yuboring.")
        return

    await call.message.delete()
    waiting_users += 1
    wait_msg = await call.message.answer(f"⏳ <b>Navbatdasiz: {waiting_users}-o'rin</b>", parse_mode="HTML")

    async with async_lock:
        a_path, r_path = f"tmp_{chat_id}.mp3", f"res_{chat_id}.txt"
        
        async def update_bar(percent, action_text):
            """Dinamik va jonli progress bar funksiyasi"""
            blocks = int(percent // 10)
            bar = "🟩" * blocks + "⬜" * (10 - blocks)
            # Har bir qadamda qiziqarli emojilar
            emoji = "🔄" if percent < 40 else "🧠" if percent < 80 else "✅"
            try:
                await wait_msg.edit_text(
                    f"🚀 <b>Hozirgi amal:</b> {action_text}\n"
                    f"<code>{bar}</code> {percent}%\n\n"
                    f"{emoji} <i>Iltimos, jarayon tugashini kuting...</i>", 
                    parse_mode="HTML"
                )
            except: pass

        try:
            # 1-Bosqich: Faylni yuklash (0% -> 10%)
            await update_bar(10, "Fayl serverga yuklanmoqda...")
            f_info = await bot.get_file(data['fid'])
            await bot.download_file(f_info.file_path, a_path)

            # 2-Bosqich: AI Transkripsiya (10% -> 40%)
            await update_bar(30, "AI ovozni eshitib, matnga o'girmoqda...")
            res = await asyncio.to_thread(model_local.transcribe, a_path)
            segments = res['segments']
            await update_bar(40, "Nutq muvaffaqiyatli tanib olindi.")

            # 3-Bosqich: Akademik Tarjima (40% -> 90%)
            tr_code = data['tr_lang'] if data['tr_lang'] != "orig" else None
            html_list, txt_list = [], []
            total_seg = len(segments)
            last_p = 40

            for i, seg in enumerate(segments):
                raw_txt = seg['text'].strip()
                if not raw_txt: continue
                
                t_stamp = format_time_stamp(seg['start'])
                tr_html, tr_txt = "", ""
                
                if tr_code:
                    try:
                        # Qisqartirmasdan akademik darajada tarjima qilish
                        translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=tr_code).translate, raw_txt)
                        tr_html = f"\n└ <i>{clean_text(translated)}</i>"
                        tr_txt = f"\n   ({translated})"
                    except: pass
                
                if data['view'] == "split":
                    html_list.append(f"<b>{t_stamp}</b> {clean_text(raw_txt)}{tr_html}")
                    txt_list.append(f"{t_stamp} {raw_txt}{tr_txt}")
                else:
                    html_list.append(f"{clean_text(raw_txt)} {tr_html}")
                    txt_list.append(f"{raw_txt} {tr_txt}")

                # Progressni har 10% qadamda yangilash
                current_p = 40 + int((i / total_seg) * 50)
                if current_p >= last_p + 10:
                    await update_bar(current_p, "Akademik tarjima tayyorlanmoqda...")
                    last_p = (current_p // 10) * 10

            # 4-Bosqich: Yakunlash (90% -> 100%)
            await update_bar(90, "Natija shakllantirilmoqda...")
            bot_me = await bot.get_me()
            sign = f"\n\n---\n👤 {data['uname']}\n🤖 @{bot_me.username}\n⏰ {get_uz_time()}"
            
            update_stats('audio', fmt)

            if fmt == "txt":
                with open(r_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(txt_list) + sign.replace("<b>","").replace("</b>",""))
                await call.message.answer_document(types.FSInputFile(r_path), caption="✅ <b>Akademik tahlil yakunlandi!</b>", parse_mode="HTML")
            else:
                # KO'P XABARLI YUBORISH (Split mantiqi)
                full_html = "\n\n".join(html_list) + sign
                chunks = split_html_text(full_html)
                for chunk in chunks:
                    try:
                        await call.message.answer(chunk, parse_mode="HTML")
                        await asyncio.sleep(0.7) # Telegram limitidan qochish
                    except:
                        await call.message.answer(clean_text(chunk))

            await update_bar(100, "Tayyor! ✅")
            await asyncio.sleep(1.5)
            await wait_msg.delete()

        except Exception as e:
            await call.message.answer(f"❌ <b>Xatolik:</b> {e}", parse_mode="HTML")
        finally:
            delete_temp_files(a_path, r_path)
            waiting_users -= 1
            if chat_id in user_data: del user_data[chat_id]

# --- 4. ADMIN PANEL HANDLERLARI (TO'LIQ) ---
@dp.message(F.text == "🔑 Admin Panel", F.chat.id == ADMIN_ID)
async def admin_panel_h(m: types.Message):
    await m.answer("🛠 <b>Admin Boshqaruv Paneli:</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_stats")
async def stats_cb(call: types.CallbackQuery):
    db = load_db()
    s = db['stats']
    msg = (
        f"📊 <b>BOT STATISTIKASI:</b>\n\n"
        f"👥 Foydalanuvchilar: {len(db['users'])}\n"
        f"🔄 Ishlovlar: {s['total_processed']}\n"
        f"🎙 Audio: {s['audio']}\n"
        f"📄 TXT format: {s['format_txt']}\n"
        f"💬 Chat format: {s['format_chat']}"
    )
    await call.message.answer(msg, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_list")
async def list_cb(call: types.CallbackQuery):
    db = load_db()
    users = db['users']
    msg = f"📋 <b>FOYDALANUVCHILAR RO'YXATI ({len(users)}):</b>\n\n"
    for i, (uid, u) in enumerate(list(users.items())[:50], 1):
        msg += f"{i}. {u['name']} (ID: {uid})\n"
    
    # Uzun ro'yxatni ham bo'lib yuboramiz
    for chunk in split_html_text(msg):
        await call.message.answer(chunk, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_bc")
async def bc_cb(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📢 <b>Broadcast:</b> Xabarni yuboring (reklama matni yoki rasm).", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_bc)
    await call.answer()

@dp.message(AdminStates.waiting_for_bc)
async def bc_process(m: types.Message, state: FSMContext):
    await state.clear()
    db = load_db()
    users = db['users']
    count = 0
    prog = await m.answer("⏳ Tarqatish boshlandi...")
    for uid in users:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=m.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await prog.edit_text(f"✅ Xabar {count} kishiga yuborildi.")

# --- 5. BOSHQA FUNKSIYALAR ---
@dp.message(F.text == "🌐 Saytga kirish")
async def site_h(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Saytni ochish", url="https://shodlikai.github.io/new_3/dastur.html")
    await m.answer("Veb-versiyaga o'tish:", reply_markup=kb.as_markup())

# --- 6. MUKAMMAL YO'RIQNOMA (ADASHGAN USERLAR UCHUN) ---
@dp.message()
async def unknown_handler(m: types.Message):
    # Asosiy tugmalarni filtrlash
    if m.text in ["🎧 Tahlil boshlash", "🌐 Saytga kirish", "👨‍💻 Bog'lanish", "ℹ️ Yordam", "🔑 Admin Panel"]:
        return

    text = (
        f"👋 <b>Salom, {m.from_user.first_name}! Suxandon AI botiga xush kelibsiz.</b>\n\n"
        "Men siz yuborgan matnli xabarni tushunmadim, chunki mening vazifam audio materiallarni tahlil qilishdir.\n\n"
        "🛠 <b>Botdan qanday foydalanish kerak?</b>\n"
        "1️⃣ Menga ovozli xabar (voice) yoki audio fayl (mp3) yuboring.\n"
        "2️⃣ Kerakli tarjima tilini va matn ko'rinishini tanlang.\n"
        "3️⃣ Men uni akademik darajada matnga aylantirib beraman.\n\n"
        "💡 <i>Yordam uchun quyidagi tugmalardan foydalaning yoki audio yuboring!</i>"
    )
    await m.answer(text, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")
        
