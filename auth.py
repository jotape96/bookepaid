import streamlit as st
import os

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("BookePaid 💜💙")
        st.subheader("Welcome — please enter your access code")
        password = st.text_input("Access code", type="password")
        if st.button("Login"):
            raw = os.environ.get("APP_PASSWORDS") or st.secrets.get("APP_PASSWORDS", "")
            valid_passwords = [p.strip() for p in raw.split(",")]
            if password in valid_passwords:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect access code")
        st.stop()