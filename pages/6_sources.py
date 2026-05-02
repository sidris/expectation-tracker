"""Kaynaklar (haber kanalı, anket sahibi, TV programı vb.)."""
import pandas as pd
import streamlit as st

from utils.db import fetch, insert, invalidate_cache
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>📰 Kaynaklar</h1>
      <p>Tahmin verisinin geldiği kanallar: Reuters, Bloomberg HT, Matriks, AA Finans,
         köşe yazıları, TV programları.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

SOURCE_TYPES = ["news", "survey", "tv", "column", "report", "manual", "other"]
SOURCE_TYPE_LABELS = {
    "news": "Haber ajansı / portal",
    "survey": "Anket sahibi",
    "tv": "TV programı",
    "column": "Köşe yazısı",
    "report": "Rapor",
    "manual": "Manuel giriş",
    "other": "Diğer",
}

with st.form("source"):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input(
            "Kaynak adı",
            placeholder="Bloomberg HT, Reuters, TV programı, köşe yazısı...",
        )
        stype_label = st.selectbox(
            "Tip", [SOURCE_TYPE_LABELS[t] for t in SOURCE_TYPES],
        )
    with c2:
        publisher = st.text_input("Yayıncı")
        url = st.text_input("URL")

    notes = st.text_area("Not")
    ok = st.form_submit_button("Kaydet", type="primary")

if ok and name:
    label_to_type = {v: k for k, v in SOURCE_TYPE_LABELS.items()}
    insert(
        "sources",
        {
            "name": name,
            "type": label_to_type.get(stype_label, "other"),
            "publisher": publisher,
            "url": url,
            "notes": notes,
        },
    )
    invalidate_cache()
    st.success("Kaynak kaydedildi.")

st.subheader("Mevcut kaynaklar")
st.dataframe(
    pd.DataFrame(fetch("sources", order="captured_at", desc=True)),
    use_container_width=True,
    hide_index=True,
)
