import streamlit as st
from datetime import date
from utils.db import fetch, insert, upsert

st.title("✍️ Tahmin Girişi")

participants = fetch("participants", order="name")
sources = fetch("sources", order="name")
pmap = {p["name"]: p["id"] for p in participants}
smap = {s["name"]: s["id"] for s in sources}

with st.form("forecast"):
    target_period = st.date_input("Hedef dönem", value=date.today().replace(day=1))
    target_type = st.selectbox("Tahmin tipi", ["monthly_cpi","annual_cpi","year_end_cpi","policy_rate","year_end_policy_rate"])
    participant = st.selectbox("Katılımcı", list(pmap.keys()) if pmap else [])
    source = st.selectbox("Kaynak", [""] + list(smap.keys()))
    forecast_value = st.number_input("Tahmin değeri", step=0.01, format="%.4f")
    forecast_date = st.date_input("Tahmin tarihi", value=date.today())
    raw_text = st.text_area("Ham not / alıntı")
    notes = st.text_area("Not")
    submit = st.form_submit_button("Kaydet")

if submit:
    event = upsert("forecast_events", {"target_period": str(target_period), "target_type": target_type}, on_conflict="target_period,target_type")[0]
    insert("forecasts", {
        "event_id": event["id"],
        "participant_id": pmap.get(participant),
        "source_id": smap.get(source) if source else None,
        "forecast_value": forecast_value,
        "forecast_date": str(forecast_date),
        "raw_text": raw_text,
        "notes": notes
    })
    st.success("Tahmin kaydedildi.")
