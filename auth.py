import streamlit as st
from supabase import create_client, Client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class User:
    def __init__(self, user_id, email, role="owner", name=None):
        self.id = user_id
        self.email = email
        self.name = name or email.split("@")[0].capitalize()
        self.role = role
        self.business_id = user_id  # Ties the business strictly to this user

    def logout(self):
        supabase.auth.sign_out()
        for key in list(st.session_state.keys()):
            del st.session_state[key]

def check_auth():
    # 1. Initialize state keys
    if "user" not in st.session_state:
        st.session_state.user = None

    # 2. Return cached user if already logged in
    if st.session_state.user is not None:
        return st.session_state.user

    # 3. If not logged in, render the login form and stop execution
    st.subheader("Login to BookepAId")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            # Construct your existing User class using Supabase's authenticated details
            st.session_state.user = User(
                user_id=res.user.id,
                email=res.user.email,
                role="owner"  # or fetch from a user_profiles table if needed
            )
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")

    st.stop()