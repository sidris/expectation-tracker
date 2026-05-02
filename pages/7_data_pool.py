"""Tüm verilerin tek noktadan görüntülenip indirildiği havuz."""
from io import BytesIO

import pandas as pd
import streamlit as st

from utils.db import fetch
from utils.export import apply_common_filters, excel_download_button
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>🗃️ Veri Havuzu</h1>
      <p>Sistemdeki tüm tahmin, anket, gerçekleşme, katılımcı ve kaynak verileri
         tek yerden görüntülenip Excel'e indirilebilir.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "Tahminler", "Anket özetleri", "Gerçekleşmeler",
    "Katılımcılar", "Kaynaklar", "Tüm Excel paketi",
])

with tabs[0]:
    df = pd.DataFrame(fetch("v_forecasts"))
    dff = apply_common_filters(df, key_prefix="pool_forecasts") if not df.empty else df
    excel_download_button(dff, "tahmin_havuzu.xlsx", "Tahmin havuzunu Excel indir")
    st.dataframe(dff, use_container_width=True, hide_index=True)

with tabs[1]:
    df = pd.DataFrame(fetch("v_poll_summaries"))
    dff = apply_common_filters(df, key_prefix="pool_polls") if not df.empty else df
    excel_download_button(dff, "anket_ozetleri.xlsx", "Anket özetlerini Excel indir")
    st.dataframe(dff, use_container_width=True, hide_index=True)

with tabs[2]:
    df = pd.DataFrame(fetch("actuals"))
    excel_download_button(df, "gerceklesmeler.xlsx", "Gerçekleşmeleri Excel indir")
    st.dataframe(df, use_container_width=True, hide_index=True)

with tabs[3]:
    df = pd.DataFrame(fetch("participants", order="name"))
    excel_download_button(df, "katilimcilar.xlsx", "Katılımcıları Excel indir")
    st.dataframe(df, use_container_width=True, hide_index=True)

with tabs[4]:
    df = pd.DataFrame(fetch("sources", order="captured_at", desc=True))
    excel_download_button(df, "kaynaklar.xlsx", "Kaynakları Excel indir")
    st.dataframe(df, use_container_width=True, hide_index=True)

with tabs[5]:
    datasets = {
        "tahminler": pd.DataFrame(fetch("v_forecasts")),
        "anket_ozetleri": pd.DataFrame(fetch("v_poll_summaries")),
        "gerceklesmeler": pd.DataFrame(fetch("actuals")),
        "katilimcilar": pd.DataFrame(fetch("participants")),
        "kaynaklar": pd.DataFrame(fetch("sources")),
        "leaderboard": pd.DataFrame(fetch("v_leaderboard")),
    }
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, data in datasets.items():
            data.to_excel(writer, index=False, sheet_name=name[:31])
    st.download_button(
        "📦 Tüm verileri tek Excel dosyası olarak indir",
        output.getvalue(),
        "beklenti_takip_tum_veriler.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
