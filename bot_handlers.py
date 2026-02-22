import asyncio
import os
import re
import hashlib
import gc
import streamlit as st
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import whisper
from deep_translator import GoogleTranslator

# BIZNING MODULLAR
from config import BOT_TOKEN, ADMIN_ID
from database import (
    update_user, update_stats, get_all_users, get_stats, 
    save_transcript, get_user_transcripts, get_transcript_by_id,
    save_audio_cache, get_audio_cache
)
from utils import get_uz_time, clean_text, delete_temp_files, format_time_stamp, split_html_text
from keyboards import (
    get_main_menu, get_tr_kb, get_split_kb, get_format_kb, 
    get_admin_kb, get_list_format_kb, get_contact_kb,
    get_transcripts_pagination_kb, get_transcript_format_kb
)
# MATNLAR FAYLIDAN CHAQIRISH (YANGI)
from messages import (
    get_welcome_msg, get_guide_msg, get_new_user_admin_msg,
    get_pechat_text, get_pechat_html, HELP_MSG, AUDIO_RECEIVED_MSG,
    VIEW_MODE_MSG, FORMAT_MODE_MSG
)

try:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
except Exception as e:
    st.error(f"Botni ishga tushirishda xatolik: {e}")
    st.stop()

# ==========================================
# HOLATLAR VA O'ZGARUVCHILAR
# ==========================================
class UserStates(StatesGroup):
    waiting_for_contact_msg = State()

class AdminStates(StatesGroup):
    waiting_for_bc = State()
    waiting_for_user_id_ts = State()

async_lock = asyncio.Lock()
waiting_users = 0
user_data = {}

@st.cache_resource
def load_whisper():
    return whisper.load_model("small")

model_local = load_whisper()

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

