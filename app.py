"""Entry point.  Run with:  streamlit run app.py"""
import streamlit as st

from shared import background_switch, chart_theme, inject_css

st.set_page_config(page_title="Media Kit", page_icon="🌿", layout="wide")
inject_css()
chart_theme()

nav = st.navigation([
    st.Page("media_kit.py", title="Media kit", default=True),
    st.Page("creator.py", title="Creator analytics"),
    st.Page("calendar_page.py", title="Posting calendar", url_path="calendar"),
], position="hidden")
nav.run()
background_switch()  # bottom of every page
