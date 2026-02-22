import streamlit as st
import threading
import asyncio
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# BIZNING MODULLAR
from config import BOT_TOKEN
from bot_handlers import dp, bot
from database import get_all_users, get_stats

# --- 1. PAGE CONFIG & NEON CSS ---
st.set_page_config(page_title="Suxandon AI Admin", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #00ffcc; }
    div[data-testid="stMetric"] {
        background-color: #1c1f26; border: 2px solid #00ffcc;
        border-radius: 10px; padding: 15px;
        box-shadow: 0 0 10px #00ffcc, 0 0 20px #00ffcc inset; text-align: center;
    }
    div[data-testid="stMetricLabel"] { color: #ff00ff !important; font-weight: bold; }
    div[data-testid="stMetricValue"] { color: #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FIREBASE MA'LUMOTLARINI OLISH ---
try:
    users = get_all_users()
    stats = get_stats()
    total_users = len(users)
    total_processed = stats.get('total_processed', 0)
    audio_count = stats.get('audio', 0)
    
    st.title("⚡ Suxandon AI - Boshqaruv Paneli")
    
    # --- 3. METRIKALAR ---
    col1, col2, col3 = st.columns(3)
    with col1: st.metric(label="👥 Jami Foydalanuvchilar", value=f"{total_users} ta")
    with col2: st.metric(label="🔄 Tahlil qilingan fayllar", value=f"{total_processed} ta")
    with col3: st.metric(label="🎙 Audio Tahlillar", value=f"{audio_count} ta")

    # --- 4. FOYDALANUVCHILAR JADVALI ---
    st.markdown("### 📋 Oxirgi qo'shilgan foydalanuvchilar")
    if users:
        df = pd.DataFrame(users)
        # Jadval ustunlarini chiroyli tartiblash
        df = df[['name', 'username', 'id', 'audio_count', 'last_audio_time', 'joined_at']]
        df.columns = ["Ism", "Username", "ID", "Audio Soni", "Oxirgi Audio", "Qo'shilgan vaqti"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Hozircha foydalanuvchilar yo'q.")

except Exception as e:
    st.warning(f"Baza ma'lumotlari yuklanishida xatolik: {e}")

# --- 5. BOT RUNNER (ENG MUHIM QISM - KILLER & SINGLETON) ---
def run_bot_in_background():
    """Botni alohida oqimda va xavfsiz ishga tushirish"""
    
    async def _runner():
        try:
            # 1. KILLER: Eski webhooklarni o'chirish (Conflict oldini olish, server qotmasligi uchun)
            await bot.delete_webhook(drop_pending_updates=True)
            # 2. BOTNI YOQISH
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e:
            print(f"Bot Error: {e}")

    def _thread_target():
        # Yangi event loop ochamiz (Streamlit bilan urushmasligi uchun)
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(_runner())

    # SINGLETON: Agar thread allaqachon ishlayotgan bo'lsa, ikkinchisini ochmaymiz
    thread_name = "TelegramBotThread"
    is_running = False
    for t in threading.enumerate():
        if t.name == thread_name:
            is_running = True
            break
            
    if not is_running:
        # Daemon=True -> Streamlit o'chsa, bot ham o'chadi (osilib qolmaydi)
        bot_thread = threading.Thread(target=_thread_target, name=thread_name, daemon=True)
        bot_thread.start()

# Botni fon rejimida ishga tushirish
run_bot_in_background()
