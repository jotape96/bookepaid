import streamlit as st


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("BookePaid 💜💙")
        st.subheader("Welcome — please enter your access code")
        password = st.text_input("Access code", type="password")
        if st.button("Login"):
            valid_passwords = st.secrets.get("APP_PASSWORDS", "").split(",")
            valid_passwords = [p.strip() for p in valid_passwords]
            st.write(f"Debug — valid passwords: {valid_passwords}")  # temporary
            if password in valid_passwords:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect access code")
        st.stop()