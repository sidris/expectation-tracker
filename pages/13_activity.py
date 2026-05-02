"""Aktivite akışı — sistemde yapılan tüm önemli işlemlerin logu."""
import pandas as pd
import streamlit as st

from utils.db import fetch
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>🕘 Aktivite Akışı</h1>
      <p>Sistemde yapılan kayıt, düzenleme ve sync işlemleri. Otomatik loglanır;
         manuel giriş yapılmaz.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

df = pd.DataFrame(fetch("activity_log", order="created_at", desc=True, limit=500))

if df.empty:
    st.info("Henüz aktivite kaydı yok.")
else:
    # Tip bazında basit filtre
    if "activity_type" in df.columns:
        types = sorted(df["activity_type"].dropna().unique())
        selected = st.multiselect(
            "Aktivite tipine göre filtrele", types, default=types,
        )
        if selected:
            df = df[df["activity_type"].isin(selected)]

    st.dataframe(df, use_container_width=True, hide_index=True)
