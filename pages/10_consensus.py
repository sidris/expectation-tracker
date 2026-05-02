"""Konsensus analizi — tahminlerin ortalamadan/medyandan sapması."""
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.db import fetch
from utils.ui import inject_theme, plot_layout

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>📌 Konsensus Analizi</h1>
      <p>Her tahmincinin konsensüse (medyan/ortalama) göre konumu. Boxplot
         dışındaki "uç" tahminciler ve konsensusla uyumlu olanlar burada görülür.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    df = pd.DataFrame(fetch("v_consensus_analysis"))
except Exception as e:
    st.error("Konsensus verisi okunamadı.")
    st.code(str(e))
    st.stop()

if df.empty:
    st.info("Henüz konsensus analizi için yeterli tahmin yok.")
    st.stop()

required_cols = [
    "consensus_mean",
    "forecast_value",
    "participant_type",
    "participant_name",
    "deviation_from_median",
]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.warning("Konsensus view'ında eksik kolon var.")
    st.write("Eksik kolonlar:", missing)
    st.dataframe(df)
    st.stop()

df["consensus_mean"] = pd.to_numeric(df["consensus_mean"], errors="coerce")
df["forecast_value"] = pd.to_numeric(df["forecast_value"], errors="coerce")
df["deviation_from_median"] = pd.to_numeric(df["deviation_from_median"], errors="coerce").fillna(0)
df["abs_deviation"] = df["deviation_from_median"].abs()
df = df.dropna(subset=["consensus_mean", "forecast_value"])

if df.empty:
    st.info("Grafik için yeterli sayısal veri yok.")
    st.stop()

st.subheader("Konsensüse göre konum")
fig = px.scatter(
    df,
    x="consensus_mean",
    y="forecast_value",
    color="participant_type",
    hover_name="participant_name",
    size="abs_deviation",
    title="Tahminin konsensüse göre konumu (45° çizgi = tam uyum)",
)
# 45° referans çizgisi
import numpy as np
lo = float(min(df["consensus_mean"].min(), df["forecast_value"].min()))
hi = float(max(df["consensus_mean"].max(), df["forecast_value"].max()))
fig.add_shape(
    type="line", x0=lo, y0=lo, x1=hi, y1=hi,
    line=dict(color="#9ca3af", dash="dash", width=1),
)
st.plotly_chart(plot_layout(fig, height=520), use_container_width=True)

st.subheader("En çok sapan tahminciler")
top_dev = (
    df.groupby("participant_name", as_index=False)
    .agg(
        ortalama_sapma=("deviation_from_median", "mean"),
        ortalama_mutlak_sapma=("abs_deviation", "mean"),
        tahmin_sayisi=("forecast_value", "count"),
    )
    .sort_values("ortalama_mutlak_sapma", ascending=False)
    .head(20)
)
st.dataframe(top_dev, use_container_width=True, hide_index=True)

st.subheader("Tüm konsensus verisi")
st.dataframe(df, use_container_width=True, hide_index=True)
