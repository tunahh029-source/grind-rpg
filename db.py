from supabase import create_client
import streamlit as st
import uuid

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

if "player_id" not in st.session_state:
    st.session_state.player_id = str(uuid.uuid4())

PLAYER_ID = st.session_state.player_id



