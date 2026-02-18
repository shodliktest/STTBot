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
    st.error(f"Token xatosi: {e}")
    st.stop()

# --- FSM STATES ---
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
    # Eng yaxshi natija uchun 'base' ishlatilgan
    return whisper.load_model("base")

model_local = load_whisper()

# --- 1. START HANDLER ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    update_user(m.from_user)
    
    # Adminga xabar
    try:
        u_link = f"@{m.from_user.username}" if m.from_user.username else "Username yo'q"
        admin_info = (
            f"🆕 <b>YANGI FOYDALANUVCHI:</b>\n"
            f"👤 Ism: {m.from_user.full_name}\n"
            f"🆔 ID: <code>{m.from_user.id}</code>\n"
            f"🔗 Link: {u_link}"
        )
        await bot.send_message(ADMIN_ID, admin_info, parse_mode="HTML")
    except:
        pass

    welcome_text = (
        f"👋 <b>Assalomu alaykum, {m.from_user.first_name}!</b>\n\n"
        f"🎙 <b>Suxandon AI</b> botiga xush kelibsiz.\n"
        "Men audio fayllarni matnga aylantirib, ularni akademik darajada tarjima qilib bera olaman.\n\n"
        "🚀 <b>Ishni boshlash uchun menga audio fayl yoki ovozli xabar yuboring!</b>"
    )
    await m.answer(welcome_text, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")

# --- 2. ASOSIY TUGMALAR ---
@dp.message(F.text == "ℹ️ Yordam")
async def help_handler(m: types.Message):
    help_txt = (
        "📚 <b>BOTDAN FOYDALANISH YO'RIQNOMASI</b>\n\n"
        "1️⃣ <b>Audio yuboring:</b> Botga ovozli xabar (voice) yoki MP3 fayl yuboring.\n"
        "2️⃣ <b>Tilni tanlang:</b> Matn qaysi tilga tarjima qilinishini belgilang.\n"
        "3️⃣ <b>Ko'rinish:</b> Matn vaqtlar bilan (Time Split) yoki yaxlit (Full) bo'lishini tanlang.\n"
        "4️⃣ <b>Format:</b> Natijani xabar ko'rinishida yoki .txt faylida oling.\n\n"
        "⚠️ <b>Cheklovlar:</b>\n"
        "- Maksimal fayl hajmi: 20 MB\n"
        "- Davomiyligi: 30-60 daqiqagacha (tavsiya etiladi)"
    )
    await m.answer(help_txt, parse_mode="HTML")

@dp.message(F.text == "👨‍💻 Bog'lanish")
async def contact_handler(m: types.Message):
    await m.answer(
        "👨‍💻 <b>Admin bilan bog'lanish uchun pastdagi tugmani bosing:</b>",
        reply_markup=get_contact_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "msg_to_admin")
async def start_feedback(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_contact_msg)
    await call.message.answer("📝 <b>Xabaringizni yozing, men uni adminga yetkazaman:</b>", parse_mode="HTML")
    await call.answer()

@dp.message(UserStates.waiting_for_contact_msg)
async def process_feedback(m: types.Message, state: FSMContext):
    await state.clear()
    try:
        u_info = f"👤 {m.from_user.full_name} (ID: {m.from_user.id})"
        await bot.send_message(ADMIN_ID, f"📩 <b>YANGI MUROJAAT:</b>\n\n{u_info}\n📝 Xabar: {m.text}", parse_mode="HTML")
        await m.answer("✅ <b>Xabaringiz yuborildi!</b>", parse_mode="HTML")
    except:
        await m.answer("❌ Xabarni yuborishda xatolik yuz berdi.")

# --- 3. ADMIN REPLY MANTIQI ---
@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(m: types.Message):
    orig = m.reply_to_message.text
    match = re.search(r"ID: (\d+)", orig)
    if match:
        target_id = int(match.group(1))
        try:
            await bot.send_message(target_id, f"💬 <b>Admin javobi:</b>\n\n{m.text}", parse_mode="HTML")
            await m.answer("✅ Javob foydalanuvchiga yetkazildi.")
        except:
            await m.answer("❌ Foydalanuvchi botni bloklagan bo'lishi mumkin.")

# --- 4. AUDIO QABUL QILISH ---
@dp.message(F.audio | F.voice)
async def catch_audio(m: types.Message):
    file_id = m.audio.file_id if m.audio else m.voice.file_id
    file_size = m.audio.file_size if m.audio else m.voice.file_size

    if file_size > 20 * 1024 * 1024:
        await m.answer("❌ <b>Fayl hajmi juda katta (Max: 20MB).</b>", parse_mode="HTML")
        return

    u_tag = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
    user_data[m.chat.id] = {
        'fid': file_id, 
        'uname': u_tag, 
        'tr_lang': None, 
        'view': None
    }
    
    await m.answer("🌍 <b>Audio qabul qilindi. Tarjima tilini tanlang:</b>", reply_markup=get_tr_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tr_"))
async def set_translation(call: types.CallbackQuery):
    user_data[call.message.chat.id]['tr_lang'] = call.data.replace("tr_", "")
    await call.message.edit_text("📄 <b>Matn ko'rinishini tanlang:</b>", reply_markup=get_split_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("v_"))
async def set_view(call: types.CallbackQuery):
    user_data[call.message.chat.id]['view'] = call.data.replace("v_", "")
    await call.message.edit_text("💾 <b>Natijani qaysi formatda olmoqchisiz?</b>", reply_markup=get_format_kb(), parse_mode="HTML")

# --- 5. ASOSIY PROCESSOR (TO'LIQ VA YANGILANGAN) ---
@dp.callback_query(F.data.startswith("f_"))
async def process_final(call: types.CallbackQuery):
    global waiting_users
    chat_id = call.message.chat.id
    fmt = call.data.replace("f_", "")
    data = user_data.get(chat_id)
    
    if not data:
        await call.message.answer("❌ Ma'lumotlar topilmadi, qaytadan audio yuboring.")
        return

    await call.message.delete()
    waiting_users += 1
    wait_msg = await call.message.answer(f"⏳ <b>Siz navbatdasiz: {waiting_users}-o'rin</b>\nIltimos, kuting...", parse_mode="HTML")

    async with async_lock:
        a_path = f"tmp_{chat_id}.mp3"
        r_path = f"res_{chat_id}.txt"
        
        try:
            # 1. Yuklab olish
            await wait_msg.edit_text("📥 <b>Fayl serverga yuklanmoqda...</b>", parse_mode="HTML")
            f_info = await bot.get_file(data['fid'])
            await bot.download_file(f_info.file_path, a_path)

            # 2. Transkripsiya
            await wait_msg.edit_text("🧠 <b>AI nutqni matnga aylantirmoqda...</b>", parse_mode="HTML")
            result = await asyncio.to_thread(model_local.transcribe, a_path)
            segments = result.get('segments', [])

            # 3. Akademik Tarjima va Matn yig'ish
            tr_code = data['tr_lang'] if data['tr_lang'] != "orig" else None
            html_parts, txt_parts = [], []
            
            for i, seg in enumerate(segments):
                original = seg['text'].strip()
                if not original: continue
                
                final_line_html = ""
                final_line_txt = ""
                
                # Timestamp
                t_stamp = format_time_stamp(seg['start'])
                
                # Tarjima mantiqi (Akademik va qisqartirmasdan)
                if tr_code:
                    try:
                        translated = await asyncio.to_thread(
                            GoogleTranslator(source='auto', target=tr_code).translate, 
                            original
                        )
                        if data['view'] == "split":
                            final_line_html = f"<b>{t_stamp}</b> {clean_text(original)}\n└ <i>{clean_text(translated)}</i>"
                            final_line_txt = f"{t_stamp} {original}\n   ({translated})"
                        else:
                            final_line_html = f"{clean_text(original)} (<i>{clean_text(translated)}</i>)"
                            final_line_txt = f"{original} ({translated})"
                    except:
                        final_line_html = clean_text(original)
                        final_line_txt = original
                else:
                    # Tarjimasiz holat
                    if data['view'] == "split":
                        final_line_html = f"<b>{t_stamp}</b> {clean_text(original)}"
                        final_line_txt = f"{t_stamp} {original}"
                    else:
                        final_line_html = clean_text(original)
                        final_line_txt = original
                
                html_parts.append(final_line_html)
                txt_parts.append(final_line_txt)

                # Har 10 segmentda progressni ko'rsatish
                if i % 10 == 0:
                    await wait_msg.edit_text(f"⏳ <b>Tahlil ketmoqda: {int((i/len(segments))*100)}%</b>", parse_mode="HTML")

            # Yakuniy imzo
            bot_info = await bot.get_me()
            signature = f"\n\n---\n👤 {data['uname']}\n🤖 @{bot_info.username}\n⏰ {get_uz_time()}"
            
            # 4. Yuborish mantiqi
            update_stats('audio', fmt)

            if fmt == "txt":
                full_txt = "\n\n".join(txt_parts) + signature
                with open(r_path, "w", encoding="utf-8") as f:
                    f.write(full_txt)
                await call.message.answer_document(
                    types.FSInputFile(r_path), 
                    caption="✅ <b>Sizning akademik tahlilingiz tayyor!</b>", 
                    parse_mode="HTML"
                )
            else:
                # KO'P XABARLI YUBORISH (Yangi mantiq)
                full_html = "\n\n".join(html_parts) + signature
                chunks = split_html_text(full_html)
                
                for index, chunk in enumerate(chunks):
                    try:
                        await call.message.answer(chunk, parse_mode="HTML")
                        # Telegram Flood limitdan qochish uchun
                        await asyncio.sleep(0.7)
                    except:
                        # HTML xato bo'lsa, toza matnni yuborish
                        await call.message.answer(clean_text(chunk))

            await wait_msg.delete()

        except Exception as e:
            await call.message.answer(f"❌ <b>Xatolik yuz berdi:</b>\n{str(e)}", parse_mode="HTML")
        finally:
            delete_temp_files(a_path, r_path)
            waiting_users -= 1
            if chat_id in user_data:
                del user_data[chat_id]

# --- 6. ADMIN PANEL HANDLERLARI ---
@dp.message(F.text == "🔑 Admin Panel", F.chat.id == ADMIN_ID)
async def admin_main(m: types.Message):
    await m.answer("🛠 <b>Boshqaruv paneli:</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_stats")
async def admin_stats(call: types.CallbackQuery):
    db = load_db()
    s = db['stats']
    msg = (
        "📊 <b>BOT STATISTIKASI:</b>\n\n"
        f"👥 Jami userlar: {len(db['users'])}\n"
        f"🔄 Jami ishlovlar: {s['total_processed']}\n"
        f"🎙 Audiodan: {s['audio']}\n"
        f"📄 TXT format: {s['format_txt']}\n"
        f"💬 Chat format: {s['format_chat']}"
    )
    await call.message.answer(msg, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_list")
async def admin_user_list(call: types.CallbackQuery):
    db = load_db()
    users = db['users']
    text = "📋 <b>FOYDALANUVCHILAR:</b>\n\n"
    for i, (uid, u) in enumerate(list(users.items())[:50], 1):
        text += f"{i}. {u['name']} (ID: {uid})\n"
    
    # Ro'yxat uzun bo'lsa bo'lib yuborish
    for chunk in split_html_text(text):
        await call.message.answer(chunk, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "adm_bc")
async def admin_bc_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_bc)
    await call.message.answer("📢 <b>Broadcast:</b> Xabarni yuboring (rasm, matn, video bo'lishi mumkin).", parse_mode="HTML")
    await call.answer()

@dp.message(AdminStates.waiting_for_bc)
async def admin_bc_send(m: types.Message, state: FSMContext):
    await state.clear()
    db = load_db()
    users = db['users']
    count = 0
    prog_msg = await m.answer(f"⏳ Yuborish boshlandi: 0/{len(users)}")
    
    for uid in users:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=m.message_id)
            count += 1
            if count % 20 == 0:
                await prog_msg.edit_text(f"⏳ Yuborilmoqda: {count}/{len(users)}")
            await asyncio.sleep(0.05)
        except:
            pass
    await m.answer(f"✅ Xabar {count} kishiga muvaffaqiyatli yetkazildi.")

# --- 7. BOSHQA FUNKSIYALAR ---
@dp.message(F.text == "🌐 Saytga kirish")
async def web_link(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Saytni ochish", url="https://shodlikai.github.io/new_3/dastur.html")
    await m.answer("Suxandon AI veb-versiyasidan foydalanish uchun tugmani bosing:", reply_markup=kb.as_markup())

# --- 8. MUKAMMAL YO'RIQNOMA (ADASHIB YOZILGAN XABARLAR UCHUN) ---
@dp.message()
async def catch_all_unknown(m: types.Message):
    # Bu handler faqat tugmalarga tegishli bo'lmagan ixtiyoriy matnlarni ushlaydi
    if m.text in ["🎧 Tahlil boshlash", "🌐 Saytga kirish", "👨‍💻 Bog'lanish", "ℹ️ Yordam", "🔑 Admin Panel"]:
        return # Bular o'z handlerlariga ega

    guide = (
        f"👋 <b>Salom, {m.from_user.first_name}! Sizga qanday yordam bera olaman?</b>\n\n"
        "Men siz yozgan matnli xabarni tahlil qila olmayman. Mening asosiy vazifam — <b>Audio nutqni matnga aylantirish.</b>\n\n"
        "🚀 <b>Botdan foydalanish uchun:</b>\n"
        "1. Menga ovozli xabar (voice) yoki audio fayl (mp3) yuboring.\n"
        "2. Men uni avtomatik taniyman va sizdan qaysi tilga tarjima qilishni so'rayman.\n"
        "3. Akademik darajadagi tarjima va tahlilni qabul qilib olasiz.\n\n"
        "💡 <i>Hozirgi menyudan foydalanish uchun pastdagi tugmalarni bosing yoki audio tashlang!</i>"
    )
    await m.answer(guide, reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")
            
