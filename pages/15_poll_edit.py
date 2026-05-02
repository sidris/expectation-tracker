from datetime import date

import pandas as pd
import streamlit as st

from utils.db import fetch
from utils.domain import MONTHS_TR, TARGET_TYPES, TARGET_TYPE_LABELS, log_activity, target_period_from_year_month, ensure_event
from utils.poll_helpers import delete_forecast, get_poll_forecasts, to_float_or_none, update_poll_summary, upsert_poll_forecast
from utils.ui import inject_theme

inject_theme()
st.title("✏️ Anket Düzenle")
st.caption("Önceden girilmiş Reuters/Matriks/Bloomberg HT anketlerini açıp eksik kurum ekleyebilir, mevcut kurum değerlerini değiştirebilir veya yanlış kurum tahminlerini silebilirsin.")

polls = fetch("v_poll_summaries", order="published_at", limit=1000)
participants = fetch("participants", order="name")
sources = fetch("sources", order="name")

insts = [p for p in participants if p.get("type") == "institution" and p.get("is_active", True) is not False]
source_by_id = {s["id"]: s for s in sources}
source_name_to_id = {s["name"]: s["id"] for s in sources}

if not polls:
    st.info("Henüz düzenlenecek anket yok. Önce 'Anket + Kurum Toplu Girişi' sayfasından bir anket ekle.")
    st.stop()

if not insts:
    st.warning("Kurum listesi boş. Önce Katılımcılar sayfasından Albaraka, QNB, Deutsche Bank gibi kurumları ekle.")

# Daha anlaşılır seçim etiketi
poll_options = sorted(
    polls,
    key=lambda p: (str(p.get("published_at") or ""), str(p.get("source_name") or ""), str(p.get("poll_name") or "")),
    reverse=True,
)

def poll_label(p: dict) -> str:
    return f"{p.get('published_at') or '-'} | {p.get('source_name') or 'Kaynak yok'} | {p.get('poll_name') or '-'} | {p.get('event_label') or '-'}"

selected_poll = st.selectbox("Düzenlenecek anket", poll_options, format_func=poll_label)

existing_forecasts = get_poll_forecasts(selected_poll["id"])
forecast_by_participant = {}
extra_duplicates = []
for row in sorted(existing_forecasts, key=lambda r: str(r.get("forecast_date") or ""), reverse=True):
    pid = row.get("participant_id")
    if pid and pid not in forecast_by_participant:
        forecast_by_participant[pid] = row
    else:
        extra_duplicates.append(row)

