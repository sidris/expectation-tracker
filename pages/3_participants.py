import streamlit as st
import pandas as pd
from utils.db import fetch, insert

st.title("👥 Katılımcılar")

with st.form("participant"):
    name = st.text_input("Ad / kurum adı")
    ptype = st.selectbox("Tip", ["person","institution","media_poll"])
    institution_name = st.text_input("Bağlı kurum / yayın")
    title = st.text_input("Unvan")
    notes = st.text_area("Not")
    ok = st.form_submit_button("Kaydet")

if ok and name:
    insert("participants", {"name": name, "type": ptype, "institution_name": institution_name, "title": title, "notes": notes})
    st.success("Katılımcı kaydedildi.")

st.dataframe(pd.DataFrame(fetch("participants", order="name")), use_container_width=True)
