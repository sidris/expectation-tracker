import streamlit as st
import pandas as pd
import plotly.express as px

from utils.db import fetch
from utils.ui import inject_theme

inject_theme()

st.title("📌 Konsensus Analizi")

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
    "abs_deviation_from_mean",
]

missing = [c for c in required_cols if c not in df.columns]

if missing:
    st.warning("Konsensus view'ında eksik kolon var.")
    st.write("Eksik kolonlar:", missing)
    st.dataframe(df)
    st.stop()

df["consensus_mean"] = pd.to_numeric(df["consensus_mean"], errors="coerce")
df["forecast_value"] = pd.to_numeric(df["forecast_value"], errors="coerce")
df["abs_deviation_from_mean"] = pd.to_numeric(df["abs_deviation_from_mean"], errors="coerce").fillna(0)

df = df.dropna(subset=["consensus_mean", "forecast_value"])

if df.empty:
    st.info("Grafik için yeterli sayısal veri yok.")
    st.stop()

st.dataframe(df, use_container_width=True)

fig = px.scatter(
    df,
    x="consensus_mean",
    y="forecast_value",
    color="participant_type",
    hover_name="participant_name",
    size="abs_deviation_from_mean",
    title="Konsensüse göre konum",
)

fig.update_layout(
    height=520,
    margin=dict(l=20, r=20, t=60, b=20),
)

st.plotly_chart(fig, use_container_width=True)