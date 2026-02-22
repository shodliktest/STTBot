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
    kb.button(text="❌ Tarjima kerak emas (Faqat Original)", callback_data="tr_orig")
    kb.button(text="🇺🇿 O'zbekchaga (Original + Tarjima)", callback_data="tr_uz")
    kb.button(text="🇺🇿 Faqat O'zbekcha (Originalsiz)", callback_data="tr_uz_only")
    kb.button(text="🇷🇺 Ruscha tarjima", callback_data="tr_ru")
    kb.button(text="🇬🇧 Inglizcha tarjima", callback_data="tr_en")
    kb.adjust(1)
    return kb.as_markup()

# 3. KO'RINISH MENYUSI
def get_split_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⏱ Time Split (Vaqtlar bilan bo'lingan)", callback_data="v_split")
    kb.button(text="📖 Full Context (Yaxlit matn ko'rinishida)", callback_data="v_full")
    kb.adjust(1)
    return kb.as_markup()

# 4. FORMAT MENYUSI
def get_format_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📁 TXT Fayl (Hujjat sifatida yuklash)", callback_data="f_txt")
    kb.button(text="💬 Chat (To'g'ridan-to'g'ri xabar)", callback_data="f_chat")
    kb.adjust(1)
    return kb.as_markup()

# 5. ADMIN PANEL
def get_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Statistika", callback_data="adm_stats")
    kb.button(text="📋 Userlar Ro'yxati", callback_data="adm_list_menu")
    kb.button(text="📢 Broadcast (Reklama)", callback_data="adm_bc")
    kb.adjust(1)
    return kb.as_markup()

# --- YANGI QO'SHILGAN FUNKSIYA (Xatolik shuning uchun beryapti) ---
def get_list_format_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Chatda ko'rish", callback_data="list_chat")
    kb.button(text="📁 TXT faylida olish", callback_data="list_txt")
    kb.adjust(2)
    return kb.as_markup()

# 6. ALOQA
def get_contact_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✍️ Adminga xabar yozish", callback_data="msg_to_admin")
    return kb.as_markup()
