from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import ADMIN_ID

# 1. ASOSIY MENYU
def get_main_menu(uid):
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎧 Tahlil boshlash")
    kb.button(text="🌐 Saytga kirish")
    kb.button(text="👨‍💻 Bog'lanish")
    kb.button(text="ℹ️ Yordam")
    if uid == ADMIN_ID: 
        kb.button(text="🔑 Admin Panel")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# 2. TARJIMA MENYUSI
def get_tr_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Tarjima qilinmasin (Original)", callback_data="tr_orig")
    kb.button(text="🇺🇿 O'zbekchaga (Qavs ichida)", callback_data="tr_uz")
    kb.button(text="🇷🇺 Ruschaga (Qavs ichida)", callback_data="tr_ru")
    kb.button(text="🇬🇧 Inglizchaga (Qavs ichida)", callback_data="tr_en")
    kb.adjust(1)
    return kb.as_markup()

# 3. KO'RINISH MENYUSI
def get_split_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⏱ Time Split (Vaqt [00:10] bilan)", callback_data="v_split")
    kb.button(text="📖 Full Context (Yaxlit matn)", callback_data="v_full")
    kb.adjust(1)
    return kb.as_markup()

# 4. FORMAT MENYUSI
def get_format_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📁 TXT Fayl (Hujjat)", callback_data="f_txt")
    kb.button(text="💬 Chat (Xabar)", callback_data="f_chat")
    kb.adjust(2)
    return kb.as_markup()

# 5. ADMIN PANEL
def get_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Statistika", callback_data="adm_stats")
    kb.button(text="📋 Ro'yxat", callback_data="adm_list")
    kb.button(text="📢 Broadcast", callback_data="adm_bc")
    kb.adjust(1)
    return kb.as_markup()

# 6. ALOQA UCHUN TUGMA
def get_contact_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✍️ Adminga yozish", callback_data="msg_to_admin")
    return kb.as_markup()
    
