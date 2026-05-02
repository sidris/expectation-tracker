"""Kaynak güven skoru — manuel değerlendirme + hesaplanan skor."""
import pandas as pd
import streamlit as st

from utils.db import fetch, insert, invalidate_cache
from utils.export import excel_download_button
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>⭐ Kaynak Güven Skoru</h1>
      <p>Her kaynak için hem manuel değerlendirme (doğruluk, hız, şeffaflık)
         hem de geçmiş hatadan hesaplanan skor.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

sources = pd.DataFrame(fetch("sources", order="name"))
scores = pd.DataFrame(fetch("v_source_scores"))

if sources.empty:
    st.info("Önce kaynak ekleyin.")
else:
    smap = {r["name"]: r["id"] for _, r in sources.iterrows()}
    with st.form("quality"):
        source = st.selectbox("Kaynak", list(smap.keys()))
        c1, c2, c3 = st.columns(3)
        accuracy = c1.slider("Doğruluk", 0.0, 5.0, 3.0, 0.5)
        speed = c2.slider("Hız", 0.0, 5.0, 3.0, 0.5)
        transparency = c3.slider("Şeffaflık", 0.0, 5.0, 3.0, 0.5)
        notes = st.text_area("Not")
        ok = st.form_submit_button("Değerlendirme kaydet", type="primary")
    if ok:
        insert(
            "source_quality_reviews",
            {
                "source_id": smap[source],
                "accuracy_score": accuracy,
                "speed_score": speed,
                "transparency_score": transparency,
                "notes": notes,
            },
        )
        invalidate_cache()
        st.success("Kaynak değerlendirmesi kaydedildi.")

    excel_download_button(scores, "kaynak_guven_skorlari.xlsx", "Skorları Excel indir")
    st.subheader("Mevcut kaynak skorları")
    st.dataframe(scores, use_container_width=True, hide_index=True)
