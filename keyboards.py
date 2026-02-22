from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import ADMIN_ID

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

def get_tr_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Tarjima kerak emas (Faqat Original)", callback_data="tr_orig")
    kb.button(text="🇺🇿 O'zbekchaga (Original + Tarjima)", callback_data="tr_uz")
    kb.button(text="🇺🇿 Faqat O'zbekcha (Originalsiz)", callback_data="tr_uz_only")
    kb.button(text="🇷🇺 Ruscha tarjima", callback_data="tr_ru")
    kb.button(text="🇬🇧 Inglizcha tarjima", callback_data="tr_en")
    kb.adjust(1)
    return kb.as_markup()

def get_split_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⏱ Time Split (Vaqtlar bilan)", callback_data="v_split")
    kb.button(text="📖 Full Context (Yaxlit matn)", callback_data="v_full")
    kb.adjust(1)
    return kb.as_markup()

def get_format_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📁 TXT Fayl (Hujjat)", callback_data="f_txt")
    kb.button(text="💬 Chat (Xabar)", callback_data="f_chat")
    kb.adjust(1)
    return kb.as_markup()

def get_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Statistika", callback_data="adm_stats")
    kb.button(text="📋 Userlar Ro'yxati", callback_data="adm_list_menu")
    kb.button(text="📁 Transkriptlarni ko'rish", callback_data="adm_view_ts") # YANGI
    kb.button(text="📢 Broadcast (Reklama)", callback_data="adm_bc")
    kb.button(text="📈 TGStat (Kengaytirilgan)", url="https://shodlikai.github.io/new_3/dastur.html") # Dashboardga ssilka
    kb.adjust(1)
    return kb.as_markup()

def get_list_format_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Chatda ko'rish", callback_data="list_chat")
    kb.button(text="📁 TXT faylida olish", callback_data="list_txt")
    kb.adjust(2)
    return kb.as_markup()

def get_contact_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✍️ Adminga xabar yozish", callback_data="msg_to_admin")
    return kb.as_markup()

# --- YANGI: TRANSKRIPTLAR UCHUN PAGINATION (VARAKLASH) ---
def get_transcripts_pagination_kb(user_id, current_page, total_pages, page_items):
    kb = InlineKeyboardBuilder()
    
    # Raqamli tugmalarni qo'shish (1, 2, 3...)
    buttons = []
    for idx, item in enumerate(page_items):
        # item['id'] bu Firestore dagi document ID
        buttons.append(
            InlineKeyboardBuilder().button(text=f"[{idx+1}]", callback_data=f"ts_sel_{item['id']}")
        )
    
    # Raqamlarni bitta qatorga tizish
    for b in buttons: kb.attach(b)
    kb.adjust(len(buttons))
    
    # Oldingi va Keyingi tugmalari
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardBuilder().button(text="⬅️ Oldingi", callback_data=f"ts_pg_{user_id}_{current_page-1}"))
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardBuilder().button(text="Keyingi ➡️", callback_data=f"ts_pg_{user_id}_{current_page+1}"))
    
    if nav_buttons:
        nav_kb = InlineKeyboardBuilder()
        for nb in nav_buttons: nav_kb.attach(nb)
        nav_kb.adjust(len(nav_buttons))
        kb.attach(nav_kb)
        
    return kb.as_markup()

def get_transcript_format_kb(doc_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Chatda o'qish", callback_data=f"ts_fmt_chat_{doc_id}")
    kb.button(text="📁 TXT Faylida olish", callback_data=f"ts_fmt_txt_{doc_id}")
    kb.adjust(2)
    return kb.as_markup()
