import streamlit as st
import pandas as pd
from datetime import date
from utils.db import fetch, insert, upsert

st.title("🧾 Anket Özetleri")

st.caption("Reuters, Bloomberg HT, AA Finans, Matriks gibi kurumların açıkladığı min / max / medyan / katılımcı sayısı özetleri burada tutulur. Anketin tek tek kurum cevaplarını ise Tahmin Girişi sayfasından bu ankete bağlayarak gir.")

sources = fetch("sources", order="name")
smap = {s["name"]: s["id"] for s in sources}
months = {
    "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6,
    "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12,
}

with st.form("poll"):
    c1, c2 = st.columns(2)
    with c1:
        target_year = st.number_input("Hedef yıl", min_value=2000, max_value=2100, value=date.today().year, step=1)
    with c2:
        target_month_name = st.selectbox("Hedef ay", list(months.keys()), index=date.today().month - 1)

    target_type = st.selectbox("Gösterge", ["monthly_cpi", "annual_cpi", "year_end_cpi", "policy_rate", "year_end_policy_rate"])
    source = st.selectbox("Anketi yayımlayan kaynak", list(smap.keys()) if smap else [])
    poll_name = st.text_input("Anket adı", value="Beklenti anketi")
    published_at = st.date_input("Yayın tarihi", value=date.today())
    participant_count = st.number_input("Katılımcı sayısı", min_value=0, step=1)
    min_value = st.number_input("Min", step=0.01)
    max_value = st.number_input("Max", step=0.01)
    median_value = st.number_input("Medyan", step=0.01)
    mean_value = st.number_input("Ortalama", step=0.01)
    notes = st.text_area("Not")
    ok = st.form_submit_button("Kaydet")

if ok:
    target_period = date(int(target_year), months[target_month_name], 1)
    event = upsert(
        "forecast_events",
        {"target_period": str(target_period), "target_type": target_type},
        on_conflict="target_period,target_type",
    )[0]
    insert(
        "poll_summaries",
        {
            "event_id": event["id"],
            "source_id": smap.get(source),
            "poll_name": poll_name,
            "participant_count": int(participant_count),
            "min_value": min_value,
            "max_value": max_value,
            "median_value": median_value,
            "mean_value": mean_value,
            "published_at": str(published_at),
            "notes": notes,
        },
    )
    st.success("Anket özeti kaydedildi. Tekil kurum cevaplarını Tahmin Girişi sayfasında bu ankete bağlayabilirsin.")

st.dataframe(pd.DataFrame(fetch("v_poll_summaries")), use_container_width=True)
