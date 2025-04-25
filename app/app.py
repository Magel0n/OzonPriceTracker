import os
import streamlit as st

api_url = os.environ.get("API_URL", "127.0.0.1")
api_port = int(os.environ.get("API_PORT", "12345"))

st.write("""
# My first app
Hello *world!*
""")