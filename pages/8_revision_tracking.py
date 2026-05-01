import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import fetch
from utils.export import apply_common_filters, excel_download_button
from utils.ui import inject_theme, plot_layout

inject_theme()
st.title("🔁 Revizyon Takibi")
st.caption("Aynı katılımcının aynı dönem/gösterge için zaman içindeki tahmin değişimlerini izleyin.")

df = pd.DataFrame(fetch("v_revision_history"))
if df.empty:
    st.info("Revizyon göstermek için tahmin girin.")
else:
    dff = apply_common_filters(df, key_prefix="rev")
    excel_download_button(dff, "revizyon_takibi.xlsx", "Revizyonları Excel indir")
    fig = px.line(dff.sort_values("forecast_date"), x="forecast_date", y="forecast_value", color="participant_name", markers=True, line_shape="spline", title="Tahmin revizyon çizgisi")
    st.plotly_chart(plot_layout(fig, height=520), use_container_width=True)
    st.dataframe(dff, use_container_width=True, hide_index=True)
