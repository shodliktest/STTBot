import asyncio
import threading

import pandas as pd
import streamlit as st

from bot_handlers import dp, bot
from config import BOT_TOKEN
from database import get_stats, get_user_count, get_users_page, get_daily_user_growth, increment_page_view

st.set_page_config(page_title="SHodlik AI STT Admin", page_icon="⚡", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #00ffcc; }
div[data-testid="stMetric"] { background-color: #1c1f26; border: 2px solid #00ffcc; border-radius: 10px; padding: 15px; text-align: center;}
div[data-testid="stMetricLabel"] { color: #ff00ff !important; font-weight: bold; }
div[data-testid="stMetricValue"] { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

if "visited" not in st.session_state:
    st.session_state.visited = True
    increment_page_view()

try:
    stats = get_stats()
    user_count = get_user_count()
    st.title("⚡ SHodlik AI STT - Boshqaruv Paneli")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Foydalanuvchilar", f"{user_count} ta")
    c2.metric("🔄 Jami Tahlillar", f"{stats.get('total_processed', 0)} ta")
    c3.metric("🎙 Audio Tahlillar", f"{stats.get('audio', 0)} ta")
    c4.metric("👁 Saytga Tashriflar", f"{stats.get('page_views', 0)} marta")

    growth = get_daily_user_growth(90)
    if growth:
        st.markdown("### 📈 Foydalanuvchilar o'sishi")
        df = pd.DataFrame(growth)
        if "date" in df.columns and "new_users" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            st.line_chart(df.set_index("date")["new_users"])

    st.markdown("### 📋 So'nggi foydalanuvchilar")
    users = get_users_page(50)
    if users:
        rows = []
        for u in users:
            rows.append({
                "Ism": u.get("name", "-"), "Username": u.get("username", "-"),
                "ID": u.get("id", "-"), "Qo'shilgan": u.get("joined_at", "-"),
                "Audio": u.get("audio_count", 0), "Oxirgi faollik": u.get("last_active", "-"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Hozircha userlar yo'q.")
except Exception as e:
    st.warning(f"Dashboard xatosi: {e}")


def run_bot_in_background():
    async def runner():
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e:
            print(f"Polling Error: {e}")

    if not any(t.name == "BotThread" and t.is_alive() for t in threading.enumerate()):
        threading.Thread(target=lambda: asyncio.run(runner()), name="BotThread", daemon=True).start()


run_bot_in_background()
