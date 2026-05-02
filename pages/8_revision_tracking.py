"""Revizyon takibi — aynı katılımcının zaman içindeki tahmin değişimleri."""
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db import fetch
from utils.export import apply_common_filters, excel_download_button
from utils.ui import inject_theme, plot_layout

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>🔁 Revizyon Takibi</h1>
      <p>Aynı katılımcının aynı hedef dönem ve gösterge için zaman içindeki
         tahmin değişimleri. Örn: 11.04.2026 → 28, 18.04.2026 → 30.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

df = pd.DataFrame(fetch("v_revision_history"))
if df.empty:
    st.info("Revizyon göstermek için en az bir tahmin girin.")
else:
    dff = apply_common_filters(df, key_prefix="rev")
    excel_download_button(dff, "revizyon_takibi.xlsx", "Revizyonları Excel indir")

    if not dff.empty:
        st.subheader("Revizyon çizgisi")
        fig = px.line(
            dff.sort_values("forecast_date"),
            x="forecast_date",
            y="forecast_value",
            color="participant_name",
            markers=True,
            line_shape="spline",
            hover_data=["event_label", "revision_no", "previous_forecast", "revision_delta", "poll_name"],
            title="Tahmin revizyonları",
        )
        st.plotly_chart(plot_layout(fig, height=520), use_container_width=True)

        st.subheader("Revizyon ısı haritası")
        heat = dff.copy()
        heat["forecast_date_str"] = pd.to_datetime(
            heat["forecast_date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        pivot = heat.pivot_table(
            index="participant_name",
            columns="forecast_date_str",
            values="forecast_value",
            aggfunc="last",
        )
        if not pivot.empty:
            fig_h = px.imshow(
                pivot,
                aspect="auto",
                labels=dict(x="Tahmin tarihi", y="Katılımcı", color="Tahmin"),
                title="Tahmin revizyon ısı haritası",
            )
            st.plotly_chart(plot_layout(fig_h, height=520), use_container_width=True)

        st.subheader("Revizyon tablosu")
        st.dataframe(dff, use_container_width=True, hide_index=True)
