import os
import streamlit as st
from supabase import create_client

def get_client():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)
