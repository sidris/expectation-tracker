from datetime import date

import pandas as pd
import streamlit as st

from utils.db import fetch, insert, upsert
from utils.domain import MONTHS_TR, TARGET_TYPES, TARGET_TYPE_LABELS, ensure_event, log_activity, target_period_from_year_month
from utils.ui import inject_theme

inject_theme()
st.title("📊 Anket + Kurum Toplu Girişi")
st.caption("Reuters/Matriks gibi anketlerde hem özet değerleri hem de tek tek cevap veren kurum tahminlerini aynı ekrandan gir.")

participants = fetch("participants", order="name")
sources = fetch("sources", order="name")
insts = [p for p in participants if p.get("type") == "institution"]
smap = {s["name"]: s["id"] for s in sources}

if not insts:
    st.warning("Önce Katılımcılar sayfasından kurumları ekle: Albaraka, QNB, Deutsche Bank vb.")
if not sources:
    st.warning("Önce Kaynaklar sayfasından Reuters, Bloomberg HT, Matriks gibi kaynakları ekle.")

with st.form("bulk_poll_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        source = st.selectbox("Anketi yayımlayan kaynak", list(smap.keys()) if smap else [])
        poll_name = st.text_input("Anket adı", value="Reuters beklenti anketi")
    with c2:
        target_year = st.number_input("Hedef yıl", min_value=2000, max_value=2100, value=date.today().year, step=1)
        target_month_name = st.selectbox("Hedef ay", list(MONTHS_TR.keys()), index=date.today().month - 1)
    with c3:
        target_type_label = st.selectbox("Gösterge", [TARGET_TYPE_LABELS[t] for t in TARGET_TYPES])
        published_at = st.date_input("Yayın tarihi", value=date.today())

    target_type = {v: k for k, v in TARGET_TYPE_LABELS.items()}[target_type_label]

    st.markdown("### Anket özeti")
    c4, c5, c6, c7 = st.columns(4)
    min_value = c4.number_input("Min", step=0.01, format="%.4f")
    max_value = c5.number_input("Max", step=0.01, format="%.4f")
    median_value = c6.number_input("Medyan", step=0.01, format="%.4f")
    mean_value = c7.number_input("Ortalama", step=0.01, format="%.4f")
    notes = st.text_area("Anket notu / haber metni")

    st.markdown("### Kurum cevapları")
    st.caption("Boş bıraktığın kurumlar kaydedilmez. Aynı kurum aynı dönem için sonra yeni değer verirse revizyon olarak ayrıca tutulur.")
    institution_values = {}
    cols = st.columns(3)
    for i, p in enumerate(insts):
        with cols[i % 3]:
            val = st.number_input(p["name"], value=None, step=0.01, format="%.4f", key=f"bulk_{p['id']}")
            if val is not None:
                institution_values[p["id"]] = val

    save = st.form_submit_button("Anketi ve kurum tahminlerini kaydet")

if save:
    target_period = target_period_from_year_month(int(target_year), MONTHS_TR[target_month_name])
    event_id = ensure_event(target_period, target_type)
    participant_count = len(institution_values)

    poll = insert(
        "poll_summaries",
        {
            "event_id": event_id,
            "source_id": smap.get(source),
            "poll_name": poll_name,
            "participant_count": participant_count,
            "min_value": min_value,
            "max_value": max_value,
            "median_value": median_value,
            "mean_value": mean_value,
            "published_at": str(published_at),
            "notes": notes,
            "raw_payload": {"institution_count_entered": participant_count},
        },
    )[0]

    rows = []
    for participant_id, value in institution_values.items():
        rows.append(
            {
                "event_id": event_id,
                "participant_id": participant_id,
                "source_id": smap.get(source),
                "poll_id": poll["id"],
                "forecast_value": value,
                "forecast_date": str(published_at),
                "source_text": poll_name,
                "notes": "Anket kurum kırılımı",
            }
        )
    if rows:
        insert("forecasts", rows)
    log_activity("poll_bulk_entry", "Anket ve kurum cevapları kaydedildi", f"{poll_name}: {participant_count} kurum", "poll_summaries", poll["id"])
    st.success(f"Anket özeti ve {participant_count} kurum tahmini kaydedildi.")

st.subheader("Son anketler")
st.dataframe(pd.DataFrame(fetch("v_poll_summaries", order="published_at", limit=200)), use_container_width=True, hide_index=True)
