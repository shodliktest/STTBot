import streamlit as st
import threading
import asyncio
import pandas as pd
import plotly.express as px

from config import BOT_TOKEN
from bot_handlers import dp, bot
from database import get_all_users, get_stats, increment_page_view

# --- PAGE CONFIG ---
st.set_page_config(page_title="SHodlik AI STT Admin", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #00ffcc; }
    div[data-testid="stMetric"] { background-color: #1c1f26; border: 2px solid #00ffcc; border-radius: 10px; padding: 15px; text-align: center;}
    div[data-testid="stMetricLabel"] { color: #ff00ff !important; font-weight: bold; }
    div[data-testid="stMetricValue"] { color: #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

# TASHRIFLARNI SANASH
if 'visited' not in st.session_state:
    st.session_state.visited = True
    increment_page_view()

try:
    users = get_all_users()
    stats = get_stats()
    
    st.title("⚡ SHodlik AI STT - Boshqaruv Paneli")
    
    # METRIKALAR
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Foydalanuvchilar", f"{len(users)} ta")
    c2.metric("🔄 Jami Tahlillar", f"{stats.get('total_processed', 0)} ta")
    c3.metric("🎙 Audio Tahlillar", f"{stats.get('audio', 0)} ta")
    c4.metric("👁 Saytga Tashriflar", f"{stats.get('page_views', 0)} marta")

    # TGSTAT GRAFIKI (User o'sishi)
    st.markdown("### 📈 TGStat: Foydalanuvchilar o'sish dinamikasi")
    if users:
        df = pd.DataFrame(users)
        if 'joined_at' in df.columns:
            df['date'] = pd.to_datetime(df['joined_at']).dt.date
            daily_users = df.groupby('date').size().reset_index(name='Yangi Userlar')
            
            fig = px.line(daily_users, x='date', y='Yangi Userlar', markers=True, template="plotly_dark")
            fig.update_traces(line_color='#00ffcc', marker=dict(size=8, color='#ff00ff'))
            st.plotly_chart(fig, use_container_width=True)
            
        st.markdown("### 📋 Barcha Foydalanuvchilar")
        
        # YANGILANISH: Jadvalda qo'shilgan vaqtini ham ko'rsatamiz va ustun nomlarini chiroyli qilamiz
        show_cols = ['name', 'username', 'id', 'joined_at', 'audio_count', 'last_audio_time']
        for c in show_cols: 
            if c not in df.columns: df[c] = "-"
            
        df_display = df[show_cols].copy()
        df_display.columns = ["Ism", "Username", "ID", "Qo'shilgan vaqti", "Audio Soni", "Oxirgi faollik"]
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
except Exception as e:
    st.warning(f"Xatolik: {e}")

# --- BOT RUNNER (SINGLETON & KILLER) ---
def run_bot_in_background():
    async def _runner():
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e: 
            print(f"Polling Error: {e}")
            
    def _t():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_runner())

    if not any(t.name == "BotThread" for t in threading.enumerate()):
        threading.Thread(target=_t, name="BotThread", daemon=True).start()

run_bot_in_background()
