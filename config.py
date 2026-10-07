import streamlit as st
import pytz

BOT_TOKEN = st.secrets.get("BOT_TOKEN", "TOKEN_YOQ")
ADMIN_ID = int(st.secrets.get("ADMIN_ID", 1416457518))
TELEGRAM_DB_CHANNEL_ID = int(st.secrets.get("TELEGRAM_DB_CHANNEL_ID", 0))
WHISPER_MODEL = str(st.secrets.get("WHISPER_MODEL", "base"))
UZ_TZ = pytz.timezone("Asia/Tashkent")
