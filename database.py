import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pytz

UZ_TZ = pytz.timezone('Asia/Tashkent')

def get_uz_time():
    """Hozirgi vaqtni qaytaradi"""
    return datetime.now(UZ_TZ).strftime('%Y-%m-%d %H:%M:%S')

# --- FIREBASE ULANISHI ---
if not firebase_admin._apps:
    try:
        if "firebase" in st.secrets:
            cred_dict = dict(st.secrets["firebase"])
        else:
            cred_dict = dict(st.secrets)

        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"❌ Firebase ulanish xatosi (Secrets qismini tekshiring): {e}")
        st.stop()

try:
    db = firestore.client()
except Exception as e:
    st.error(f"❌ Firestore xatosi: {e}")
    st.stop()


# --- DB FUNKSIYALARI ---
def update_user(user, added_audio=False):
    """Foydalanuvchini bazaga qo'shish yoki yangilash"""
    try:
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
            return True
        else:
            update_data = {
                "name": user.full_name,
                "username": username,
                "last_active": now
            }
            if added_audio:
                update_data["audio_count"] = firestore.Increment(1)
                update_data["last_audio_time"] = now
            user_ref.update(update_data)
            return False
    except Exception as e:
        print(f"DB Update Error: {e}")
        return False

def update_stats(file_type, output_format):
    """Statistikani yangilash"""
    try:
        stat_ref = db.collection('settings').document('stats')
        if not stat_ref.get().exists:
            stat_ref.set({"total_processed": 0, "audio": 0, "video": 0, "format_txt": 0, "format_chat": 0, "page_views": 0})
        
        batch = db.batch()
        batch.update(stat_ref, {"total_processed": firestore.Increment(1)})
        
        if file_type == 'audio': 
            batch.update(stat_ref, {"audio": firestore.Increment(1)})
        else: 
            batch.update(stat_ref, {"video": firestore.Increment(1)})
            
        if output_format == 'txt': 
            batch.update(stat_ref, {"format_txt": firestore.Increment(1)})
        else: 
            batch.update(stat_ref, {"format_chat": firestore.Increment(1)})
            
        batch.commit()
    except Exception as e:
        print(f"Stats Error: {e}")

def increment_page_view():
    """Saytga tashriflarni sanash"""
    try:
        stat_ref = db.collection('settings').document('stats')
        if not stat_ref.get().exists:
            stat_ref.set({"total_processed": 0, "audio": 0, "video": 0, "format_txt": 0, "format_chat": 0, "page_views": 0})
        stat_ref.update({"page_views": firestore.Increment(1)})
    except Exception: 
        pass

def get_all_users():
    """Barcha foydalanuvchilarni olish"""
    try:
        users = []
        docs = db.collection('users').order_by('joined_at', direction=firestore.Query.DESCENDING).stream()
        for doc in docs: 
            users.append(doc.to_dict())
        return users
    except Exception: 
        return []

def get_stats():
    """Barcha statistikani olish"""
    try:
        doc = db.collection('settings').document('stats').get()
        if doc.exists: 
            return doc.to_dict()
        return {}
    except Exception: 
        return {}


# --- TRANSKRIPTLAR (MATNLAR) UCHUN FUNKSIYALAR ---
def save_transcript(user_id, text, audio_name="Audio"):
    """Foydalanuvchi matnini Firebasega saqlash"""
    try:
        now = get_uz_time()
        final_name = f"{audio_name}_{now.replace(':', '-').replace(' ', '_')}" 
        
        doc_ref = db.collection('transcripts').document()
        doc_ref.set({
            "user_id": str(user_id),
            "audio_name": final_name,
            "text": text,
            "created_at": now
        })
    except Exception as e:
        print(f"Save Transcript Error: {e}")

def get_user_transcripts(user_id):
    """Bitta foydalanuvchining barcha matnlarini ID orqali olish"""
    try:
        docs = db.collection('transcripts').where('user_id', '==', str(user_id)).stream()
        res = [{"id": d.id, **d.to_dict()} for d in docs]
        res.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return res
    except Exception: 
        return []

def get_transcript_by_id(doc_id):
    """Aniq bitta matn hujjatini ID orqali olish"""
    try:
        doc = db.collection('transcripts').document(doc_id).get()
        if doc.exists: 
            return doc.to_dict()
        return None
    except Exception: 
        return None
        
