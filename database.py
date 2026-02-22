import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pytz

UZ_TZ = pytz.timezone('Asia/Tashkent')

def get_uz_time():
    return datetime.now(UZ_TZ).strftime('%Y-%m-%d %H:%M:%S')

# Firebase ulanishini initsializatsiya qilish (Faqat bir marta)
if not firebase_admin._apps:
    try:
        cred_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase ulanish xatosi: {e}")

db = firestore.client()

def update_user(user, added_audio=False):
    """Foydalanuvchini bazaga qo'shish yoki yangilash. Audio tashlaganini hisobga olish."""
    user_ref = db.collection('users').document(str(user.id))
    doc = user_ref.get()
    
    now = get_uz_time()
    username = f"@{user.username}" if user.username else "Mavjud emas"
    
    if not doc.exists:
        user_data = {
            "id": str(user.id),
            "name": user.full_name,
            "username": username,
            "joined_at": now,
            "last_active": now,
            "audio_count": 1 if added_audio else 0,
            "last_audio_time": now if added_audio else "Hali yubormagan"
        }
        user_ref.set(user_data)
        return True # Yangi foydalanuvchi ekanligini bildiradi
    else:
        update_data = {
            "name": user.full_name,
            "username": username,
            "last_active": now
        }
        if added_audio:
            current_count = doc.to_dict().get("audio_count", 0)
            update_data["audio_count"] = current_count + 1
            update_data["last_audio_time"] = now
            
        user_ref.update(update_data)
        return False

def update_stats(file_type, output_format):
    """Global statistikani yangilash"""
    stat_ref = db.collection('settings').document('stats')
    doc = stat_ref.get()
    
    if not doc.exists:
        stat_ref.set({
            "total_processed": 0, "audio": 0, "video": 0, 
            "format_txt": 0, "format_chat": 0
        })
    
    # Increment amallari
    increment = firestore.Increment(1)
    updates = {"total_processed": increment}
    
    if file_type == 'audio': updates["audio"] = increment
    else: updates["video"] = increment
        
    if output_format == 'txt': updates["format_txt"] = increment
    else: updates["format_chat"] = increment
        
    stat_ref.update(updates)

def get_all_users():
    """Barcha foydalanuvchilarni olish"""
    users = []
    docs = db.collection('users').order_by('joined_at', direction=firestore.Query.DESCENDING).stream()
    for doc in docs:
        users.append(doc.to_dict())
    return users

def get_stats():
    """Statistikani olish"""
    doc = db.collection('settings').document('stats').get()
    if doc.exists:
        return doc.to_dict()
    return {"total_processed": 0, "audio": 0, "format_txt": 0, "format_chat": 0}
