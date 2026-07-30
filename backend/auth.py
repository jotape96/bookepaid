import streamlit as st
from models import User

def check_auth():
    """Handle login and return the current user or None."""
    
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        st.title("BookepAId 💜💙")
        st.subheader("Welcome — please sign in")

        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if email and password:
                user = User.login(email, password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid email or password")
            else:
                st.error("Please enter your email and password")
        st.stop()

    return st.session_state.user