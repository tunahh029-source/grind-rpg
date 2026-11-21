"""Kết nối Supabase + lưu/tải dữ liệu cho một người chơi duy nhất.

UserID cố định: dùng PLAYER_ID trong secrets nếu có, không thì dùng giá trị mặc định bên dưới.
Đừng đổi ID này sau khi đã chơi, nếu không app sẽ coi là nhân vật mới.
"""
import time
import uuid

import streamlit as st
from supabase import create_client

DEFAULT_PLAYER_ID = "7b1f3c9e-5a42-4d6e-9c1a-2f8d0e6b4a37"
TABLE = "players"
BACKUP_EVERY_SECONDS = 24 * 3600  # sao lưu tự động tối đa 1 lần/ngày
SAVE_RETRIES = 3

try:
    _URL = st.secrets["SUPABASE_URL"]
    _KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("❌ Thiếu SUPABASE_URL / SUPABASE_KEY trong Streamlit secrets (xem README.md).")
    st.stop()

PLAYER_ID = str(st.secrets.get("PLAYER_ID", DEFAULT_PLAYER_ID))
AUTO_BACKUP_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"grind-rpg/auto-backup/{PLAYER_ID}"))
RESET_BACKUP_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"grind-rpg/reset-backup/{PLAYER_ID}"))


@st.cache_resource
def _client(url, key):
    return create_client(url, key)


supabase = _client(_URL, _KEY)


def fetch_player():
    """Trả về (đã_có_dòng, dữ_liệu). Ném lỗi nếu không đọc được."""
    res = supabase.table(TABLE).select("data").eq("id", PLAYER_ID).execute()
    rows = res.data or []
    if not rows:
        return False, None
    return True, rows[0].get("data")


def insert_player(data):
    """Tạo nhân vật mới. Dùng insert (không upsert) để không bao giờ ghi đè dòng đã có."""
    supabase.table(TABLE).insert({"id": PLAYER_ID, "data": data}).execute()


def _upsert(row_id, data):
    last_err = None
    for attempt in range(SAVE_RETRIES):
        try:
            supabase.table(TABLE).upsert({"id": row_id, "data": data}).execute()
            return
        except Exception as e:  # thử lại khi mạng chập chờn
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise last_err


def save_player(data):
    """Lưu toàn bộ tiến trình (có thử lại). Ném lỗi nếu cả 3 lần đều thất bại."""
    now = time.time()
    data["last_updated"] = now
    need_backup = now - data.get("last_backup", 0) > BACKUP_EVERY_SECONDS
    if need_backup:
        data["last_backup"] = now
    _upsert(PLAYER_ID, data)
    if need_backup:
        backup_player(data, "auto")


def backup_player(data, tag="auto"):
    """Sao lưu vào một dòng riêng (không làm hỏng luồng chính nếu lỗi)."""
    row_id = RESET_BACKUP_ID if tag == "reset" else AUTO_BACKUP_ID
    try:
        _upsert(row_id, data)
        return True
    except Exception:
        return False
