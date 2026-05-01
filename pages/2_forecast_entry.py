import streamlit as st
from datetime import date
from utils.db import fetch, insert, upsert

st.title("✍️ Tahmin Girişi")

participants = fetch("participants", order="name")
sources = fetch("sources", order="name")
polls = fetch("v_poll_summaries", order="published_at")

pmap = {p["name"]: p["id"] for p in participants}
smap = {s["name"]: s["id"] for s in sources}
poll_map = {
    f"{p.get('published_at') or ''} | {p.get('poll_name')} | {p.get('event_label')}": p["id"]
    for p in polls
}

months = {
    "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6,
    "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12,
}

with st.form("forecast"):
    c1, c2 = st.columns(2)
    with c1:
        target_year = st.number_input("Hedef yıl", min_value=2000, max_value=2100, value=date.today().year, step=1)
    with c2:
        target_month_name = st.selectbox("Hedef ay", list(months.keys()), index=date.today().month - 1)

    target_type = st.selectbox("Tahmin tipi", ["monthly_cpi", "annual_cpi", "year_end_cpi", "policy_rate", "year_end_policy_rate"])
    participant = st.selectbox("Katılımcı", list(pmap.keys()) if pmap else [])
    source = st.selectbox("Kaynak tablosu kaydı", [""] + list(smap.keys()))
    related_poll = st.selectbox("Bağlı anket özeti (Reuters/Matriks kurum listesi gibi)", [""] + list(poll_map.keys()))

    forecast_value = st.number_input("Tahmin değeri", step=0.01, format="%.4f")
    forecast_date = st.date_input("Tahminin açıklandığı tarih", value=date.today())
    source_text = st.text_input("Kaynak açıklaması", placeholder="Örn. Reuters anketi, Bloomberg HT yayını, köşe yazısı...")
    source_url = st.text_input("Kaynak URL")
    raw_text = st.text_area("Ham not / alıntı")
    notes = st.text_area("Not")
    submit = st.form_submit_button("Kaydet")

if submit:
    target_period = date(int(target_year), months[target_month_name], 1)
    event = upsert(
        "forecast_events",
        {"target_period": str(target_period), "target_type": target_type},
        on_conflict="target_period,target_type",
    )[0]

    insert(
        "forecasts",
        {
            "event_id": event["id"],
            "participant_id": pmap.get(participant),
            "source_id": smap.get(source) if source else None,
            "poll_id": poll_map.get(related_poll) if related_poll else None,
            "forecast_value": forecast_value,
            "forecast_date": str(forecast_date),
            "source_text": source_text,
            "source_url": source_url,
            "raw_text": raw_text,
            "notes": notes,
        },
    )
    st.success("Tahmin kaydedildi. Aynı katılımcının aynı hedefe farklı tarihlerde verdiği tahminler revizyon olarak ayrı ayrı saklanır.")