# ==========================================
# 1. START VA YORDAM QISMI
# ==========================================
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    is_new = update_user(m.from_user, added_audio=False)
    
    if is_new:
        try:
            u_link = f"@{m.from_user.username}" if m.from_user.username else "Mavjud emas"
            msg = get_new_user_admin_msg(m.from_user.full_name, m.from_user.id, u_link, get_uz_time())
            await bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
        except Exception: 
            pass

    welcome = get_welcome_msg(m.from_user.first_name)
    await m.answer(welcome, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")

@dp.message(F.text == "ℹ️ Yordam")
async def help_handler(m: types.Message):
    await m.answer(HELP_MSG, parse_mode="HTML")


# ==========================================
# 2. BOG'LANISH VA ADMIN JAVOBI
# ==========================================
@dp.message(F.text == "👨‍💻 Bog'lanish")
async def contact_h(m: types.Message):
    await m.answer(
        "👨‍💻 Admin bilan bog'lanish uchun quyidagi tugmani bosing va xabaringizni yozing:", 
        reply_markup=get_contact_kb(), 
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "msg_to_admin")
async def feedback_init(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_contact_msg)
    await call.message.answer(
        "📝 <b>Xabaringizni yozing:</b>\n<i>(Bu xabar to'g'ridan-to'g'ri adminga boradi)</i>", 
        parse_mode="HTML"
    )
    await call.answer()

@dp.message(UserStates.waiting_for_contact_msg)
async def feedback_done(m: types.Message, state: FSMContext):
    await state.clear()
    admin_msg = (
        f"📩 <b>YANGI MUROJAAT:</b>\n"
        f"👤 Kimdan: {m.from_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{m.from_user.id}</code>\n"
        f"📝 Xabar:\n{m.text}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
        await m.answer("✅ <b>Xabaringiz adminga yetkazildi!</b> Javobni kuting.", parse_mode="HTML")
    except Exception:
        await m.answer("❌ Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")

@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply_to_user(m: types.Message):
    orig_text = m.reply_to_message.text
    if not orig_text: 
        return
    match = re.search(r"ID:\s*(\d+)", orig_text)
    if match:
        target_id = int(match.group(1))
        try:
            await bot.send_message(target_id, f"👨‍💻 <b>Admin javobi:</b>\n\n{m.text}", parse_mode="HTML")
            await m.answer("✅ Javobingiz foydalanuvchiga muvaffaqiyatli yetkazildi.")
        except Exception as e:
            await m.answer(f"❌ Xatolik: Foydalanuvchi botni bloklagan bo'lishi mumkin. ({e})")


# ==========================================
# 3. AUDIO QABUL QILISH VA SOZLAMALAR
# ==========================================
@dp.message(F.audio | F.voice)
async def handle_audio_file(m: types.Message):
    file_id = m.audio.file_id if m.audio else m.voice.file_id
    file_size = m.audio.file_size if m.audio else m.voice.file_size

    if file_size > 20 * 1024 * 1024:
        await m.answer("❌ <b>Hajm juda katta!</b>\nIltimos, 20MB dan oshmaydigan audio yuboring.", parse_mode="HTML")
        return

    update_user(m.from_user, added_audio=True)
    u_tag = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
    
    audio_name = "Voice_Message"
    if m.audio and m.audio.file_name:
        audio_name = m.audio.file_name

    user_data[m.chat.id] = {
        'fid': file_id, 
        'mid': m.message_id, 
        'uname': u_tag, 
        'tr_lang': None, 
        'view': None, 
        'audio_name': audio_name
    }
    
    await m.answer(AUDIO_RECEIVED_MSG, reply_markup=get_tr_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tr_"))
async def set_translation_mode(call: types.CallbackQuery):
    user_data[call.message.chat.id]['tr_lang'] = call.data.replace("tr_", "")
    await call.message.edit_text(VIEW_MODE_MSG, reply_markup=get_split_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("v_"))
async def set_view_mode(call: types.CallbackQuery):
    user_data[call.message.chat.id]['view'] = call.data.replace("v_", "")
    await call.message.edit_text(FORMAT_MODE_MSG, reply_markup=get_format_kb(), parse_mode="HTML")


# =========================================================
# 4. ASOSIY PROTSESSOR (KESH TIZIMI VA RAM TOZALASH BILAN)
# =========================================================
@dp.callback_query(F.data.startswith("f_"))
async def run_analysis(call: types.CallbackQuery):
    global waiting_users
    chat_id = call.message.chat.id
    fmt = call.data.replace("f_", "")
    data = user_data.get(chat_id)
    
    if not data:
        await call.message.answer("❌ Ma'lumotlar topilmadi. Qaytadan audio yuboring.")
        return

    await call.message.delete()
    waiting_users += 1
    wait_msg = await call.message.answer(
        f"⏳ <b>Navbatdasiz: {waiting_users}-o'rin</b>\nAI ishga tushmoqda...", 
        parse_mode="HTML"
    )

    segments = None
    res = None
    html_parts = []
    txt_parts = []

    async with async_lock:
        a_path, r_path = f"aud_{chat_id}.mp3", f"res_{chat_id}.txt"
        
        async def update_live_bar(percent, status_text):
            blocks = int(percent // 10)
            bar = "🟩" * blocks + "⬜" * (10 - blocks)
            icon = "🔄" if percent < 50 else "🧠" if percent < 90 else "✅"
            try: 
                await wait_msg.edit_text(
                    f"🚀 <b>Jarayon holati:</b> {status_text}\n"
                    f"<code>{bar}</code> {percent}%\n\n"
                    f"{icon} <i>Suxandon AI tahlil qilmoqda...</i>", 
                    parse_mode="HTML"
                )
            except Exception: 
                pass

        try:
            await update_live_bar(10, "Audio yuklanmoqda...")
            f_info = await bot.get_file(data['fid'])
            await bot.download_file(f_info.file_path, a_path)

            await update_live_bar(20, "Baza tekshirilmoqda...")
            file_hash = get_file_hash(a_path)
            cached_segments = get_audio_cache(file_hash)

            if cached_segments:
                await update_live_bar(40, "⚡ Baza ichidan tayyor matn topildi! (Vaqt tejaldi)")
                segments = cached_segments
            else:
                await update_live_bar(30, "AI tahlil qilmoqda (Bu biroz vaqt oladi)...")
                res = await asyncio.to_thread(model_local.transcribe, a_path, language="uz")
                segments = [{'start': float(s['start']), 'end': float(s['end']), 'text': str(s['text'])} for s in res['segments']]
                save_audio_cache(file_hash, segments)
                await update_live_bar(40, "Nutq muvaffaqiyatli o'qildi.")

            tr_mode = data['tr_lang']
            total = len(segments)
            last_p = 40

            for i, seg in enumerate(segments):
                raw = seg['text'].strip()
                if not raw: 
                    continue
                
                stamp = format_time_stamp(seg['start'])
                tr_html, tr_txt = "", ""
                
                if tr_mode != "orig":
                    t_lang = "uz" if "uz" in tr_mode else tr_mode
                    try:
                        translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=t_lang).translate, raw)
                        if tr_mode == "uz_only": 
                            raw = translated 
                        else:
                            tr_html = f"\n└ <i>{clean_text(translated)}</i>"
                            tr_txt = f"\n   ({translated})"
                    except Exception: 
                        pass
                
                if data['view'] == "split":
                    html_parts.append(f"<b>{stamp}</b> {clean_text(raw)}{tr_html}")
                    txt_parts.append(f"{stamp} {raw}{tr_txt}")
                else:
                    html_parts.append(f"{clean_text(raw)}{tr_html}")
                    txt_parts.append(f"{raw}{tr_txt}")

                cur_p = 40 + int((i / total) * 50)
                if cur_p >= last_p + 10:
                    await update_live_bar(cur_p, "Akademik tarjima tayyorlanmoqda...")
                    last_p = (cur_p // 10) * 10

            await update_live_bar(95, "Natija shakllantirilmoqda...")
            bot_me = await bot.get_me()
            
            # messages.py dan pechatlarni olamiz
            pechat_txt = get_pechat_text(data['uname'], bot_me.username, get_uz_time())
            pechat_html = get_pechat_html(data['uname'], bot_me.username, get_uz_time())
            
            full_txt_to_save = "\n\n".join(txt_parts) + pechat_txt
            save_transcript(chat_id, full_txt_to_save, audio_name=data.get('audio_name', 'Audio'))
            
            update_stats('audio', fmt)

            if fmt == "txt":
                with open(r_path, "w", encoding="utf-8") as f: 
                    f.write(full_txt_to_save)
                await call.message.answer_document(
                    types.FSInputFile(r_path), 
                    caption=pechat_html, 
                    reply_to_message_id=data['mid'], 
                    parse_mode="HTML"
                )
            else:
                full_html = "\n\n".join(html_parts) + pechat_html
                chunks = split_html_text(full_html)
                for chunk in chunks:
                    try: 
                        await call.message.answer(chunk, parse_mode="HTML", reply_to_message_id=data['mid'])
                        await asyncio.sleep(0.8)
                    except Exception: 
                        await call.message.answer(clean_text(chunk), reply_to_message_id=data['mid'])

            await update_live_bar(100, "Tayyor! ✅")
            await asyncio.sleep(1.5)
            await wait_msg.delete()

        except Exception as e:
            await call.message.answer(f"❌ Xatolik yuz berdi: {e}")
        finally:
            delete_temp_files(a_path, r_path)
            waiting_users -= 1
            if chat_id in user_data: 
                del user_data[chat_id]
                
            del segments
            del res
            del html_parts
            del txt_parts
            gc.collect() 


# ==========================================
# 5. ADMIN PANEL VA BROADCAST
# ==========================================
@dp.message(F.text == "🔑 Admin Panel", F.chat.id == ADMIN_ID)
async def admin_main(m: types.Message):
    await m.answer("🛠 <b>Admin Boshqaruv Paneli</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_stats")
async def stats_cb(call: types.CallbackQuery):
    s = get_stats()
    msg = (
        f"📊 <b>Statistika:</b>\n\n"
        f"🔄 Jami tahlillar: {s.get('total_processed', 0)}\n"
        f"🎙 Audiodan: {s.get('audio', 0)}\n"
        f"📄 TXT format: {s.get('format_txt', 0)}\n"
        f"💬 Chat format: {s.get('format_chat', 0)}"
    )
    await call.message.answer(msg, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_list_menu")
async def list_menu_cb(call: types.CallbackQuery):
    await call.message.edit_text("📋 <b>Ro'yxat formatini tanlang:</b>", reply_markup=get_list_format_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("list_"))
async def generate_user_list(call: types.CallbackQuery):
    format_type = call.data.replace("list_", "")
    users = get_all_users()
    await call.message.delete()
    
    if not users:
        await call.message.answer("❌ Hozircha foydalanuvchilar yo'q.")
        return

    msg_parts = []
    for i, u in enumerate(users, 1):
        name = u.get('name', 'Nomsiz')
        uid = u.get('id', 'Noma\'lum')
        a_count = u.get('audio_count', 0)
        a_time = u.get('last_audio_time', 'Yubormagan')
        joined = u.get('joined_at', 'Noma\'lum')
        
        msg_parts.append(
            f"<b>{i}. {name}</b> (ID: <code>{uid}</code>)\n"
            f"   📅 Qo'shilgan: {joined}\n"
            f"   🎧 Audiolar: {a_count} ta | ⏳ Oxirgi: {a_time}\n"
        )
        
    full_text = f"📋 <b>FOYDALANUVCHILAR RO'YXATI ({len(users)} ta):</b>\n\n" + "\n".join(msg_parts)

    if format_type == "txt":
        file_name = "user_list.txt"
        with open(file_name, "w", encoding="utf-8") as f: 
            f.write(clean_text(full_text).replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
        await call.message.answer_document(types.FSInputFile(file_name), caption="📋 Foydalanuvchilar ro'yxati.")
        os.remove(file_name)
    else:
        chunks = split_html_text(full_text)
        for chunk in chunks:
            await call.message.answer(chunk, parse_mode="HTML")
            await asyncio.sleep(0.5)

@dp.callback_query(F.data == "adm_bc")
async def bc_cb(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📢 <b>Broadcast:</b> Hammaga yuboriladigan xabarni tashlang:")
    await state.set_state(AdminStates.waiting_for_bc)
    await call.answer()

@dp.message(AdminStates.waiting_for_bc)
async def bc_process(m: types.Message, state: FSMContext):
    await state.clear()
    users = get_all_users()
    c = 0
    prog = await m.answer(f"⏳ Tarqatish boshlandi... (0/{len(users)})")
    
    for u in users:
        uid = u.get('id')
        if uid:
            try:
                await bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=m.message_id)
                c += 1
                if c % 20 == 0: 
                    await prog.edit_text(f"⏳ Tarqatilmoqda... ({c}/{len(users)})")
                await asyncio.sleep(0.05)
            except Exception: 
                pass
    await prog.edit_text(f"✅ Xabar {c} ta foydalanuvchiga yetkazildi.")


# ==========================================
# 6. TRANSKRIPTLARNI QIDIRISH VA PAGINATION
# ==========================================
@dp.callback_query(F.data == "adm_view_ts")
async def ask_ts_user_id(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🔍 <b>Qidiruv:</b> Tahlilni ko'rish uchun foydalanuvchi ID raqamini yuboring:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id_ts)
    await call.answer()

@dp.message(AdminStates.waiting_for_user_id_ts)
async def process_ts_search(m: types.Message, state: FSMContext):
    await state.clear()
    uid = m.text.strip()
    msg = await m.answer("⏳ Qidirilmoqda...")
    transcripts = get_user_transcripts(uid)
    
    if not transcripts:
        await msg.edit_text(f"❌ <code>{uid}</code> ID bo'yicha hech qanday matn topilmadi.", parse_mode="HTML")
        return
        
    await show_transcript_page(msg, uid, transcripts, page=1)

async def show_transcript_page(message: types.Message, user_id, transcripts, page):
    items_per_page = 5
    total_pages = (len(transcripts) + items_per_page - 1) // items_per_page
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_items = transcripts[start_idx:end_idx]
    
    text = (
        f"📂 <b>Foydalanuvchi:</b> <code>{user_id}</code>\n"
        f"📊 <b>Jami audiolari:</b> {len(transcripts)} ta\n"
        f"📄 <b>Sahifa:</b> {page}/{total_pages}\n\n"
    )
    
    for idx, item in enumerate(page_items):
        name = item.get('audio_name', 'Nomsiz')
        date = item.get('created_at', 'Vaqt noma\'lum')
        text += f"<b>[{idx+1}]</b> 🎵 {name}\n   🕒 {date}\n\n"
        
    text += "👇 <i>Qaysi matnni ko'rmoqchisiz? Raqamni tanlang:</i>"
    kb = get_transcripts_pagination_kb(user_id, page, total_pages, page_items)
    
    try: 
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception: 
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("ts_pg_"))
async def ts_pagination_handler(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid, page = parts[2], int(parts[3])
    transcripts = get_user_transcripts(uid)
    await show_transcript_page(call.message, uid, transcripts, page)
    await call.answer()

@dp.callback_query(F.data.startswith("ts_sel_"))
async def ts_select_handler(call: types.CallbackQuery):
    doc_id = call.data.replace("ts_sel_", "")
    await call.message.edit_text("💾 <b>Matnni qaysi formatda olmoqchisiz?</b>", reply_markup=get_transcript_format_kb(doc_id), parse_mode="HTML")

@dp.callback_query(F.data.startswith("ts_fmt_"))
async def ts_send_handler(call: types.CallbackQuery):
    parts = call.data.split("_")
    fmt, doc_id = parts[2], parts[3]
    await call.message.delete()
    
    ts_data = get_transcript_by_id(doc_id)
    if not ts_data:
        await call.message.answer("❌ Bu matn bazadan topilmadi.")
        return
        
    full_text = ts_data.get('text', 'Matn bo\'sh')
    
    if fmt == "txt":
        file_path = f"admin_view_{doc_id}.txt"
        with open(file_path, "w", encoding="utf-8") as f: 
            f.write(full_text)
        await call.message.answer_document(types.FSInputFile(file_path), caption="📂 So'ralgan tahlil.")
        os.remove(file_path)
    else:
        chunks = split_html_text(clean_text(full_text))
        for chunk in chunks:
            await call.message.answer(chunk, parse_mode="HTML")
            await asyncio.sleep(0.5)

# ==========================================
# 7. ADASHGANLAR UCHUN YO'RIQNOMA
# ==========================================
@dp.message(F.text == "🌐 Saytga kirish")
async def web_h(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Saytni ochish", url="https://shodlikai.github.io/new_3/dastur.html")
    await m.answer("Veb-sahifaga o'tish:", reply_markup=kb.as_markup())

@dp.message()
async def unknown_handler(m: types.Message):
    if m.text in ["🎧 Tahlil boshlash", "🌐 Saytga kirish", "👨‍💻 Bog'lanish", "ℹ️ Yordam", "🔑 Admin Panel"]: 
        return
        
    guide = get_guide_msg(m.from_user.first_name)
    await m.answer(guide, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")
