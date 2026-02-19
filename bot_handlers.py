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
    st.error(f"Botni ishga tushirishda xatolik: {e}")
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

# --- 1. START VA YORDAM ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    update_user(m.from_user)
    try:
        u_link = f"@{m.from_user.username}" if m.from_user.username else "Mavjud emas"
        msg = f"🆕 <b>Yangi foydalanuvchi:</b> {m.from_user.full_name} (ID: {m.from_user.id})"
        await bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
    except: pass

    welcome = (
        f"👋 <b>Assalomu alaykum, {m.from_user.first_name}!</b>\n\n"
        f"🎙 <b>Suxandon AI</b> botiga xush kelibsiz. Men audio materiallarni akademik darajada tahlil qilaman.\n\n"
        "🚀 <b>Ishni boshlash uchun ovozli xabar yoki audio fayl yuboring!</b>"
    )
    await m.answer(welcome, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")

@dp.message(F.text == "ℹ️ Yordam")
async def help_handler(m: types.Message):
    help_text = (
        "📚 <b>Botdan qanday foydalaniladi?</b>\n\n"
        "1. Menga audio fayl yuboring.\n"
        "2. <b>Tarjima turi:</b> Ovozni shunchaki matnga aylantirish yoki boshqa tilga tarjima qilishni tanlang.\n"
        "3. <b>Ko'rinish:</b> Matn vaqtlar bilan bo'lingan bo'lsinmi yoki yaxlit kitob ko'rinishidami?\n"
        "4. <b>Format:</b> Natijani chatda o'qish qulaymi yoki .txt hujjat qilib beraymi?\n\n"
        "⚠️ <i>Fayl hajmi 20MB dan oshmasligi kerak.</i>"
    )
    await m.answer(help_text, parse_mode="HTML")

# --- 2. AUDIO QABUL QILISH ---
@dp.message(F.audio | F.voice)
async def handle_audio_file(m: types.Message):
    file_id = m.audio.file_id if m.audio else m.voice.file_id
    file_size = m.audio.file_size if m.audio else m.voice.file_size

    if file_size > 20 * 1024 * 1024:
        await m.answer("❌ <b>Hajm juda katta!</b>\nIltimos, 20MB dan oshmaydigan audio yuboring.", parse_mode="HTML")
        return

    u_tag = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
    user_data[m.chat.id] = {
        'fid': file_id, 
        'mid': m.message_id, 
        'uname': u_tag, 
        'tr_lang': None, 
        'view': None
    }
    
    explanation = (
        "🌍 <b>Audio qabul qilindi! Endi tarjima usulini tanlang.</b>\n\n"
        "Bu bosqichda siz audio qaysi tilda ekanligidan qat'i nazar, uni o'zbek, rus yoki ingliz tillariga tarjima qilishni belgilaysiz.\n\n"
        "🔹 <b>Original:</b> Faqat ovozdagi gaplar o'z tilida chiqadi.\n"
        "🔹 <b>O'zbekchaga:</b> Ham ovozdagi gap, ham uning o'zbekcha akademik tarjimasi birga chiqadi.\n"
        "🔹 <b>Faqat O'zbekcha:</b> Chet tilidagi audio bo'lsa, originalni o'chirib, faqat tarjimani o'zini yozadi."
    )
    await m.answer(explanation, reply_markup=get_tr_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tr_"))
async def set_translation_mode(call: types.CallbackQuery):
    user_data[call.message.chat.id]['tr_lang'] = call.data.replace("tr_", "")
    
    view_explanation = (
        "📄 <b>Ajoyib! Endi matn ko'rinishini tanlang.</b>\n\n"
        "Sizga matn qanday tartibda ko'rsatilishini tanlang:\n\n"
        "⏱ <b>Time Split:</b> Matnni sekundlar (masalan [00:15]) bo'yicha bo'laklab beradi. Bu darslar yoki intervyular uchun juda qulay.\n"
        "📖 <b>Full Context:</b> Matnni vaqtlarisiz, yaxlit kitobdek yoki xatboshilardan iborat qilib beradi. O'qish uchun eng yaxshi format."
    )
    await call.message.edit_text(view_explanation, reply_markup=get_split_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("v_"))
async def set_view_mode(call: types.CallbackQuery):
    user_data[call.message.chat.id]['view'] = call.data.replace("v_", "")
    
    format_explanation = (
        "💾 <b>Oxirgi bosqich: Natijani qanday olishni tanlang.</b>\n\n"
        "Bu natija sizga qayerda va qanday ko'rinishda kelishini belgilaydi:\n\n"
        "📁 <b>TXT Fayl:</b> Bot sizga barcha matnni hujjat (.txt) ko'rinishida yuboradi. Uni telefoningizga saqlab olishingiz mumkin.\n"
        "💬 <b>Chat (Xabar):</b> Bot natijani to'g'ridan-to'g'ri shu yerga xabar ko'rinishida yuboradi. Agar matn juda uzun bo'lsa, u bir nechta xabarlarga bo'lib yuboriladi."
    )
    await call.message.edit_text(format_explanation, reply_markup=get_format_kb(), parse_mode="HTML")

# --- 3. ASOSIY PROTSESSOR (PROGRESS BAR BILAN) ---
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
    wait_msg = await call.message.answer(f"⏳ <b>Navbatdasiz: {waiting_users}-o'rin</b>\nAI hozir boshqa audio bilan band...", parse_mode="HTML")

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
                    f"{icon} <i>Suxandon AI akademik darajada ishlamoqda...</i>", 
                    parse_mode="HTML"
                )
            except: pass

        try:
            # Bosqich 1: Yuklash (10%)
            await update_live_bar(10, "Audio yuklanmoqda...")
            f_info = await bot.get_file(data['fid'])
            await bot.download_file(f_info.file_path, a_path)

            # Bosqich 2: Whisper AI (10% -> 40%)
            await update_live_bar(30, "AI ovozdagi so'zlarni tanimoqda...")
            res = await asyncio.to_thread(model_local.transcribe, a_path)
            segments = res['segments']
            await update_live_bar(40, "Nutq muvaffaqiyatli o'qildi.")

            # Bosqich 3: Tarjima va Tahlil (40% -> 90%)
            tr_mode = data['tr_lang']
            html_parts, txt_parts = [], []
            total = len(segments)
            last_p = 40

            for i, seg in enumerate(segments):
                raw = seg['text'].strip()
                if not raw: continue
                
                stamp = format_time_stamp(seg['start'])
                tr_html, tr_txt = "", ""
                
                if tr_mode != "orig":
                    t_lang = "uz" if "uz" in tr_mode else tr_mode
                    try:
                        translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=t_lang).translate, raw)
                        if tr_mode == "uz_only":
                            raw = translated # Faqat tarjima rejimi
                        else:
                            tr_html = f"\n└ <i>{clean_text(translated)}</i>"
                            tr_txt = f"\n   ({translated})"
                    except: pass
                
                if data['view'] == "split":
                    html_parts.append(f"<b>{stamp}</b> {clean_text(raw)}{tr_html}")
                    txt_parts.append(f"{stamp} {raw}{tr_txt}")
                else:
                    html_parts.append(f"{clean_text(raw)}{tr_html}")
                    txt_parts.append(f"{raw}{tr_txt}")

                # Progressni har 10% da yangilash
                cur_p = 40 + int((i / total) * 50)
                if cur_p >= last_p + 10:
                    await update_live_bar(cur_p, "Akademik tarjima tayyorlanmoqda...")
                    last_p = (cur_p // 10) * 10

            # Bosqich 4: Yakunlash
            await update_live_bar(95, "Natija shakllantirilmoqda...")
            bot_me = await bot.get_me()
            footer = f"\n\n---\n👤 {data['uname']}\n🤖 @{bot_me.username}\n⏰ {get_uz_time()}"
            
            update_stats('audio', fmt)

            if fmt == "txt":
                with open(r_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(txt_parts) + footer.replace("<b>","").replace("</b>",""))
                await call.message.answer_document(
                    types.FSInputFile(r_path), 
                    caption="✅ <b>Akademik tahlil fayl ko'rinishida tayyor!</b>", 
                    reply_to_message_id=data['mid'], # ORIGINAL AUDIOGA JAVOB
                    parse_mode="HTML"
                )
            else:
                full_html = "\n\n".join(html_parts) + footer
                chunks = split_html_text(full_html)
                for chunk in chunks:
                    try:
                        await call.message.answer(
                            chunk, 
                            parse_mode="HTML", 
                            reply_to_message_id=data['mid'] # ORIGINAL AUDIOGA JAVOB
                        )
                        await asyncio.sleep(0.8)
                    except:
                        await call.message.answer(clean_text(chunk), reply_to_message_id=data['mid'])

            await update_live_bar(100, "Tayyor! ✅")
            await asyncio.sleep(1.5)
            await wait_msg.delete()

        except Exception as e:
            await call.message.answer(f"❌ Xatolik: {e}")
        finally:
            delete_temp_files(a_path, r_path)
            waiting_users -= 1
            if chat_id in user_data: del user_data[chat_id]

# --- 4. ADMIN PANEL (TO'LIQ) ---
@dp.message(F.text == "🔑 Admin Panel", F.chat.id == ADMIN_ID)
async def admin_main(m: types.Message):
    await m.answer("🛠 <b>Admin Boshqaruv Paneli</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_stats")
async def stats_cb(call: types.CallbackQuery):
    db = load_db(); s = db['stats']
    msg = f"📊 <b>Statistika:</b>\n\nUserlar: {len(db['users'])}\nIshlovlar: {s['total_processed']}"
    await call.message.answer(msg, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_list")
async def list_cb(call: types.CallbackQuery):
    db = load_db(); users = db['users']
    msg = "📋 <b>Userlar ro'yxati:</b>\n\n"
    for i, (uid, u) in enumerate(list(users.items())[:50], 1):
        msg += f"{i}. {u['name']} (ID: {uid})\n"
    for chunk in split_html_text(msg):
        await call.message.answer(chunk, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_bc")
async def bc_cb(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📢 Xabarni yuboring:")
    await state.set_state(AdminStates.waiting_for_bc)
    await call.answer()

@dp.message(AdminStates.waiting_for_bc)
async def bc_process(m: types.Message, state: FSMContext):
    await state.clear()
    db = load_db(); users = db['users']; c = 0
    for uid in users:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=m.message_id)
            c += 1; await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ {c} userga yuborildi.")

# --- 5. BOG'LANISH VA YO'RIQNOMA ---
@dp.message(F.text == "👨‍💻 Bog'lanish")
async def contact_h(m: types.Message):
    await m.answer("Admin bilan bog'lanish uchun xabar qoldiring:", reply_markup=get_contact_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "msg_to_admin")
async def feedback_init(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_contact_msg)
    await call.message.answer("📝 Xabaringizni yozing:")
    await call.answer()

@dp.message(UserStates.waiting_for_contact_msg)
async def feedback_done(m: types.Message, state: FSMContext):
    await state.clear()
    await bot.send_message(ADMIN_ID, f"📩 <b>Murojaat:</b>\n👤 {m.from_user.full_name}\n📝 {m.text}", parse_mode="HTML")
    await m.answer("✅ Xabaringiz yetkazildi.")

@dp.message(F.text == "🌐 Saytga kirish")
async def web_h(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Saytni ochish", url="https://shodlikai.github.io/new_3/dastur.html")
    await m.answer("Veb-sahifaga o'tish:", reply_markup=kb.as_markup())

# --- 6. ADASHGANLAR UCHUN YO'RIQNOMA (MUKAMMAL) ---
@dp.message()
async def unknown_handler(m: types.Message):
    if m.text in ["🎧 Tahlil boshlash", "🌐 Saytga kirish", "👨‍💻 Bog'lanish", "ℹ️ Yordam", "🔑 Admin Panel"]:
        return

    guide = (
        f"👋 <b>Salom, {m.from_user.first_name}! Suxandon AI botiga xush kelibsiz.</b>\n\n"
        "Siz yozgan matnli xabarni tushunmadim, chunki mening vazifam audio materiallarni tahlil qilishdir.\n\n"
        "🛠 <b>Botdan qanday foydalanish kerak?</b>\n"
        "1️⃣ Menga ovozli xabar (voice) yoki audio fayl (mp3) yuboring.\n"
        "2️⃣ Bot so'ragan tarjima turi, matn ko'rinishi va formatini tanlang.\n"
        "3️⃣ Men uni akademik darajada matnga aylantirib, audioingizga <b>javob (reply)</b> sifatida qaytaraman.\n\n"
        "💡 <i>Menyudagi tugmalardan foydalaning yoki hoziroq audio yuboring!</i>"
    )
    await m.answer(guide, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")
                       
