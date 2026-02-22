# messages.py

def get_welcome_msg(first_name):
    return (
        f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\n"
        f"🎙 <b>SHodlik AI</b> botiga xush kelibsiz.\n"
        f"Men audio materiallarni akademik darajada tahlil qilib beraman.\n\n"
        "🚀 <b>Ishni boshlash uchun ovozli xabar yoki audio fayl yuboring!</b>"
    )

def get_guide_msg(first_name):
    return (
        f"👋 <b>Salom, {first_name}! SHodlik AI botiga xush kelibsiz.</b>\n\n"
        "Siz yozgan matnli xabarni tushunmadim, chunki mening vazifam audio materiallarni tahlil qilishdir.\n\n"
        "🛠 <b>Botdan qanday foydalanish kerak?</b>\n"
        "1️⃣ Menga ovozli xabar (voice) yoki audio fayl (mp3) yuboring.\n"
        "2️⃣ Bot so'ragan tarjima turi, matn ko'rinishi va formatini tanlang.\n"
        "3️⃣ Men uni akademik darajada matnga aylantirib, audioingizga <b>javob (reply)</b> sifatida qaytaraman.\n\n"
        "💡 <i>Menyudagi tugmalardan foydalaning yoki hoziroq audio yuboring!</i>"
    )

def get_new_user_admin_msg(full_name, user_id, username, joined_time):
    return (
        f"🆕 <b>YANGI FOYDALANUVCHI QO'SHILDI:</b>\n\n"
        f"👤 <b>Ism:</b> {full_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"⏰ <b>Vaqt:</b> {joined_time}"
    )

def get_pechat_text(username, bot_username, time_now):
    return (
        f"\n\n✅ Natija tayyor!\n\n"
        f"👤 {username}\n"
        f"🤖 @{bot_username}\n"
        f"⏰ {time_now}"
    )

def get_pechat_html(username, bot_username, time_now):
    return (
        f"\n\n<b>✅ Natija tayyor!</b>\n\n"
        f"👤 {username}\n"
        f"🤖 @{bot_username}\n"
        f"⏰ {time_now}"
    )

HELP_MSG = (
    "📚 <b>Botdan qanday foydalaniladi?</b>\n\n"
    "1. Menga audio fayl yuboring.\n"
    "2. <b>Tarjima turi:</b> Ovozni shunchaki matnga aylantirish yoki boshqa tilga tarjima qilishni tanlang.\n"
    "3. <b>Ko'rinish:</b> Matn vaqtlar bilan bo'lingan bo'lsinmi yoki yaxlit kitob ko'rinishidami?\n"
    "4. <b>Format:</b> Natijani chatda o'qish qulaymi yoki .txt hujjat qilib beraymi?\n\n"
    "⚠️ <i>Fayl hajmi 20MB dan oshmasligi kerak.</i>"
)

AUDIO_RECEIVED_MSG = (
    "🌍 <b>Audio qabul qilindi! Endi tarjima usulini tanlang.</b>\n\n"
    "🔹 <b>Original:</b> Faqat ovozdagi gaplar o'z tilida chiqadi.\n"
    "🔹 <b>O'zbekchaga:</b> Asl matn va uning tarjimasi birga keladi.\n"
    "🔹 <b>Faqat O'zbekcha:</b> Asl matnni o'chirib, faqat tarjimani beradi."
)

VIEW_MODE_MSG = (
    "📄 <b>Matn ko'rinishini tanlang:</b>\n\n"
    "⏱ <b>Time Split:</b> Matnni sekundlar [00:15] bo'yicha bo'laklaydi.\n"
    "📖 <b>Full Context:</b> Matnni yaxlit kitobdek qilib beradi."
)

FORMAT_MODE_MSG = (
    "💾 <b>Natijani qanday olishni tanlang:</b>\n\n"
    "📁 <b>TXT Fayl:</b> Barcha matn hujjat (.txt) ko'rinishida keladi.\n"
    "💬 <b>Chat (Xabar):</b> Natija to'g'ridan-to'g'ri botga xabar bo'lib keladi."
)
