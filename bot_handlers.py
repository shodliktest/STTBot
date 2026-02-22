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
from database import update_user, update_stats, get_all_users, get_stats
from utils import (
    get_uz_time, clean_text, delete_temp_files, 
    format_time_stamp, split_html_text
)
from keyboards import (
    get_main_menu, get_tr_kb, get_split_kb, get_format_kb, 
    get_admin_kb, get_list_format_kb, get_contact_kb
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
    # Firebase'ga qo'shish va yangi foydalanuvchi bo'lsa adminga to'liq xabar berish
    is_new = update_user(m.from_user, added_audio=False)
    
    if is_new:
        try:
            u_link = f"@{m.from_user.username}" if m.from_user.username else "Mavjud emas"
            msg = (
                f"🆕 <b>YANGI FOYDALANUVCHI QO'SHILDI:</b>\n\n"
                f"👤 <b>Ism:</b> {m.from_user.full_name}\n"
                f"🆔 <b>ID:</b> <code>{m.from_user.id}</code>\n"
                f"🔗 <b>Username:</b> {u_link}\n"
                f"⏰ <b>Vaqt:</b> {get_uz_time()}"
            )
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

# --- 2. ADMIN BILAN ALOQA (REPLY MANTIQI TO'LIQ TIKLANDI) ---
@dp.message(F.text == "👨‍💻 Bog'lanish")
async def contact_h(m: types.Message):
    await m.answer("👨‍💻 Admin bilan bog'lanish uchun quyidagi tugmani bosing va xabaringizni yozing:", reply_markup=get_contact_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "msg_to_admin")
async def feedback_init(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_contact_msg)
    await call.message.answer("📝 <b>Xabaringizni yozing:</b>\n<i>(Bu xabar to'g'ridan-to'g'ri adminga boradi va admin sizga bot orqali javob qaytara oladi)</i>", parse_mode="HTML")
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
    except Exception as e:
        await m.answer("❌ Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")

# ADMIN REPLY (Admin userga javob qaytarishi)
@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply_to_user(m: types.Message):
    original_text = m.reply_to_message.text
    if not original_text: return
    
    # ID ni matn ichidan qidirish (Murojaat xabaridagi formatdan)
    match = re.search(r"ID:\s*(\d+)", original_text)
    if match:
        target_user_id = int(match.group(1))
        try:
            await bot.send_message(
                target_user_id, 
                f"👨‍💻 <b>Admin javobi:</b>\n\n{m.text}", 
                parse_mode="HTML"
            )
            await m.answer("✅ Javobingiz foydalanuvchiga muvaffaqiyatli yetkazildi.")
        except Exception as e:
            await m.answer(f"❌ Xatolik: Foydalanuvchi botni bloklagan bo'lishi mumkin. ({e})")

# --- 3. AUDIO QABUL QILISH ---
@dp.message(F.audio | F.voice)
async def handle_audio_file(m: types.Message):
    file_id = m.audio.file_id if m.audio else m.voice.file_id
    file_size = m.audio.file_size if m.audio else m.voice.file_size

    if file_size > 20 * 1024 * 1024:
        await m.answer("❌ <b>Hajm juda katta!</b>\nIltimos, 20MB dan oshmaydigan audio yuboring.", parse_mode="HTML")
        return

    # Foydalanuvchining audio tashlaganini Firebase'da qayd etish
    update_user(m.from_user, added_audio=True)

    u_tag = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
    user_data[m.chat.id] = {
        'fid': file_id, 
        'mid': m.message_id, # REPLY UCHUN SAQLAYMIZ
        'uname': u_tag, 
        'tr_lang': None, 
        'view': None
    }
    
    explanation = (
        "🌍 <b>Audio qabul qilindi! Endi tarjima usulini tanlang.</b>\n\n"
        "🔹 <b>Original:</b> Faqat ovozdagi gaplar o'z tilida chiqadi.\n"
        "🔹 <b>O'zbekchaga:</b> Asl matn va uning tarjimasi birga.\n"
        "🔹 <b>Faqat O'zbekcha:</b> Asl matnni o'chirib, faqat tarjimani beradi."
    )
    await m.answer(explanation, reply_markup=get_tr_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tr_"))
async def set_translation_mode(call: types.CallbackQuery):
    user_data[call.message.chat.id]['tr_lang'] = call.data.replace("tr_", "")
    
    view_explanation = (
        "📄 <b>Matn ko'rinishini tanlang:</b>\n\n"
        "⏱ <b>Time Split:</b> Matnni sekundlar [00:15] bo'yicha bo'laklaydi.\n"
        "📖 <b>Full Context:</b> Matnni yaxlit kitobdek qilib beradi."
    )
    await call.message.edit_text(view_explanation, reply_markup=get_split_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("v_"))
async def set_view_mode(call: types.CallbackQuery):
    user_data[call.message.chat.id]['view'] = call.data.replace("v_", "")
    
    format_explanation = (
        "💾 <b>Natijani qanday olishni tanlang:</b>\n\n"
        "📁 <b>TXT Fayl:</b> Barcha matn hujjat (.txt) ko'rinishida keladi.\n"
        "💬 <b>Chat (Xabar):</b> Natija to'g'ridan-to'g'ri botga xabar bo'lib keladi."
    )
    await call.message.edit_text(format_explanation, reply_markup=get_format_kb(), parse_mode="HTML")

# --- 4. ASOSIY PROTSESSOR (PROGRESS BAR BILAN) ---
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
    wait_msg = await call.message.answer(f"⏳ <b>Navbatdasiz: {waiting_users}-o'rin</b>\nAI ishga tushmoqda...", parse_mode="HTML")

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
            except: pass

        try:
            # Bosqich 1: Yuklash
            await update_live_bar(10, "Audio yuklanmoqda...")
            f_info = await bot.get_file(data['fid'])
            await bot.download_file(f_info.file_path, a_path)

            # Bosqich 2: Whisper AI
            await update_live_bar(30, "AI ovozdagi so'zlarni tanimoqda...")
            res = await asyncio.to_thread(model_local.transcribe, a_path)
            segments = res['segments']
            await update_live_bar(40, "Nutq muvaffaqiyatli o'qildi.")

            # Bosqich 3: Tarjima
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
                            raw = translated 
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

                # Progress
                cur_p = 40 + int((i / total) * 50)
                if cur_p >= last_p + 10:
                    await update_live_bar(cur_p, "Akademik tarjima tayyorlanmoqda...")
                    last_p = (cur_p // 10) * 10

            # Bosqich 4: Yuborish
            await update_live_bar(95, "Natija shakllantirilmoqda...")
            bot_me = await bot.get_me()
            footer = f"\n\n---\n👤 Tayyorladi: {data['uname']}\n🤖 Bot: @{bot_me.username}\n⏰ Vaqt: {get_uz_time()}"
            
            update_stats('audio', fmt)

            if fmt == "txt":
                with open(r_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(txt_parts) + footer.replace("<b>","").replace("</b>",""))
                await call.message.answer_document(
                    types.FSInputFile(r_path), 
                    caption="✅ <b>Akademik tahlil tayyor!</b>", 
                    reply_to_message_id=data['mid'], 
                    parse_mode="HTML"
                )
            else:
                full_html = "\n\n".join(html_parts) + footer
                chunks = split_html_text(full_html)
                for chunk in chunks:
                    try:
                        await call.message.answer(chunk, parse_mode="HTML", reply_to_message_id=data['mid'])
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

# --- 5. ADMIN PANEL (YANGILANGAN MANTIQ) ---
@dp.message(F.text == "🔑 Admin Panel", F.chat.id == ADMIN_ID)
async def admin_main(m: types.Message):
    await m.answer("🛠 <b>Admin Boshqaruv Paneli</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_stats")
async def stats_cb(call: types.CallbackQuery):
    s = get_stats()
    msg = (
        f"📊 <b>Statistika:</b>\n\n"
        f"🔄 Jami ishlovlar: {s.get('total_processed', 0)}\n"
        f"🎙 Audiodan: {s.get('audio', 0)}\n"
        f"📄 TXT format: {s.get('format_txt', 0)}\n"
        f"💬 Chat format: {s.get('format_chat', 0)}"
    )
    await call.message.answer(msg, parse_mode="HTML")
    await call.answer()

# FORMAT SO'RASH QISMI
@dp.callback_query(F.data == "adm_list_menu")
async def list_menu_cb(call: types.CallbackQuery):
    await call.message.edit_text("📋 <b>Ro'yxatni qaysi formatda olmoqchisiz?</b>", reply_markup=get_list_format_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("list_"))
async def generate_user_list(call: types.CallbackQuery):
    format_type = call.data.replace("list_", "")
    users = get_all_users()
    await call.message.delete()
    
    if not users:
        await call.message.answer("❌ Hozircha foydalanuvchilar yo'q.")
        return

    # Matnni shakllantirish (Audio soni va vaqti bilan)
    msg_parts = []
    for i, u in enumerate(users, 1):
        name = u.get('name', 'Nomsiz')
        uid = u.get('id', 'Noma\'lum')
        a_count = u.get('audio_count', 0)
        a_time = u.get('last_audio_time', 'Yubormagan')
        
        line = f"<b>{i}. {name}</b> (ID: <code>{uid}</code>)\n   🎧 Audiolar: {a_count} ta | ⏳ Oxirgi marta: {a_time}\n"
        msg_parts.append(line)
        
    full_text = f"📋 <b>FOYDALANUVCHILAR RO'YXATI ({len(users)} ta):</b>\n\n" + "\n".join(msg_parts)

    if format_type == "txt":
        # TXT formatida yuborish
        file_name = "user_list.txt"
        clean_full_text = clean_text(full_text).replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(clean_full_text)
        await call.message.answer_document(types.FSInputFile(file_name), caption="📋 Barcha foydalanuvchilar ro'yxati.")
        os.remove(file_name)
    else:
        # Chat ko'rinishida yuborish (Bo'laklab)
        chunks = split_html_text(full_text)
        for chunk in chunks:
            await call.message.answer(chunk, parse_mode="HTML")
            await asyncio.sleep(0.5)

@dp.callback_query(F.data == "adm_bc")
async def bc_cb(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📢 <b>Broadcast:</b> Hammaga yuboriladigan xabarni (rasm, video, matn) tashlang:")
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
                if c % 20 == 0: await prog.edit_text(f"⏳ Tarqatilmoqda... ({c}/{len(users)})")
                await asyncio.sleep(0.05)
            except: pass
    await prog.edit_text(f"✅ Xabar {c} ta foydalanuvchiga yetkazildi.")

# --- 6. ADASHGANLAR UCHUN YO'RIQNOMA ---
@dp.message(F.text == "🌐 Saytga kirish")
async def web_h(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Saytni ochish", url="https://shodlikai.github.io/new_3/dastur.html")
    await m.answer("Veb-sahifaga o'tish:", reply_markup=kb.as_markup())

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
