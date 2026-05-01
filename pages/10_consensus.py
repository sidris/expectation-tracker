import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import fetch
from utils.export import apply_common_filters, excel_download_button
from utils.ui import inject_theme, plot_layout

inject_theme()
st.title("🎯 Konsensüs Sapması")
st.caption("Katılımcı tahminlerini aynı dönem/gösterge ortalaması ve medyanından sapmaya göre analiz eder.")

df = pd.DataFrame(fetch("v_consensus_analysis"))
if df.empty:
    st.info("Konsensüs analizi için tahmin girin.")
else:
    dff = apply_common_filters(df, key_prefix="consensus")
    excel_download_button(dff, "konsensus_analizi.xlsx", "Konsensüs analizini Excel indir")
    fig = px.scatter(dff, x="consensus_mean", y="forecast_value", color="participant_type", hover_name="participant_name", size="abs_deviation_from_mean", title="Konsensüse göre konum")
    fig.add_shape(type="line", x0=dff["consensus_mean"].min(), y0=dff["consensus_mean"].min(), x1=dff["consensus_mean"].max(), y1=dff["consensus_mean"].max(), line=dict(dash="dash"))
    st.plotly_chart(plot_layout(fig, height=520), use_container_width=True)
    st.dataframe(dff.sort_values("abs_deviation_from_mean"), use_container_width=True, hide_index=True)
