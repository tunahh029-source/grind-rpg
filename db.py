from supabase import create_client
import streamlit as st
import uuid

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

PLAYER_ID = "demo-player"  # sau này đổi thành user login