st.markdown("### Anket özeti")
with st.form("poll_edit_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        source_names = list(source_name_to_id.keys())
        current_source_name = selected_poll.get("source_name") or (source_names[0] if source_names else "")
        source_index = source_names.index(current_source_name) if current_source_name in source_names else 0
        source_name = st.selectbox("Anketi yayımlayan kaynak", source_names, index=source_index if source_names else None)
        poll_name = st.text_input("Anket adı", value=selected_poll.get("poll_name") or "")
    with c2:
        current_year = int(selected_poll.get("target_year") or date.today().year)
        current_month = int(selected_poll.get("target_month") or date.today().month)
        target_year = st.number_input("Hedef yıl", min_value=2000, max_value=2100, value=current_year, step=1)
        month_names = list(MONTHS_TR.keys())
        target_month_name = st.selectbox("Hedef ay", month_names, index=max(0, current_month - 1))
    with c3:
        current_type = selected_poll.get("target_type") or "policy_rate"
        current_label = TARGET_TYPE_LABELS.get(current_type, current_type)
        labels = [TARGET_TYPE_LABELS[t] for t in TARGET_TYPES]
        target_type_label = st.selectbox("Gösterge", labels, index=labels.index(current_label) if current_label in labels else 0)
        published_at = st.date_input("Yayın tarihi", value=pd.to_datetime(selected_poll.get("published_at") or date.today()).date())

    st.markdown("#### Özet değerler")
    c4, c5, c6, c7, c8 = st.columns(5)
    min_value = c4.text_input("Min", value="" if selected_poll.get("min_value") is None else str(selected_poll.get("min_value")))
    max_value = c5.text_input("Max", value="" if selected_poll.get("max_value") is None else str(selected_poll.get("max_value")))
    median_value = c6.text_input("Medyan", value="" if selected_poll.get("median_value") is None else str(selected_poll.get("median_value")))
    mean_value = c7.text_input("Ortalama", value="" if selected_poll.get("mean_value") is None else str(selected_poll.get("mean_value")))
    participant_count_manual = c8.text_input("Katılımcı sayısı", value="" if selected_poll.get("participant_count") is None else str(selected_poll.get("participant_count")))
    notes = st.text_area("Anket notu / haber metni", value=selected_poll.get("notes") or "")

    st.markdown("### Kurum tahminleri")
    st.caption("Boş bırakırsan yeni tahmin eklenmez. Mevcut bir değeri silmek için sağdaki 'Sil' kutusunu işaretle.")

    edited_values = {}
    delete_ids = []
    cols = st.columns(3)
    for i, p in enumerate(insts):
        row = forecast_by_participant.get(p["id"])
        existing_value = "" if not row else str(row.get("forecast_value") or "")
        with cols[i % 3]:
            st.markdown(f"**{p['name']}**")
            value_text = st.text_input("Tahmin", value=existing_value, key=f"edit_value_{p['id']}", label_visibility="collapsed")
            if row:
                delete_flag = st.checkbox("Sil", key=f"delete_{row['id']}")
                if delete_flag:
                    delete_ids.append(row["id"])
            edited_values[p["id"]] = value_text

    submitted = st.form_submit_button("Değişiklikleri Kaydet")

if submitted:
    try:
        target_type = {v: k for k, v in TARGET_TYPE_LABELS.items()}[target_type_label]
        target_period = target_period_from_year_month(int(target_year), MONTHS_TR[target_month_name])
        event_id = ensure_event(target_period, target_type)
        source_id = source_name_to_id.get(source_name)

        for fid in delete_ids:
            delete_forecast(fid)

        saved_count = 0
        for pid, value_text in edited_values.items():
            if forecast_by_participant.get(pid) and forecast_by_participant[pid]["id"] in delete_ids:
                continue
            value = to_float_or_none(value_text)
            if value is None:
                continue
            upsert_poll_forecast(
                poll_id=selected_poll["id"],
                event_id=event_id,
                participant_id=pid,
                source_id=source_id,
                forecast_value=value,
                forecast_date=str(published_at),
                source_text=poll_name,
                notes="Anket kurum kırılımı / düzenlendi",
            )
            saved_count += 1

        participant_count = int(to_float_or_none(participant_count_manual) or saved_count)
        update_poll_summary(
            selected_poll["id"],
            {
                "event_id": event_id,
                "source_id": source_id,
                "poll_name": poll_name.strip() or "Anket",
                "participant_count": participant_count,
                "min_value": to_float_or_none(min_value),
                "max_value": to_float_or_none(max_value),
                "median_value": to_float_or_none(median_value),
                "mean_value": to_float_or_none(mean_value),
                "published_at": str(published_at),
                "notes": notes.strip() if notes else None,
                "raw_payload": {"edited_from_poll_edit": True, "institution_count_saved": saved_count},
            },
        )
        log_activity("poll_edit", "Anket düzenlendi", f"{poll_name}: {saved_count} kurum tahmini kaydedildi, {len(delete_ids)} silindi", "poll_summaries", selected_poll["id"])
        st.success(f"Anket güncellendi. {saved_count} kurum tahmini kaydedildi, {len(delete_ids)} kayıt silindi.")
        st.rerun()
    except Exception as exc:
        st.error("Kayıt sırasında hata oluştu.")
        st.code(str(exc))

if extra_duplicates:
    st.warning("Bu ankette aynı kurum için birden fazla kayıt var. Ekranda en yeni kayıt düzenlenir. Eski duplicate kayıtları veri havuzundan kontrol edebilirsin.")
    st.dataframe(pd.DataFrame(extra_duplicates), use_container_width=True, hide_index=True)

st.markdown("### Mevcut kurum kırılımı")
current = pd.DataFrame(existing_forecasts)
if current.empty:
    st.info("Bu ankete bağlı kurum tahmini henüz yok.")
else:
    name_map = {p["id"]: p["name"] for p in participants}
    current["participant_name"] = current["participant_id"].map(name_map)
    st.dataframe(current[["participant_name", "forecast_value", "forecast_date", "notes", "id"]], use_container_width=True, hide_index=True)
