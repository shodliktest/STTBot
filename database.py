"""Small Firestore metadata/index layer.

Large objects (audio and transcript JSON) are intentionally NOT stored in Firestore.
They live in a private Telegram channel. Firestore stores only small references.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pytz
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

UZ_TZ = pytz.timezone("Asia/Tashkent")
_STATS_DEFAULTS = {
    "total_processed": 0,
    "audio": 0,
    "video": 0,
    "format_txt": 0,
    "format_chat": 0,
    "page_views": 0,
}
_db = None


def get_uz_time() -> str:
    return datetime.now(UZ_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _init_db():
    global _db
    if _db is not None:
        return _db
    if firebase_admin._apps:
        _db = firestore.client()
        return _db

    cred_dict = None
    if "firebase" in st.secrets:
        cred_dict = dict(st.secrets["firebase"])
    elif "FIREBASE_SERVICE_ACCOUNT" in st.secrets:
        cred_dict = dict(st.secrets["FIREBASE_SERVICE_ACCOUNT"])
    else:
        # Backward compatible with the old flat secret layout.
        possible = {k: st.secrets[k] for k in ("type", "project_id", "private_key_id", "private_key", "client_email", "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url", "client_x509_cert_url") if k in st.secrets}
        if possible:
            cred_dict = possible

    if not cred_dict:
        raise RuntimeError("Firebase service-account Secrets topilmadi.")
    if "private_key" in cred_dict:
        cred_dict["private_key"] = str(cred_dict["private_key"]).replace("\\n", "\n")
    firebase_admin.initialize_app(credentials.Certificate(cred_dict))
    _db = firestore.client()
    return _db


# Keep import-time initialization out of bot modules. Streamlit can still show a
# clear error when the dashboard actually needs Firebase.
def get_db():
    return _init_db()


def update_user(user, added_audio: bool = False) -> bool:
    db = get_db()
    ref = db.collection("users").document(str(user.id))
    snap = ref.get()
    now = get_uz_time()
    username = f"@{user.username}" if user.username else "Mavjud emas"
    if not snap.exists:
        ref.set({
            "id": str(user.id),
            "name": user.full_name,
            "username": username,
            "joined_at": now,
            "last_active": now,
            "audio_count": 1 if added_audio else 0,
            "last_audio_time": now if added_audio else "Hali yubormagan",
        })
        # Small daily aggregate for the dashboard; never scan all users for a graph.
        day = now[:10]
        db.collection("daily_stats").document(day).set({
            "date": day, "new_users": firestore.Increment(1)
        }, merge=True)
        return True
    data = {"name": user.full_name, "username": username, "last_active": now}
    if added_audio:
        data.update(audio_count=firestore.Increment(1), last_audio_time=now)
    ref.update(data)
    return False


def _ensure_stats(ref):
    if not ref.get().exists:
        ref.set(dict(_STATS_DEFAULTS))


def update_stats(file_type: str, output_format: str):
    db = get_db()
    ref = db.collection("settings").document("stats")
    _ensure_stats(ref)
    updates = {"total_processed": firestore.Increment(1)}
    updates["audio" if file_type == "audio" else "video"] = firestore.Increment(1)
    updates["format_txt" if output_format == "txt" else "format_chat"] = firestore.Increment(1)
    ref.update(updates)


def increment_page_view():
    try:
        db = get_db()
        ref = db.collection("settings").document("stats")
        _ensure_stats(ref)
        ref.update({"page_views": firestore.Increment(1)})
    except Exception as exc:
        print(f"Page view error: {exc}")


def get_stats() -> dict[str, Any]:
    try:
        snap = get_db().collection("settings").document("stats").get()
        return snap.to_dict() if snap.exists else {}
    except Exception as exc:
        print(f"Stats read error: {exc}")
        return {}


def get_user_count() -> int:
    try:
        # count() avoids downloading every user document.
        agg = get_db().collection("users").count().get()
        return int(agg[0][0].value)
    except Exception:
        # Fallback only if the SDK/backend doesn't support aggregation.
        return sum(1 for _ in get_db().collection("users").stream())


def get_users_page(limit: int = 50, start_after: Optional[dict] = None) -> list[dict]:
    """Read only one dashboard page, never the complete user collection."""
    query = get_db().collection("users").order_by("joined_at", direction=firestore.Query.DESCENDING).limit(limit)
    if start_after:
        query = query.start_after(start_after)
    docs = list(query.stream())
    return [{"_doc_id": d.id, **d.to_dict()} for d in docs]


def get_daily_user_growth(limit_days: int = 90) -> list[dict]:
    """Small pre-aggregated graph source; no full users scan."""
    docs = get_db().collection("daily_stats").order_by("date", direction=firestore.Query.DESCENDING).limit(limit_days).stream()
    rows = [d.to_dict() for d in docs]
    return list(reversed(rows))


def _safe_id(value: str) -> str:
    value = str(value).strip()
    if not value or len(value) > 256 or "/" in value:
        raise ValueError("Noto'g'ri Firestore ID")
    return value


def get_audio_index(file_hash: str) -> Optional[dict]:
    try:
        snap = get_db().collection("audio_index").document(_safe_id(file_hash)).get()
        return snap.to_dict() if snap.exists else None
    except Exception as exc:
        print(f"Audio index read error: {exc}")
        return None


def save_audio_index(file_hash: str, data: dict):
    payload = dict(data)
    payload["file_hash"] = file_hash
    payload["updated_at"] = get_uz_time()
    get_db().collection("audio_index").document(_safe_id(file_hash)).set(payload, merge=True)


def update_audio_status(file_hash: str, status: str, **fields):
    payload = {"status": status, "updated_at": get_uz_time(), **fields}
    get_db().collection("audio_index").document(_safe_id(file_hash)).set(payload, merge=True)


def save_user_mode(user_id: int, mode: str):
    get_db().collection("users").document(str(user_id)).set({"mode": mode}, merge=True)


def get_user_transcripts(user_id: str) -> list[dict]:
    """Compatibility helper. Actual transcript bodies are in Telegram DB.
    Returns only the small index records for the selected user."""
    docs = get_db().collection("audio_index").where("user_id", "==", str(user_id)).stream()
    res = [{"id": d.id, **d.to_dict()} for d in docs]
    res.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return res


def get_transcript_by_id(doc_id: str) -> Optional[dict]:
    try:
        snap = get_db().collection("audio_index").document(_safe_id(doc_id)).get()
        return snap.to_dict() if snap.exists else None
    except Exception:
        return None


# Backward-compatible names. They now only touch the small Firebase index.
def save_audio_cache(file_hash: str, segments: list[dict], **refs):
    save_audio_index(file_hash, {"status": "completed", "segments_count": len(segments), **refs})


def get_audio_cache(file_hash: str):
    item = get_audio_index(file_hash)
    return item if item and item.get("status") == "completed" else None
