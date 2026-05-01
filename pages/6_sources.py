import streamlit as st
import pandas as pd
from datetime import datetime
from utils.db import fetch, insert

st.title("📰 Kaynaklar")

with st.form("source"):
    name = st.text_input("Kaynak adı", placeholder="Bloomberg HT, Reuters, TV programı, köşe yazısı...")
    stype = st.selectbox("Tip", ["tv","column","report","survey","news","manual","other"])
    publisher = st.text_input("Yayıncı")
    url = st.text_input("URL")
    notes = st.text_area("Not")
    ok = st.form_submit_button("Kaydet")

if ok and name:
    insert("sources", {"name": name, "type": stype, "publisher": publisher, "url": url, "notes": notes})
    st.success("Kaynak kaydedildi.")

st.dataframe(pd.DataFrame(fetch("sources", order="captured_at")), use_container_width=True)
