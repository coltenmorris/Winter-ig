"""Entry point.  Run with:  streamlit run app.py"""
import streamlit as st

from shared import chart_theme, inject_css

st.set_page_config(page_title="Media Kit", page_icon="🌿", layout="wide")
inject_css()
chart_theme()

nav = st.navigation([
    st.Page("media_kit.py", title="Media kit", default=True),
    st.Page("creator.py", title="Creator analytics"),
], position="hidden")
nav.run()
