import streamlit as st
import pandas as pd
from datetime import date
from utils.db import fetch, upsert

st.title("✅ Gerçekleşmeler")

events = fetch("forecast_events", order="target_period")
emap = {f"{e['target_period']} / {e['target_type']}": e["id"] for e in events}

with st.form("actual"):
    event_label = st.selectbox("Dönem / gösterge", list(emap.keys()) if emap else [])
    actual_value = st.number_input("Gerçekleşme", step=0.01, format="%.4f")
    released_at = st.date_input("Açıklanma tarihi", value=date.today())
    source_url = st.text_input("Kaynak URL")
    ok = st.form_submit_button("Kaydet")

if ok and event_label:
    upsert("actuals", {"event_id": emap[event_label], "actual_value": actual_value, "released_at": str(released_at), "source_url": source_url}, on_conflict="event_id")
    st.success("Gerçekleşme kaydedildi.")

st.dataframe(pd.DataFrame(fetch("actuals")), use_container_width=True)
