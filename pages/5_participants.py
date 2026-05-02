"""Katılımcılar (kişi ve kurumlar)."""
import pandas as pd
import streamlit as st

from utils.db import fetch, insert, invalidate_cache
from utils.domain import PARTICIPANT_TYPES, PARTICIPANT_TYPE_LABELS
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>👥 Katılımcılar</h1>
      <p>Tahmin verisi gelen kişi ve kurumlar (Albaraka, QNB, Deutsche Bank,
         köşe yazarları vb.).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("participant"):
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Ad / kurum adı")
        ptype_label = st.selectbox(
            "Tip", [PARTICIPANT_TYPE_LABELS[t] for t in PARTICIPANT_TYPES],
        )
    with c2:
        institution_name = st.text_input("Bağlı kurum / yayın")
        title = st.text_input("Unvan")

    notes = st.text_area("Not")
    ok = st.form_submit_button("Kaydet", type="primary")

if ok and name:
    label_to_type = {v: k for k, v in PARTICIPANT_TYPE_LABELS.items()}
    insert(
        "participants",
        {
            "name": name,
            "type": label_to_type.get(ptype_label, "person"),
            "institution_name": institution_name,
            "title": title,
            "notes": notes,
        },
    )
    invalidate_cache()
    st.success("Katılımcı kaydedildi.")

st.subheader("Mevcut katılımcılar")
st.dataframe(
    pd.DataFrame(fetch("participants", order="name")),
    use_container_width=True,
    hide_index=True,
)
