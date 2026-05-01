import streamlit as st
import pandas as pd
from datetime import date
from utils.db import fetch, insert, upsert

st.title("🧾 Anket Özetleri")

events = fetch("forecast_events", order="target_period")
sources = fetch("sources", order="name")
emap = {f"{e['target_period']} / {e['target_type']}": e["id"] for e in events}
smap = {s["name"]: s["id"] for s in sources}

with st.form("poll"):
    target_period = st.date_input("Hedef dönem", value=date.today().replace(day=1))
    target_type = st.selectbox("Gösterge", ["monthly_cpi","annual_cpi","year_end_cpi","policy_rate","year_end_policy_rate"])
    source = st.selectbox("Anket kaynağı", list(smap.keys()) if smap else [])
    poll_name = st.text_input("Anket adı", value="Beklenti anketi")
    participant_count = st.number_input("Katılımcı sayısı", min_value=0, step=1)
    min_value = st.number_input("Min", step=0.01)
    max_value = st.number_input("Max", step=0.01)
    median_value = st.number_input("Medyan", step=0.01)
    mean_value = st.number_input("Ortalama", step=0.01)
    notes = st.text_area("Not")
    ok = st.form_submit_button("Kaydet")

if ok:
    event = upsert("forecast_events", {"target_period": str(target_period), "target_type": target_type}, on_conflict="target_period,target_type")[0]
    insert("poll_summaries", {
        "event_id": event["id"],
        "source_id": smap.get(source),
        "poll_name": poll_name,
        "participant_count": int(participant_count),
        "min_value": min_value,
        "max_value": max_value,
        "median_value": median_value,
        "mean_value": mean_value,
        "notes": notes
    })
    st.success("Anket özeti kaydedildi.")

st.dataframe(pd.DataFrame(fetch("poll_summaries")), use_container_width=True)
