import streamlit as st
import pandas as pd
from utils.db import fetch, insert
from utils.export import excel_download_button
from utils.ui import inject_theme

inject_theme()
st.title("⭐ Kaynak Güven Skoru")

sources = pd.DataFrame(fetch("sources", order="name"))
scores = pd.DataFrame(fetch("v_source_scores"))
if sources.empty:
    st.info("Önce kaynak ekleyin.")
else:
    smap = {r["name"]: r["id"] for _, r in sources.iterrows()}
    with st.form("quality"):
        source = st.selectbox("Kaynak", list(smap.keys()))
        accuracy = st.slider("Doğruluk", 0.0, 5.0, 3.0, 0.5)
        speed = st.slider("Hız", 0.0, 5.0, 3.0, 0.5)
        transparency = st.slider("Şeffaflık", 0.0, 5.0, 3.0, 0.5)
        notes = st.text_area("Not")
        ok = st.form_submit_button("Değerlendirme kaydet")
    if ok:
        insert("source_quality_reviews", {"source_id": smap[source], "accuracy_score": accuracy, "speed_score": speed, "transparency_score": transparency, "notes": notes})
        st.success("Kaynak değerlendirmesi kaydedildi.")
    excel_download_button(scores, "kaynak_guven_skorlari.xlsx", "Skorları Excel indir")
    st.dataframe(scores, use_container_width=True, hide_index=True)
