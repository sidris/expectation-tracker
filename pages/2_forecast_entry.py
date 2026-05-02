"""Tek Tahmin Girişi.

Anket dışı bağlamlarda (TV programı, köşe yazısı, manuel kurum açıklaması vb.)
tek bir tahmini sisteme girer. Anket içindeki kurum cevapları için
**Anket Yönetimi** sayfasını kullan.
"""
from datetime import date

import streamlit as st

from utils.db import fetch, insert, invalidate_cache
from utils.domain import (
    MONTHS_TR,
    TARGET_TYPES,
    TARGET_TYPE_LABELS,
    ensure_event,
    log_activity,
    target_period_from_year_month,
)
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>✍️ Tek Tahmin Girişi</h1>
      <p>Anket dışı kanallardan (TV, köşe yazısı, sosyal medya, kurum bülteni)
         gelen tek bir tahmini sisteme ekle.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "💡 Reuters/Matriks/Bloomberg HT gibi anketlerin **kurum kırılımını** girmek için "
    "**Anket Yönetimi** sayfasını kullan; oradaki Yeni Anket sekmesi tüm kurumları "
    "tek formda toplar."
)

participants = fetch("participants", order="name")
sources = fetch("sources", order="name")
polls = fetch("v_poll_summaries", order="published_at", desc=True, limit=500)

pmap = {p["name"]: p["id"] for p in participants}
smap = {s["name"]: s["id"] for s in sources}
poll_map = {
    f"{p.get('published_at') or ''} · {p.get('poll_name')} · {p.get('event_label')}": p["id"]
    for p in polls
}

label_to_target_type = {v: k for k, v in TARGET_TYPE_LABELS.items()}
target_type_labels_list = [TARGET_TYPE_LABELS[t] for t in TARGET_TYPES]

with st.form("forecast"):
    c1, c2, c3 = st.columns(3)
    with c1:
        target_year = st.number_input(
            "Hedef yıl", min_value=2000, max_value=2100,
            value=date.today().year, step=1,
        )
    with c2:
        target_month_name = st.selectbox(
            "Hedef ay", list(MONTHS_TR.keys()), index=date.today().month - 1,
        )
    with c3:
        target_type_label = st.selectbox("Tahmin tipi", target_type_labels_list)

    c4, c5 = st.columns(2)
    with c4:
        participant = st.selectbox("Katılımcı", list(pmap.keys()) if pmap else [])
    with c5:
        source = st.selectbox("Kaynak (opsiyonel)", [""] + list(smap.keys()))

    related_poll = st.selectbox(
        "Bağlı anket (opsiyonel — bu tahmin bir Reuters/Matriks anketinin parçasıysa)",
        [""] + list(poll_map.keys()),
    )

    c6, c7 = st.columns(2)
    with c6:
        forecast_value = st.number_input(
            "Tahmin değeri", value=None, step=0.01, format="%.4f",
        )
    with c7:
        forecast_date = st.date_input(
            "Tahminin açıklandığı tarih", value=date.today(),
        )

    source_text = st.text_input(
        "Kaynak açıklaması",
        placeholder="Örn. Bloomberg HT yayını, köşe yazısı, X paylaşımı...",
    )
    source_url = st.text_input("Kaynak URL")
    raw_text = st.text_area("Ham not / alıntı")
    notes = st.text_area("Not")
    submit = st.form_submit_button("Kaydet", type="primary")

if submit:
    if forecast_value is None:
        st.error("Tahmin değeri boş olamaz.")
    elif not participant:
        st.error("Katılımcı seçilmeli.")
    else:
        target_period = target_period_from_year_month(
            int(target_year), MONTHS_TR[target_month_name],
        )
        target_type = label_to_target_type[target_type_label]
        event_id = ensure_event(target_period, target_type)

        result = insert(
            "forecasts",
            {
                "event_id": event_id,
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
        log_activity(
            "forecast_create",
            "Tek tahmin kaydedildi",
            f"{participant} · {target_type_label} · {forecast_value}",
            "forecasts",
            result[0]["id"] if result else None,
        )
        invalidate_cache()
        st.success(
            "Tahmin kaydedildi. Aynı katılımcının aynı hedefe farklı tarihlerde "
            "verdiği tahminler revizyon olarak ayrı saklanır."
        )
