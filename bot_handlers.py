from __future__ import annotations

import asyncio
import gc
import hashlib
import os
import re
from typing import Any

import streamlit as st
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import whisper
from deep_translator import GoogleTranslator

from config import BOT_TOKEN, ADMIN_ID, WHISPER_MODEL
from database import (
    update_user, update_stats, get_users_page, get_user_count, get_stats,
    get_user_transcripts, get_transcript_by_id, get_audio_index,
    save_audio_index, update_audio_status, increment_page_view,
)
from telegram_storage import TelegramStorage
from utils import get_uz_time, clean_text, delete_temp_files, format_time_stamp, split_html_text
from keyboards import (
    get_main_menu, get_tr_kb, get_split_kb, get_format_kb,
    get_admin_kb, get_list_format_kb, get_contact_kb,
    get_transcripts_pagination_kb, get_transcript_format_kb,
    get_user_list_pagination_kb,
)
from messages import (
    get_welcome_msg, get_guide_msg, get_new_user_admin_msg,
    get_pechat_text, get_pechat_html, HELP_MSG, AUDIO_RECEIVED_MSG,
    VIEW_MODE_MSG, FORMAT_MODE_MSG,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
storage = TelegramStorage(bot)


class UserStates(StatesGroup):
    waiting_for_contact_msg = State()


class AdminStates(StatesGroup):
    waiting_for_bc = State()
    waiting_for_user_id_ts = State()


# One processing job at a time: this is deliberate for Community Cloud RAM safety.
process_lock = asyncio.Lock()
waiting_users = 0
user_data: dict[int, dict[str, Any]] = {}


@st.cache_resource(show_spinner=False)
def load_whisper():
    """Lazy-load Whisper only when the first uncached audio needs it."""
    print(f"Loading Whisper model: {WHISPER_MODEL}")
    return whisper.load_model(WHISPER_MODEL)


def get_file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _html_from_segments(segments: list[dict], tr_mode: str, view: str):
    html_parts, txt_parts = [], []
    total = max(1, len(segments))
    for seg in segments:
        raw = str(seg.get("text", "")).strip()
        if not raw:
            continue
        stamp = format_time_stamp(float(seg.get("start", 0)))
        tr_html, tr_txt = "", ""
        if tr_mode != "orig":
            target = "uz" if "uz" in tr_mode else tr_mode
            try:
                translated = await_translate_sync(raw, target)
                if tr_mode == "uz_only":
                    raw = translated
                else:
                    tr_html = f"\n└ <i>{clean_text(translated)}</i>"
                    tr_txt = f"\n   ({translated})"
            except Exception:
                pass
        if view == "split":
            html_parts.append(f"<b>{stamp}</b> {clean_text(raw)}{tr_html}")
            txt_parts.append(f"{stamp} {raw}{tr_txt}")
        else:
            html_parts.append(f"{clean_text(raw)}{tr_html}")
            txt_parts.append(f"{raw}{tr_txt}")
    return html_parts, txt_parts


def await_translate_sync(text: str, target: str) -> str:
    return GoogleTranslator(source="auto", target=target).translate(text)


@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    try:
        is_new = await asyncio.to_thread(update_user, m.from_user, False)
        if is_new:
            try:
                u_link = f"@{m.from_user.username}" if m.from_user.username else "Mavjud emas"
                msg = get_new_user_admin_msg(m.from_user.full_name, m.from_user.id, u_link, get_uz_time())
                await bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
                await storage.save_json({
                    "schema_version": 1, "type": "user", "id": str(m.from_user.id),
                    "name": m.from_user.full_name, "username": u_link,
                    "created_at": get_uz_time(),
                }, f"user_{m.from_user.id}.json", "SHodlik AI USER BACKUP")
            except Exception as e:
                print(f"new user backup error: {e}")
        await m.answer(get_welcome_msg(m.from_user.first_name), reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")
    except Exception as e:
        await m.answer("❌ Server bazasiga ulanishda vaqtinchalik xatolik. Keyinroq urinib ko'ring.")
        print(f"start error: {e}")


@dp.message(F.text == "ℹ️ Yordam")
async def help_handler(m: types.Message):
    await m.answer(HELP_MSG, parse_mode="HTML")


@dp.message(F.text == "👨‍💻 Bog'lanish")
async def contact_h(m: types.Message):
    await m.answer("👨‍💻 Admin bilan bog'lanish uchun tugmani bosing:", reply_markup=get_contact_kb(), parse_mode="HTML")


@dp.callback_query(F.data == "msg_to_admin")
async def feedback_init(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_contact_msg)
    await call.message.answer("📝 <b>Xabaringizni yozing:</b>", parse_mode="HTML")
    await call.answer()


@dp.message(UserStates.waiting_for_contact_msg)
async def feedback_done(m: types.Message, state: FSMContext):
    await state.clear()
    text = m.text or "(matn emas)"
    admin_msg = (
        f"📩 <b>YANGI MUROJAAT:</b>\n\n"
        f"👤 Kimdan: {clean_text(m.from_user.full_name)}\n"
        f"🆔 <b>ID:</b> <code>{m.from_user.id}</code>\n"
        f"📝 Xabar:\n{clean_text(text)}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
        await m.answer("✅ Xabaringiz adminga yetkazildi.")
    except Exception as e:
        print(f"feedback error: {e}")
        await m.answer("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")


@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply_to_user(m: types.Message):
    orig = m.reply_to_message.text or m.reply_to_message.caption or ""
    match = re.search(r"ID:\s*(\d+)", orig)
    if not match:
        return
    try:
        await bot.send_message(int(match.group(1)), f"👨‍💻 <b>Admin javobi:</b>\n\n{clean_text(m.text or '')}", parse_mode="HTML")
        await m.answer("✅ Javob yuborildi.")
    except Exception as e:
        await m.answer(f"❌ Yetkazib bo'lmadi: {e}")


@dp.message(F.audio | F.voice)
async def handle_audio_file(m: types.Message):
    file_id = m.audio.file_id if m.audio else m.voice.file_id
    file_size = m.audio.file_size if m.audio else m.voice.file_size
    if file_size and file_size > 20 * 1024 * 1024:
        await m.answer("❌ <b>Hajm 20MB dan oshmasligi kerak.</b>", parse_mode="HTML")
        return

    await asyncio.to_thread(update_user, m.from_user, True)
    u_tag = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
    audio_name = m.audio.file_name if m.audio and m.audio.file_name else "Voice_Message"
    user_data[m.chat.id] = {
        "fid": file_id, "mid": m.message_id, "uname": u_tag,
        "tr_lang": None, "view": None, "audio_name": audio_name,
    }
    await m.answer(AUDIO_RECEIVED_MSG, reply_markup=get_tr_kb(), parse_mode="HTML")


@dp.callback_query(F.data.startswith("tr_"))
async def set_translation_mode(call: types.CallbackQuery):
    data = user_data.get(call.message.chat.id)
    if not data:
        await call.answer("Audio topilmadi. Qayta yuboring.", show_alert=True)
        return
    data["tr_lang"] = call.data.replace("tr_", "")
    await call.message.edit_text(VIEW_MODE_MSG, reply_markup=get_split_kb(), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("v_"))
async def set_view_mode(call: types.CallbackQuery):
    data = user_data.get(call.message.chat.id)
    if not data:
        await call.answer("Audio topilmadi. Qayta yuboring.", show_alert=True)
        return
    data["view"] = call.data.replace("v_", "")
    await call.message.edit_text(FORMAT_MODE_MSG, reply_markup=get_format_kb(), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("f_"))
async def run_analysis(call: types.CallbackQuery):
    global waiting_users
    chat_id = call.message.chat.id
    fmt = call.data.replace("f_", "")
    data = user_data.get(chat_id)
    if not data:
        await call.message.answer("❌ Ma'lumotlar topilmadi. Audio-ni qaytadan yuboring.")
        return
    await call.answer()
    await call.message.delete()
    waiting_users += 1
    wait_msg = await call.message.answer(f"⏳ <b>Navbat:</b> {waiting_users}\nAI ishga tushmoqda...", parse_mode="HTML")

    a_path = f"/tmp/stt_{chat_id}_{data['mid']}.bin"
    r_path = f"/tmp/stt_{chat_id}_{data['mid']}.txt"
    try:
        async with process_lock:
            await _process_audio(chat_id, data, fmt, wait_msg, a_path, r_path)
    except Exception as e:
        print(f"Processing error: {e}")
        try:
            await call.message.answer("❌ Tahlil vaqtida xatolik yuz berdi. Qayta urinib ko'ring.")
        except Exception:
            pass
    finally:
        delete_temp_files(a_path, r_path)
        user_data.pop(chat_id, None)
        waiting_users = max(0, waiting_users - 1)
        gc.collect()


async def _process_audio(chat_id: int, data: dict, fmt: str, wait_msg: types.Message, a_path: str, r_path: str):
    async def progress(percent: int, status: str):
        blocks = max(0, min(10, percent // 10))
        try:
            await wait_msg.edit_text(
                f"🚀 <b>{status}</b>\n<code>{'🟩'*blocks}{'⬜'*(10-blocks)}</code> {percent}%",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await progress(10, "Audio yuklanmoqda...")
    f_info = await bot.get_file(data["fid"])
    await bot.download_file(f_info.file_path, a_path)
    file_hash = await asyncio.to_thread(get_file_hash, a_path)

    await progress(20, "Index tekshirilmoqda...")
    index = await asyncio.to_thread(get_audio_index, file_hash)

    segments = None
    if index and index.get("status") == "completed" and index.get("script_file_id"):
        await progress(40, "⚡ Tayyor script Telegram bazasidan olinmoqda...")
        try:
            payload = await storage.load_json(index["script_file_id"])
            segments = payload.get("segments")
        except Exception as e:
            print(f"Telegram cache read failed: {e}")
            segments = None

    if not segments:
        await progress(25, "Audio Telegram bazasiga saqlanmoqda...")
        try:
            media_kind = "voice" if data.get("is_voice") else "audio"
            saved_media = await storage.save_audio(data["fid"], media_kind, data.get("audio_name"))
            db_audio_msg_id = saved_media["message_id"]
            db_audio_file_id = saved_media["file_id"]
        except Exception as e:
            print(f"Telegram audio storage error: {e}")
            db_audio_msg_id = None
            db_audio_file_id = None

        await progress(35, "AI tahlil qilmoqda...")
        model = load_whisper()
        result = None
        try:
            result = await asyncio.to_thread(model.transcribe, a_path, fp16=False)
            segments = [
                {"start": float(s.get("start", 0)), "end": float(s.get("end", 0)), "text": str(s.get("text", ""))}
                for s in result.get("segments", [])
            ]
        finally:
            del result
            gc.collect()

        if not segments:
            raise RuntimeError("Audio ichidan nutq topilmadi.")

        await asyncio.to_thread(
            save_audio_index, file_hash,
            {
                "status": "processing",
                "user_id": str(chat_id),
                "audio_name": data.get("audio_name", "Audio"),
                "audio_message_id": db_audio_msg_id,
                "audio_file_id": db_audio_file_id or data["fid"],
                "source_file_id": data["fid"],
                "created_at": get_uz_time(),
            },
        )
    else:
        db_audio_msg_id = index.get("audio_message_id")
        db_audio_file_id = index.get("audio_file_id")

    await progress(70, "Tarjima va natija tayyorlanmoqda...")
    # Translation is blocking, so each call runs in a worker thread.
    html_parts, txt_parts = [], []
    total = max(1, len(segments))
    for i, seg in enumerate(segments):
        raw = str(seg.get("text", "")).strip()
        if not raw:
            continue
        stamp = format_time_stamp(float(seg.get("start", 0)))
        tr_html, tr_txt = "", ""
        if data["tr_lang"] != "orig":
            target = "uz" if "uz" in data["tr_lang"] else data["tr_lang"]
            try:
                translated = await asyncio.to_thread(await_translate_sync, raw, target)
                if data["tr_lang"] == "uz_only":
                    raw = translated
                else:
                    tr_html = f"\n└ <i>{clean_text(translated)}</i>"
                    tr_txt = f"\n   ({translated})"
            except Exception:
                pass
        if data["view"] == "split":
            html_parts.append(f"<b>{stamp}</b> {clean_text(raw)}{tr_html}")
            txt_parts.append(f"{stamp} {raw}{tr_txt}")
        else:
            html_parts.append(f"{clean_text(raw)}{tr_html}")
            txt_parts.append(f"{raw}{tr_txt}")
        if i % max(1, total // 5) == 0:
            await progress(70 + int(i / total * 20), "Tarjima tayyorlanmoqda...")

    bot_me = await bot.get_me()
    now = get_uz_time()
    pechat_txt = get_pechat_text(data["uname"], bot_me.username, now)
    pechat_html = get_pechat_html(data["uname"], bot_me.username, now)
    full_txt = "\n\n".join(txt_parts) + pechat_txt
    full_html = "\n\n".join(html_parts) + pechat_html

    payload = {
        "schema_version": 1,
        "file_hash": file_hash,
        "audio_name": data.get("audio_name", "Audio"),
        "user_id": str(chat_id),
        "created_at": now,
        "settings": {"translation": data["tr_lang"], "view": data["view"], "format": fmt},
        "segments": segments,
        "text": full_txt,
        "html": full_html,
    }

    # If the script was not cached, save its JSON object to Telegram and put only
    # references in Firestore. If it was cached, reuse the original script file.
    script_file_id = index.get("script_file_id") if index else None
    script_message_id = index.get("script_message_id") if index else None
    if not script_file_id:
        await progress(93, "Script Telegram bazasiga saqlanmoqda...")
        script_msg = await storage.save_json(payload, f"stt_{file_hash[:16]}.json", "SHodlik AI STT script")
        if not script_msg.document:
            raise RuntimeError("Telegram script document yuborilmadi.")
        script_file_id = script_msg.document.file_id
        script_message_id = script_msg.message_id

    await asyncio.to_thread(
        save_audio_index, file_hash,
        {
            "status": "completed",
            "user_id": str(chat_id),
            "audio_name": data.get("audio_name", "Audio"),
            "audio_file_id": db_audio_file_id or data["fid"],
            "source_file_id": data["fid"],
            "audio_message_id": db_audio_msg_id,
            "script_file_id": script_file_id,
            "script_message_id": script_message_id,
            "segments_count": len(segments),
            "created_at": index.get("created_at", now) if index else now,
            "last_used_at": now,
        },
    )
    await asyncio.to_thread(update_stats, "audio", fmt)

    await progress(97, "Natija yuborilmoqda...")
    if fmt == "txt":
        with open(r_path, "w", encoding="utf-8") as f:
            f.write(full_txt)
        await bot.send_document(
            chat_id=chat_id,
            document=types.FSInputFile(r_path),
            caption=pechat_html,
            reply_to_message_id=data["mid"],
            parse_mode="HTML",
        )
    else:
        for chunk in split_html_text(full_html):
            try:
                await bot.send_message(chat_id, chunk, parse_mode="HTML", reply_to_message_id=data["mid"])
            except Exception:
                await bot.send_message(chat_id, clean_text(chunk), reply_to_message_id=data["mid"])
            await asyncio.sleep(0.8)
    await progress(100, "Tayyor! ✅")
    await asyncio.sleep(0.5)
    try:
        await wait_msg.delete()
    except Exception:
        pass


# ================= ADMIN =================
@dp.message(F.text == "🔑 Admin Panel", F.chat.id == ADMIN_ID)
async def admin_main(m: types.Message):
    await m.answer("🛠 <b>Admin Boshqaruv Paneli</b>", reply_markup=get_admin_kb(), parse_mode="HTML")


@dp.callback_query(F.data == "adm_stats")
async def stats_cb(call: types.CallbackQuery):
    s = await asyncio.to_thread(get_stats)
    msg = (
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Userlar: {await asyncio.to_thread(get_user_count)}\n"
        f"🔄 Jami tahlillar: {s.get('total_processed', 0)}\n"
        f"🎙 Audiodan: {s.get('audio', 0)}\n"
        f"📄 TXT: {s.get('format_txt', 0)}\n"
        f"💬 Chat: {s.get('format_chat', 0)}"
    )
    await call.message.answer(msg, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "adm_list_menu")
async def list_menu_cb(call: types.CallbackQuery):
    await call.message.edit_text("📋 <b>Userlar ro'yxati:</b>", reply_markup=get_list_format_kb(), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("list_"))
async def generate_user_list(call: types.CallbackQuery):
    fmt = call.data.replace("list_", "")
    await call.message.delete()
    users = await asyncio.to_thread(get_users_page, 50, None)
    total = await asyncio.to_thread(get_user_count)
    if not users:
        await call.message.answer("❌ Hozircha foydalanuvchilar yo'q.")
        return
    await send_user_page(call.message.chat.id, users, 1, total, fmt)


async def send_user_page(chat_id: int, users: list[dict], page: int, total: int, fmt: str):
    lines = [f"📋 <b>FOYDALANUVCHILAR ({total} ta)</b> — {page}-sahifa\n"]
    start_no = (page - 1) * 50
    for i, u in enumerate(users, start_no + 1):
        lines.append(
            f"<b>{i}. {clean_text(u.get('name','Nomsiz'))}</b>\n"
            f"🆔 <code>{u.get('id','')}</code> | 🎧 {u.get('audio_count',0)} ta\n"
            f"📅 {u.get('joined_at','-')} | ⏳ {u.get('last_audio_time','-')}\n"
        )
    text = "\n".join(lines)
    if fmt == "chat":
        for chunk in split_html_text(text):
            await bot.send_message(chat_id, chunk, parse_mode="HTML")
    else:
        path = f"/tmp/users_{page}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(re.sub(r"<[^>]+>", "", text))
        await bot.send_document(chat_id, types.FSInputFile(path), caption=f"📋 Userlar — {page}-sahifa")
        delete_temp_files(path)
    if page * 50 < total:
        await bot.send_message(chat_id, "➡️ Keyingi sahifa:", reply_markup=get_user_list_pagination_kb(page, fmt, has_next=True, has_prev=(page > 1)))


@dp.callback_query(F.data.startswith("users_pg_"))
async def users_page_cb(call: types.CallbackQuery):
    _, _, page_s, fmt = call.data.split("_", 3)
    page = int(page_s)
    # Firestore cursor is intentionally not kept in RAM. Page navigation reads a
    # bounded window by skipping only when necessary; suitable for the admin list.
    # For very large registries, replace with a persisted cursor map.
    users = await asyncio.to_thread(get_users_page_offset, page, 50)
    total = await asyncio.to_thread(get_user_count)
    await send_user_page(call.message.chat.id, users, page, total, fmt)
    await call.answer()


def get_users_page_offset(page: int, limit: int):
    from database import get_db
    from firebase_admin import firestore
    q = get_db().collection("users").order_by("joined_at", direction=firestore.Query.DESCENDING).limit(limit * page)
    docs = list(q.stream())
    return [{"_doc_id": d.id, **d.to_dict()} for d in docs[-limit:]]


@dp.callback_query(F.data == "adm_bc")
async def bc_cb(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📢 <b>Broadcast:</b> Xabarni yuboring:")
    await state.set_state(AdminStates.waiting_for_bc)
    await call.answer()


@dp.message(AdminStates.waiting_for_bc)
async def bc_process(m: types.Message, state: FSMContext):
    await state.clear()
    from database import get_db
    prog = await m.answer("⏳ Tarqatish boshlandi...")
    sent = 0
    failed = 0
    # Stream one user at a time: no giant list in RAM.
    try:
        docs = get_db().collection("users").stream()
        for doc in docs:
            uid = doc.to_dict().get("id") or doc.id
            try:
                await bot.copy_message(chat_id=int(uid), from_chat_id=ADMIN_ID, message_id=m.message_id)
                sent += 1
                await asyncio.sleep(0.08)
            except Exception:
                failed += 1
            if (sent + failed) % 25 == 0:
                try:
                    await prog.edit_text(f"⏳ Tarqatilmoqda... {sent+failed}\n✅ {sent} | ❌ {failed}")
                except Exception:
                    pass
    except Exception as e:
        print(f"broadcast error: {e}")
    await prog.edit_text(f"✅ Tugadi.\nYuborildi: {sent}\nXato/bloklagan: {failed}")


@dp.callback_query(F.data == "adm_view_ts")
async def ask_ts_user_id(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🔍 Foydalanuvchi ID raqamini yuboring:")
    await state.set_state(AdminStates.waiting_for_user_id_ts)
    await call.answer()


@dp.message(AdminStates.waiting_for_user_id_ts)
async def process_ts_search(m: types.Message, state: FSMContext):
    await state.clear()
    uid = (m.text or "").strip()
    msg = await m.answer("⏳ Qidirilmoqda...")
    records = await asyncio.to_thread(get_user_transcripts, uid)
    if not records:
        await msg.edit_text(f"❌ <code>{uid}</code> bo'yicha tahlil topilmadi.", parse_mode="HTML")
        return
    await show_transcript_page(msg, uid, records, 1)


async def show_transcript_page(message: types.Message, user_id: str, records: list[dict], page: int):
    per = 5
    total_pages = max(1, (len(records) + per - 1) // per)
    items = records[(page-1)*per:page*per]
    text = f"📂 <b>User:</b> <code>{user_id}</code>\n📊 <b>Jami:</b> {len(records)}\n📄 <b>Sahifa:</b> {page}/{total_pages}\n\n"
    for idx, item in enumerate(items, 1):
        text += f"<b>[{idx}]</b> 🎵 {clean_text(item.get('audio_name','Nomsiz'))}\n🕒 {item.get('created_at','-')}\n\n"
    await message.edit_text(text, reply_markup=get_transcripts_pagination_kb(user_id, page, total_pages, items), parse_mode="HTML")


@dp.callback_query(F.data.startswith("ts_pg_"))
async def ts_pagination_handler(call: types.CallbackQuery):
    _, _, uid, page_s = call.data.split("_", 3)
    records = await asyncio.to_thread(get_user_transcripts, uid)
    await show_transcript_page(call.message, uid, records, int(page_s))
    await call.answer()


@dp.callback_query(F.data.startswith("ts_sel_"))
async def ts_select_handler(call: types.CallbackQuery):
    key = call.data.replace("ts_sel_", "")
    await call.message.edit_text("💾 <b>Natijani tanlang:</b>", reply_markup=get_transcript_format_kb(key), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("ts_fmt_"))
async def ts_send_handler(call: types.CallbackQuery):
    parts = call.data.split("_", 3)
    fmt, key = parts[2], parts[3]
    record = await asyncio.to_thread(get_transcript_by_id, key)
    await call.message.delete()
    if not record or not record.get("script_file_id"):
        await call.message.answer("❌ Telegram bazasidagi script topilmadi.")
        return
    try:
        payload = await storage.load_json(record["script_file_id"])
        full_text = payload.get("text", "Matn bo'sh")
        if fmt == "txt":
            path = f"/tmp/admin_ts_{key}.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write(full_text)
            await bot.send_document(call.message.chat.id, types.FSInputFile(path), caption="📂 So'ralgan tahlil")
            delete_temp_files(path)
        else:
            for chunk in split_html_text(payload.get("html") or clean_text(full_text)):
                await bot.send_message(call.message.chat.id, chunk, parse_mode="HTML")
                await asyncio.sleep(0.4)
    except Exception as e:
        await call.message.answer(f"❌ Telegram DB o'qilmadi: {e}")


@dp.message(F.text == "🌐 Saytga kirish")
async def web_h(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌐 Saytni ochish", url="https://shodlikai.github.io/new_3/dastur.html")
    await m.answer("Veb-sahifaga o'tish:", reply_markup=kb.as_markup())


@dp.message()
async def unknown_handler(m: types.Message):
    if m.text in ["🎧 Tahlil boshlash", "🌐 Saytga kirish", "👨‍💻 Bog'lanish", "ℹ️ Yordam", "🔑 Admin Panel"]:
        return
    await m.answer(get_guide_msg(m.from_user.first_name), reply_markup=get_main_menu(m.from_user.id), parse_mode="HTML")
