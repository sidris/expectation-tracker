import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import fetch
from utils.export import excel_download_button
from utils.ui import inject_theme, plot_layout, medal_card

inject_theme()
st.title("👤 Tahminci Profili")
profiles = pd.DataFrame(fetch("v_participant_profiles"))
forecasts = pd.DataFrame(fetch("v_forecasts"))
if profiles.empty:
    st.info("Önce katılımcı ve tahmin girin.")
else:
    names = profiles["participant_name"].dropna().sort_values().tolist()
    selected = st.selectbox("Tahminci / kurum seç", names)
    p = profiles[profiles["participant_name"] == selected].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam tahmin", int(p.get("total_forecasts") or 0))
    c2.metric("Skorlanan", int(p.get("scored_forecasts") or 0))
    c3.metric("Ort. mutlak hata", p.get("avg_abs_error") if pd.notna(p.get("avg_abs_error")) else "-")
    c4.metric("Son tahmin", str(p.get("last_forecast_date") or "-"))
    st.markdown(f"### {selected}")
    st.write(f"**Tip:** {p.get('participant_type')}  ")
    st.write(f"**Kurum/Unvan:** {p.get('institution_name') or ''} {p.get('title') or ''}")
    st.write(f"**Uzmanlık:** {p.get('expertise') or '-'}")
    pf = forecasts[forecasts["participant_name"] == selected] if not forecasts.empty else pd.DataFrame()
    if not pf.empty:
        fig = px.line(pf.sort_values("target_period"), x="target_period", y="forecast_value", color="target_type", markers=True, line_shape="spline", title="Tahmin geçmişi")
        st.plotly_chart(plot_layout(fig, height=480), use_container_width=True)
        excel_download_button(pf, f"{selected}_tahminleri.xlsx", "Bu tahmincinin verilerini Excel indir")
        st.dataframe(pf, use_container_width=True, hide_index=True)
