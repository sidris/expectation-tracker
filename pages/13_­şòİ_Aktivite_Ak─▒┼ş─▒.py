import streamlit as st
import pandas as pd
from utils.db import fetch, insert
from utils.ui import inject_theme

inject_theme()
st.title("🕘 Aktivite Akışı")
with st.form("activity"):
    activity_type = st.selectbox("Tip", ["forecast", "actual", "poll", "source", "note", "system"])
    title = st.text_input("Başlık")
    details = st.text_area("Detay")
    ok = st.form_submit_button("Akışa ekle")
if ok and title:
    insert("activity_log", {"activity_type": activity_type, "title": title, "details": details})
    st.success("Aktivite eklendi.")

df = pd.DataFrame(fetch("activity_log", order="created_at", limit=500))
st.dataframe(df, use_container_width=True, hide_index=True)
