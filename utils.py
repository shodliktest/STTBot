import os
import pytz
from datetime import datetime

# O'zbekiston vaqti
UZ_TZ = pytz.timezone('Asia/Tashkent')

def get_uz_time():
    """Hozirgi sanani qaytaradi: YYYY-MM-DD HH:MM:SS"""
    return datetime.now(UZ_TZ).strftime('%Y-%m-%d %H:%M:%S')

def clean_text(text):
    """Telegram HTML rejimi uchun matnni tozalash."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def delete_temp_files(*file_paths):
    """Vaqtinchalik fayllarni o'chirish"""
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass

def format_time_stamp(seconds):
    """Sekundlarni [MM:SS] formatiga o'tkazish"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{minutes:02d}:{secs:02d}]"

def split_html_text(text, limit=4000):
    """HTML matnni xavfsiz bo'laklarga bo'lish (uzun xabarlar uchun)."""
    if len(text) <= limit:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        
        split_at = text.rfind('\n\n', 0, limit)
        if split_at == -1:
            split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = text.rfind('. ', 0, limit)
        if split_at == -1:
            split_at = limit
            
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks
