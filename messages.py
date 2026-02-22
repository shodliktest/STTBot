# messages.py

LANGUAGES = {
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English"
}

TEXTS = {
    "uz": {
        "welcome": (
            "👋 <b>Assalomu alaykum, {name}!</b>\n\n"
            "🎙 <b>SHodlik AI</b> botiga xush kelibsiz.\n"
            "Men audio materiallarni akademik darajada tahlil qilib beraman.\n\n"
            "🚀 <b>Ishni boshlash uchun ovozli xabar yoki audio fayl yuboring!</b>"
        ),
        "guide": (
            "👋 <b>Salom, {name}! SHodlik AI botiga xush kelibsiz.</b>\n\n"
            "Siz yozgan matnli xabarni tushunmadim, chunki mening vazifam audio materiallarni tahlil qilishdir.\n\n"
            "🛠 <b>Botdan qanday foydalanish kerak?</b>\n"
            "1️⃣ Menga ovozli xabar (voice) yoki audio fayl (mp3) yuboring.\n"
            "2️⃣ Bot so'ragan tarjima turi, matn ko'rinishi va formatini tanlang.\n"
            "3️⃣ Men uni akademik darajada matnga aylantirib, audioingizga <b>javob (reply)</b> sifatida qaytaraman.\n\n"
            "💡 <i>Menyudagi tugmalardan foydalaning yoki hoziroq audio yuboring!</i>"
        ),
        "help": (
            "📚 <b>Botdan qanday foydalaniladi?</b>\n\n"
            "1. Menga audio fayl yuboring.\n"
            "2. <b>Tarjima turi:</b> Ovozni shunchaki matnga aylantirish yoki boshqa tilga tarjima qilishni tanlang.\n"
            "3. <b>Ko'rinish:</b> Matn vaqtlar bilan bo'lingan bo'lsinmi yoki yaxlit kitob ko'rinishidami?\n"
            "4. <b>Format:</b> Natijani chatda o'qish qulaymi, .txt yoki Word (.docx) hujjat qilib beraymi?\n\n"
            "⚠️ <i>Fayl hajmi 20MB dan oshmasligi kerak.</i>"
        ),
        "settings": "⚙️ <b>Sozlamalar</b>\n\nO'zingizga qulay tilni tanlang:",
        "lang_changed": "✅ Til muvaffaqiyatli o'zgartirildi!",
        "audio_received": (
            "🌍 <b>Audio qabul qilindi! Endi tarjima usulini tanlang.</b>\n\n"
            "🔹 <b>Original:</b> Faqat ovozdagi gaplar o'z tilida chiqadi.\n"
            "🔹 <b>O'zbekchaga:</b> Asl matn va uning tarjimasi birga keladi.\n"
            "🔹 <b>Faqat O'zbekcha:</b> Asl matnni o'chirib, faqat tarjimani beradi."
        ),
        "view_mode": (
            "📄 <b>Matn ko'rinishini tanlang:</b>\n\n"
            "⏱ <b>Time Split:</b> Matnni sekundlar [00:15] bo'yicha bo'laklaydi.\n"
            "📖 <b>Full Context:</b> Matnni yaxlit kitobdek qilib beradi."
        ),
        "format_mode": (
            "💾 <b>Natijani qanday olishni tanlang:</b>\n\n"
            "📄 <b>Word (.docx):</b> Chiroyli akademik Word hujjat.\n"
            "📁 <b>TXT Fayl:</b> Barcha matn hujjat (.txt) ko'rinishida keladi.\n"
            "💬 <b>Chat (Xabar):</b> Natija to'g'ridan-to'g'ri botga xabar bo'lib keladi."
        ),
        "pechat_txt": "\n\n✅ Natija tayyor!\n\n👤 {username}\n🤖 @{bot_username}\n⏰ {time_now}",
        "pechat_html": "\n\n<b>✅ Natija tayyor!</b>\n\n👤 {username}\n🤖 @{bot_username}\n⏰ {time_now}",
        "btn_start": "🎧 Tahlil boshlash",
        "btn_site": "🌐 Saytga kirish",
        "btn_contact": "👨‍💻 Bog'lanish",
        "btn_help": "ℹ️ Yordam",
        "btn_settings": "⚙️ Sozlamalar",
        "btn_admin": "🔑 Admin Panel"
    },
    "ru": {
        "welcome": (
            "👋 <b>Здравствуйте, {name}!</b>\n\n"
            "🎙 Добро пожаловать в бота <b>SHodlik AI</b>.\n"
            "Я анализирую аудиоматериалы на академическом уровне.\n\n"
            "🚀 <b>Для начала отправьте голосовое сообщение или аудиофайл!</b>"
        ),
        "guide": (
            "👋 <b>Привет, {name}! Добро пожаловать в SHodlik AI.</b>\n\n"
            "Я не понимаю текстовые сообщения, так как моя задача - анализировать аудио.\n\n"
            "🛠 <b>Как пользоваться ботом?</b>\n"
            "1️⃣ Отправьте мне голосовое сообщение или аудиофайл (mp3).\n"
            "2️⃣ Выберите тип перевода, вид текста и формат результата.\n"
            "3️⃣ Я переведу это в текст на академическом уровне и отправлю вам в виде <b>ответа (reply)</b>.\n\n"
            "💡 <i>Используйте кнопки меню или отправьте аудио прямо сейчас!</i>"
        ),
        "help": (
            "📚 <b>Как использовать бота?</b>\n\n"
            "1. Отправьте аудиофайл.\n"
            "2. <b>Перевод:</b> Оставить оригинал или перевести на другой язык.\n"
            "3. <b>Вид:</b> Разделить по таймингам или сплошным текстом.\n"
            "4. <b>Формат:</b> Прочитать в чате, получить .txt или Word (.docx).\n\n"
            "⚠️ <i>Размер файла не должен превышать 20 МБ.</i>"
        ),
        "settings": "⚙️ <b>Настройки</b>\n\nВыберите удобный для вас язык:",
        "lang_changed": "✅ Язык успешно изменен!",
        "audio_received": (
            "🌍 <b>Аудио получено! Выберите способ перевода.</b>\n\n"
            "🔹 <b>Оригинал:</b> Только исходный текст без перевода.\n"
            "🔹 <b>На узбекский:</b> Оригинал + узбекский перевод.\n"
            "🔹 <b>Только узбекский:</b> Исходный текст удаляется, выдается только перевод."
        ),
        "view_mode": (
            "📄 <b>Выберите вид текста:</b>\n\n"
            "⏱ <b>Time Split:</b> Разделение по времени [00:15].\n"
            "📖 <b>Full Context:</b> Сплошной текст как в книге."
        ),
        "format_mode": (
            "💾 <b>Как вы хотите получить результат?</b>\n\n"
            "📄 <b>Word (.docx):</b> Красивый документ Word.\n"
            "📁 <b>TXT Файл:</b> Обычный текстовый документ (.txt).\n"
            "💬 <b>Чат:</b> Результат придет прямо в виде сообщения."
        ),
        "pechat_txt": "\n\n✅ Результат готов!\n\n👤 {username}\n🤖 @{bot_username}\n⏰ {time_now}",
        "pechat_html": "\n\n<b>✅ Результат готов!</b>\n\n👤 {username}\n🤖 @{bot_username}\n⏰ {time_now}",
        "btn_start": "🎧 Начать анализ",
        "btn_site": "🌐 Перейти на сайт",
        "btn_contact": "👨‍💻 Связаться",
        "btn_help": "ℹ️ Помощь",
        "btn_settings": "⚙️ Настройки",
        "btn_admin": "🔑 Админ Панель"
    },
    "en": {
        "welcome": (
            "👋 <b>Hello, {name}!</b>\n\n"
            "🎙 Welcome to <b>SHodlik AI</b> bot.\n"
            "I analyze audio materials at an academic level.\n\n"
            "🚀 <b>Send a voice message or audio file to get started!</b>"
        ),
        "guide": (
            "👋 <b>Hi, {name}! Welcome to SHodlik AI.</b>\n\n"
            "I don't understand text messages because my job is to analyze audio.\n\n"
            "🛠 <b>How to use the bot?</b>\n"
            "1️⃣ Send me a voice message or audio file (mp3).\n"
            "2️⃣ Choose the translation type, text layout, and format.\n"
            "3️⃣ I will transcribe it academically and send it back to you as a <b>reply</b>.\n\n"
            "💡 <i>Use the menu buttons or send an audio right now!</i>"
        ),
        "help": (
            "📚 <b>How to use?</b>\n\n"
            "1. Send an audio file.\n"
            "2. <b>Translation:</b> Keep original or translate to another language.\n"
            "3. <b>Layout:</b> Time splits or full book-like text.\n"
            "4. <b>Format:</b> Read in chat, get .txt or Word (.docx) document.\n\n"
            "⚠️ <i>Max file size is 20MB.</i>"
        ),
        "settings": "⚙️ <b>Settings</b>\n\nChoose your preferred language:",
        "lang_changed": "✅ Language changed successfully!",
        "audio_received": (
            "🌍 <b>Audio received! Now choose translation method.</b>\n\n"
            "🔹 <b>Original:</b> Original text only.\n"
            "🔹 <b>To Uzbek:</b> Original + Uzbek translation.\n"
            "🔹 <b>Uzbek Only:</b> Removes original, provides only translation."
        ),
        "view_mode": (
            "📄 <b>Choose text layout:</b>\n\n"
            "⏱ <b>Time Split:</b> Split by timestamps [00:15].\n"
            "📖 <b>Full Context:</b> Solid book-like text."
        ),
        "format_mode": (
            "💾 <b>How do you want the result?</b>\n\n"
            "📄 <b>Word (.docx):</b> Beautiful Word document.\n"
            "📁 <b>TXT File:</b> Standard text document (.txt).\n"
            "💬 <b>Chat:</b> Result sent directly as a chat message."
        ),
        "pechat_txt": "\n\n✅ Result is ready!\n\n👤 {username}\n🤖 @{bot_username}\n⏰ {time_now}",
        "pechat_html": "\n\n<b>✅ Result is ready!</b>\n\n👤 {username}\n🤖 @{bot_username}\n⏰ {time_now}",
        "btn_start": "🎧 Start Analysis",
        "btn_site": "🌐 Website",
        "btn_contact": "👨‍💻 Contact",
        "btn_help": "ℹ️ Help",
        "btn_settings": "⚙️ Settings",
        "btn_admin": "🔑 Admin Panel"
    }
}

def get_msg(lang, key, **kwargs):
    """Tanlangan til bo'yicha matnni qaytaradi"""
    lang = lang if lang in TEXTS else "uz"
    text = TEXTS[lang].get(key, TEXTS["uz"].get(key, ""))
    return text.format(**kwargs) if kwargs else text

# --- Admin xabari doim o'zbek tilida qolgani ma'qul (chunki admin sizsiz) ---
def get_new_user_admin_msg(full_name, user_id, username, joined_time):
    return (
        f"🆕 <b>YANGI FOYDALANUVCHI QO'SHILDI:</b>\n\n"
        f"👤 <b>Ism:</b> {full_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"⏰ <b>Vaqt:</b> {joined_time}"
    )
