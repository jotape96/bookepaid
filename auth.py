import streamlit as st


def check_password():
    """Simple password gate using Streamlit secrets."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("BookePaid 💜💙")
        st.subheader("Welcome — please enter your access code")
        password = st.text_input("Access code", type="password")
        if st.button("Login"):
            if password == st.secrets.get("APP_PASSWORD", ""):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect access code")
        st.stop()
