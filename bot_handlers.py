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

# O'ZIMIZNING MODULLAR
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

# --- BOT OBYEKTLARI ---
try:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
except Exception as e:
    st.error(f"Botni ishga tushirib bo'lmadi: {e}")
    st.stop()

# --- STATES ---
class UserStates(StatesGroup):
    waiting_for_contact_msg = State()

class AdminStates(StatesGroup):
    waiting_for_bc = State()

# --- GLOBAL O'ZGARUVCHILAR ---
async_lock = asyncio.Lock()
waiting_users = 0
user_data = {}

@st.cache_resource
def load_whisper():
    # 'base' modeli tezlik va sifat balansi uchun optimal
    return whisper.load_model("base")

model_local = load_whisper()

# --- 1. START ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    update_user(m.from_user)
    try:
        u_link = f"@{m.from_user.username}" if m.from_user.username else "Link mavjud emas"
        admin_notif = (
            f"⚡️ <b>Yangi foydalanuvchi:</b>\n"
            f"👤 Ism: {m.from_user.full_name}\n"
            f"🆔 ID: <code>{m.from_user.id}</code>\n"
            f"🔗 Profil: {u_link}"
        )
        await bot.send_message(ADMIN_ID, admin_notif, parse_mode="HTML")
    except: pass

    welcome = (
        f"🌟 <b>Assalomu alaykum, {m.from_user.first_name}!</b>\n\n"
        "Men — <b>Suxandon AI</b> botiman. Audio nutqlarni matnga aylantirishda "
        "va ularni akademik darajada tarjima qilishda sizga yordam beraman.\n\n"
        "🎙 <b>Ishni boshlash uchun audio yoki ovozli xabar yuboring!</b>"
    )
    await m.answer(welcome, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")

# --- 2. AUDIO QABUL QILISH VA FILTRLASH ---
@dp.message(F.audio | F.voice)
async def catch_audio(m: types.Message):
    file_id = m.audio.file_id if m.audio else m.voice.file_id
    file_size = m.audio.file_size if m.audio else m.voice.file_size

    # 20MB limit
    if file_size > 20 * 1024 * 1024:
        await m.answer("⚠️ <b>Fayl hajmi juda katta!</b>\nIltimos, 20MB dan kichik audio yuboring.", parse_mode="HTML")
        return

    u_tag = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
    user_data[m.chat.id] = {'fid': file_id, 'uname': u_tag, 'tr_lang': None, 'view': None}
    
    await m.answer("🌍 <b>Audio qabul qilindi!</b>\nEndi tarjima tilini tanlang:", reply_markup=get_tr_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tr_"))
async def set_tr(call: types.CallbackQuery):
    user_data[call.message.chat.id]['tr_lang'] = call.data.replace("tr_", "")
    await call.message.edit_text("📄 <b>Matn ko'rinishi qanday bo'lsin?</b>", reply_markup=get_split_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("v_"))
async def set_view(call: types.CallbackQuery):
    user_data[call.message.chat.id]['view'] = call.data.replace("v_", "")
    await call.message.edit_text("💾 <b>Natijani qaysi formatda jo'natay?</b>", reply_markup=get_format_kb(), parse_mode="HTML")

# --- 3. ASOSIY PROTSESSOR (DINAMIK PROGRESS BAR BILAN) ---
@dp.callback_query(F.data.startswith("f_"))
async def process_audio(call: types.CallbackQuery):
    global waiting_users
    chat_id = call.message.chat.id
    fmt = call.data.replace("f_", "")
    data = user_data.get(chat_id)
    
    if not data:
        await call.message.answer("❌ Xatolik yuz berdi. Iltimos, audioni qaytadan yuboring.")
        return

    await call.message.delete()
    waiting_users += 1
    
    # Qiziqarli navbat xabari
    wait_msg = await call.message.answer(
        f"⏳ <b>Navbatdasiz:</b> <code>{waiting_users}-o'rin</code>\n"
        f"<i>Bot hozir boshqa foydalanuvchiga yordam beryapti...</i>", 
        parse_mode="HTML"
    )

    async with async_lock:
        a_path, r_path = f"aud_{chat_id}.mp3", f"res_{chat_id}.txt"
        
        # --- DINAMIK PROGRESS BAR FUNKSIYASI ---
        async def update_visual_progress(percent, stage_text):
            # Qiziqarli emojilar to'plami
            icons = ["⚙️", "🔄", "🧠", "✨", "📝", "🌍", "✅"]
            icon = icons[min(int(percent // 15), len(icons)-1)]
            
            blocks = int(percent // 10)
            bar = "🎬" * blocks + "▫️" * (10 - blocks)
            
            try:
                await wait_msg.edit_text(
                    f"🚀 <b>Hozirgi amal:</b> {stage_text}\n"
                    f"<code>{bar}</code> {percent}%\n\n"
                    f"{icon} <i>AI tizimi ishlamoqda...</i>", 
                    parse_mode="HTML"
                )
            except: pass

        try:
            # 1. Yuklash
            await update_visual_progress(10, "Audio yuklanmoqda...")
            file_info = await bot.get_file(data['fid'])
            await bot.download_file(file_info.file_path, a_path)

            # 2. Transkripsiya (Whisper AI)
            await update_visual_progress(35, "AI ovozni eshitib tahlil qilyapti...")
            result = await asyncio.to_thread(model_local.transcribe, a_path)
            segments = result.get('segments', [])

            # 3. Akademik Tarjima
            tr_code = data['tr_lang'] if data['tr_lang'] != "orig" else None
            html_list, txt_list = [], []
            
            total = len(segments)
            await update_visual_progress(60, "Matn lug'at asosida shakllantirilyapti...")

            for i, s in enumerate(segments):
                raw_txt = s['text'].strip()
                if not raw_txt: continue
                
                stamp = format_time_stamp(s['start'])
                line_html, line_txt = "", ""
                
                # Akademik tarjima mantiqi: To'liq va qisqartirishsiz
                if tr_code:
                    try:
                        translated = await asyncio.to_thread(
                            GoogleTranslator(source='auto', target=tr_code).translate, raw_txt
                        )
                        if data['view'] == "split":
                            line_html = f"<b>{stamp}</b> {clean_text(raw_txt)}\n└ <i>{clean_text(translated)}</i>"
                            line_txt = f"{stamp} {raw_txt}\n   ({translated})"
                        else:
                            line_html = f"{clean_text(raw_txt)} (<i>{clean_text(translated)}</i>)"
                            line_txt = f"{raw_txt} ({translated})"
                    except:
                        line_html = clean_text(raw_txt); line_txt = raw_txt
                else:
                    if data['view'] == "split":
                        line_html = f"<b>{stamp}</b> {clean_text(raw_txt)}"
                        line_txt = f"{stamp} {raw_txt}"
                    else:
                        line_html = clean_text(raw_txt); line_txt = raw_txt
                
                html_list.append(line_html)
                txt_list.append(line_txt)

                # Har 10 ta segmentda progressni yangilash
                if i % 10 == 0:
                    prog_val = 60 + int((i/total)*35)
                    await update_visual_progress(prog_val, "Akademik tarjima tayyorlanmoqda...")

            # 4. Yakunlash va Imzo
            bot_me = await bot.get_me()
            footer = f"\n\n---\n👤 <b>Tayyorladi:</b> {data['uname']}\n🤖 <b>Bot:</b> @{bot_me.username}\n⏰ <b>Vaqt:</b> {get_uz_time()}"
            
            update_stats('audio', fmt)

            if fmt == "txt":
                full_txt = "\n\n".join(txt_list) + footer.replace("<b>", "").replace("</b>", "")
                with open(r_path, "w", encoding="utf-8") as f: f.write(full_txt)
                await call.message.answer_document(types.FSInputFile(r_path), caption="✅ <b>Akademik tahlil yakunlandi!</b>", parse_mode="HTML")
            else:
                # KO'P XABARLI YUBORISH (Agar sig'masa davom ettiradi)
                full_html = "\n\n".join(html_list) + footer
                chunks = split_html_text(full_html)
                
                for idx, chunk in enumerate(chunks):
                    try:
                        await call.message.answer(chunk, parse_mode="HTML")
                        await asyncio.sleep(0.8) # Telegram cheklovi uchun
                    except:
                        await call.message.answer(clean_text(chunk))

            await wait_msg.delete()

        except Exception as e:
            await call.message.answer(f"❌ <b>Xatolik:</b> {e}", parse_mode="HTML")
        finally:
            delete_temp_files(a_path, r_path)
            waiting_users -= 1
            if chat_id in user_data: del user_data[chat_id]

# --- 4. ADMIN PANEL VA BROADCAST ---
@dp.message(F.text == "🔑 Admin Panel", F.chat.id == ADMIN_ID)
async def admin_main(m: types.Message):
    await m.answer("🛠 <b>Admin boshqaruv paneli:</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_stats")
async def show_stats(call: types.CallbackQuery):
    db = load_db()
    s = db['stats']
    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar: {len(db['users'])}\n"
        f"⚙️ Jami ishlovlar: {s['total_processed']}\n"
        f"🎙 Audiodan: {s['audio']}\n"
        f"📄 TXT format: {s['format_txt']}\n"
        f"💬 Chat format: {s['format_chat']}"
    )
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_bc")
async def bc_init(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_bc)
    await call.message.answer("📢 <b>Broadcast:</b> Xabarni yuboring (reklama matni, rasm yoki video).", parse_mode="HTML")
    await call.answer()

@dp.message(AdminStates.waiting_for_bc)
async def bc_run(m: types.Message, state: FSMContext):
    await state.clear()
    db = load_db(); users = db['users']; success = 0
    status_msg = await m.answer("⏳ Tarqatish boshlandi...")
    
    for uid in users:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=m.message_id)
            success += 1
            await asyncio.sleep(0.05)
        except: pass
    
    await status_msg.edit_text(f"✅ <b>Natija:</b> {success} kishiga yetkazildi.", parse_mode="HTML")

# --- 5. BOG'LANISH VA YORDAM ---
@dp.message(F.text == "👨‍💻 Bog'lanish")
async def contact_info(m: types.Message):
    await m.answer("👨‍💻 Admin bilan bog'lanish uchun pastdagi tugmani bosing:", reply_markup=get_contact_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "msg_to_admin")
async def feedback_entry(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_contact_msg)
    await call.message.answer("📝 Xabaringizni yozing:")
    await call.answer()

@dp.message(UserStates.waiting_for_contact_msg)
async def feedback_finish(m: types.Message, state: FSMContext):
    await state.clear()
    await bot.send_message(ADMIN_ID, f"📩 <b>Yangi murojaat:</b>\nKimdan: {m.from_user.full_name}\nID: <code>{m.from_user.id}</code>\nXabar: {m.text}", parse_mode="HTML")
    await m.answer("✅ Xabaringiz yetkazildi.")

@dp.message(F.text == "ℹ️ Yordam")
async def help_cmd(m: types.Message):
    await m.answer("📚 <b>Botdan foydalanish:</b>\n1. Audio yuboring.\n2. Tilni tanlang.\n3. Natijani oling.\n\nSavollar bo'lsa adminga yozing.", parse_mode="HTML")

@dp.message(F.text == "🌐 Saytga kirish")
async def web_open(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Saytni ochish", url="https://shodlikai.github.io/new_3/dastur.html")
    await m.answer("Saytga kirish uchun tugmani bosing:", reply_markup=kb.as_markup())

# --- 6. MUKAMMAL YO'RIQNOMA (ADASHIB YOZILGANLAR UCHUN) ---
@dp.message()
async def guide_handler(m: types.Message):
    # Agar foydalanuvchi ixtiyoriy matn yozsa (va bu asosiy tugma bo'lmasa)
    if m.text in ["🎧 Tahlil boshlash", "🌐 Saytga kirish", "👨‍💻 Bog'lanish", "ℹ️ Yordam", "🔑 Admin Panel"]:
        return

    instruction = (
        f"👋 <b>Salom, {m.from_user.first_name}! Suxandon AI botiga xush kelibsiz.</b>\n\n"
        "Men siz yozgan matnni tushunmayapman, chunki mening asosiy vazifam <b>Audio materiallarni</b> tahlil qilishdir.\n\n"
        "🛠 <b>Botdan qanday foydalanish kerak?</b>\n"
        "1. Menga ovozli xabar (voice) yoki audio fayl (mp3) yuboring.\n"
        "2. Men uni avtomatik taniyman va akademik darajada matnga aylantirib beraman.\n"
        "3. Kerak bo'lsa, inglizcha yoki ruschadan o'zbekchaga to'liq tarjima qilib beraman.\n\n"
        "📍 <i>Hozircha quyidagi menyu tugmalaridan foydalaning yoki menga audio yuboring!</i>"
    )
    await m.answer(instruction, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")
    
