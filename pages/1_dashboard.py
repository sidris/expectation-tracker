import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.db import fetch
from utils.export import apply_common_filters, excel_download_button, add_display_labels
from utils.ui import inject_theme, styled_line, plot_layout

inject_theme()
st.markdown("""
<div class="hero">
  <h1>📈 Dashboard</h1>
  <p>Filtrelenebilir tahminler, gerçekleşmeler, trendler, ısı haritası ve madalya kürsüsü.</p>
</div>
""", unsafe_allow_html=True)

raw = add_display_labels(pd.DataFrame(fetch("v_forecasts")))
if raw.empty:
    st.info("Henüz tahmin yok.")
    st.stop()
raw["target_period"] = pd.to_datetime(raw["target_period"], errors="coerce")
raw["forecast_date"] = pd.to_datetime(raw["forecast_date"], errors="coerce")
dff = apply_common_filters(raw, key_prefix="dash")
if dff.empty:
    st.warning("Filtrelere uyan kayıt yok.")
    st.stop()

excel_download_button(dff, "filtreli_tahminler.xlsx", "Filtreli tahminleri Excel indir")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tahmin sayısı", len(dff), "+ filtreli")
c2.metric("Katılımcı", dff["participant_name"].nunique())
c3.metric("Kaynak", dff["source_name"].nunique() if "source_name" in dff else 0)
c4.metric("Skorlanan", int(dff["actual_value"].notna().sum()))

st.markdown("### 🏅 Madalya Kürsüsü")
lb = pd.DataFrame(fetch("v_leaderboard"))
if not lb.empty and "target_type" in dff.columns:
    lb = lb[lb["target_type"].isin(dff["target_type"].dropna().unique())]
if not lb.empty:
    top3 = lb.sort_values("mean_abs_error").head(3)
    cols = st.columns(3)
    medals = ["🥇", "🥈", "🥉"]
    for i, (_, r) in enumerate(top3.iterrows()):
        cols[i].markdown(f'''
        <div class="medal-card">
          <div class="medal">{medals[i]}</div>
          <div class="name">{r['participant_name']}</div>
          <div class="score">Ortalama hata: {r['mean_abs_error']:.2f}<br>{int(r['scored_count'])} skorlanmış tahmin</div>
        </div>
        ''', unsafe_allow_html=True)
else:
    st.caption("Madalya için en az 2 gerçekleşmiş tahmin gerekiyor.")

st.markdown("### Trend: tahminler ve gerçekleşme")
trend_mode = st.radio("Trend görünümü", ["Katılımcı bazlı", "Gösterge ortalaması"], horizontal=True)
if trend_mode == "Katılımcı bazlı":
    fig = styled_line(dff.sort_values("target_period"), x="target_period", y="forecast_value", color="participant_name", title="Tahmin trendi")
else:
    avg = dff.groupby(["target_period", "target_type_label"], as_index=False).agg(forecast_value=("forecast_value", "mean"), actual_value=("actual_value", "mean"))
    fig = styled_line(avg.sort_values("target_period"), x="target_period", y="forecast_value", color="target_type_label", title="Ortalama beklenti trendi", fill=True)
actual = dff.dropna(subset=["actual_value"]).drop_duplicates(["target_period", "target_type"])
if not actual.empty:
    fig.add_trace(go.Scatter(x=actual["target_period"], y=actual["actual_value"], mode="lines+markers", name="Gerçekleşme", line=dict(width=4, color="#111827", dash="dot", shape="spline"), marker=dict(size=8, color="#111827")))
st.plotly_chart(fig, use_container_width=True)



st.markdown("### 📦 Anket / kurum dağılımı")
box_df = dff.dropna(subset=["forecast_value"]).copy()
if not box_df.empty:
    box_df["group_label"] = box_df["poll_name"].fillna(box_df["event_label"])
    fig_box = px.box(
        box_df,
        x="group_label",
        y="forecast_value",
        points="all",
        color="target_type_label" if "target_type_label" in box_df.columns else None,
        hover_data=["participant_name", "forecast_date", "poll_name"],
        title="Anket ve kurum cevapları dağılımı",
    )
    st.plotly_chart(plot_layout(fig_box, height=520), use_container_width=True)
else:
    st.info("Boxplot için tahmin verisi girin.")

st.markdown("### Isı haritası: mutlak hata")
heat = dff.dropna(subset=["abs_error"]).pivot_table(index="participant_name", columns="target_period", values="abs_error", aggfunc="mean")
if not heat.empty:
    fig2 = px.imshow(heat, aspect="auto", labels=dict(color="Mutlak hata"), color_continuous_scale="Purples")
    st.plotly_chart(plot_layout(fig2, height=520), use_container_width=True)
else:
    st.info("Isı haritası için gerçekleşme verisi girin.")

st.markdown("### Filtreli veri")
st.dataframe(dff, use_container_width=True, hide_index=True)
