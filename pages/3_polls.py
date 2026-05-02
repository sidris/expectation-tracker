"""Anket Yönetimi.

Reuters/Matriks/Bloomberg HT gibi anketleri yönetir.
Eski 5_poll_summaries, 14_poll_bulk_entry ve 15_poll_edit sayfalarının
birleştirilmiş halidir.

İki sekme:
    - Yeni Anket: özet + kurum kırılımını birlikte gir
    - Mevcut Anketleri Düzenle: önceki anketlere kurum ekle/güncelle/sil
"""
from datetime import date

import pandas as pd
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
from utils.poll_helpers import (
    delete_forecast,
    get_poll_forecasts,
    to_float_or_none,
    update_poll_summary,
    upsert_poll_forecast,
)
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>📊 Anket Yönetimi</h1>
      <p>Reuters, Matriks, Bloomberg HT gibi kaynakların açıkladığı anketleri ve
         tek tek kurum cevaplarını tek yerden yönet.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Ortak veri (hem yeni hem düzenleme için)
# ---------------------------------------------------------------------------

participants = fetch("participants", order="name")
sources = fetch("sources", order="name")
insts = [p for p in participants if p.get("type") == "institution"]
smap = {s["name"]: s["id"] for s in sources}
source_by_id = {s["id"]: s for s in sources}

if not insts:
    st.warning(
        "Önce **Katılımcılar** sayfasından kurumları ekle (Albaraka, QNB, Deutsche Bank vb.)."
    )
if not sources:
    st.warning(
        "Önce **Kaynaklar** sayfasından Reuters, Bloomberg HT, Matriks gibi kaynakları ekle."
    )

label_to_target_type = {v: k for k, v in TARGET_TYPE_LABELS.items()}
target_type_labels_list = [TARGET_TYPE_LABELS[t] for t in TARGET_TYPES]
month_names = list(MONTHS_TR.keys())

tab_new, tab_edit = st.tabs(["➕ Yeni Anket", "✏️ Mevcut Anketleri Düzenle"])

# ---------------------------------------------------------------------------
# Yeni Anket sekmesi
# ---------------------------------------------------------------------------

with tab_new:
    st.caption(
        "Anket özetini (min/max/medyan/ortalama) ve isteğe bağlı olarak "
        "kurum bazında cevapları aynı ekrandan gir. Boş bıraktığın kurumlar kaydedilmez."
    )

    with st.form("new_poll_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_source = st.selectbox("Anketi yayımlayan kaynak", list(smap.keys()) if smap else [])
            new_poll_name = st.text_input("Anket adı", value="Reuters beklenti anketi")
        with c2:
            new_target_year = st.number_input(
                "Hedef yıl", min_value=2000, max_value=2100,
                value=date.today().year, step=1,
            )
            new_target_month_name = st.selectbox(
                "Hedef ay", month_names, index=date.today().month - 1,
            )
        with c3:
            new_target_type_label = st.selectbox("Gösterge", target_type_labels_list)
            new_published_at = st.date_input("Yayın tarihi", value=date.today())

        st.markdown("##### Anket özeti")
        c4, c5, c6, c7 = st.columns(4)
        new_min = c4.number_input("Min", value=None, step=0.01, format="%.4f")
        new_max = c5.number_input("Max", value=None, step=0.01, format="%.4f")
        new_median = c6.number_input("Medyan", value=None, step=0.01, format="%.4f")
        new_mean = c7.number_input("Ortalama", value=None, step=0.01, format="%.4f")
        new_notes = st.text_area("Anket notu / haber metni")

        st.markdown("##### Kurum cevapları (opsiyonel)")
        st.caption(
            "Boş bıraktığın kurumlar kaydedilmez. Aynı kurum aynı dönem için sonra "
            "yeni değer verirse revizyon olarak ayrıca tutulur."
        )
        new_inst_values: dict[str, float] = {}
        cols = st.columns(3)
        for i, p in enumerate(insts):
            with cols[i % 3]:
                v = st.number_input(
                    p["name"], value=None, step=0.01, format="%.4f",
                    key=f"new_poll_{p['id']}",
                )
                if v is not None:
                    new_inst_values[p["id"]] = v

        new_save = st.form_submit_button("Anketi kaydet", type="primary")

    if new_save:
        target_period = target_period_from_year_month(int(new_target_year), MONTHS_TR[new_target_month_name])
        target_type = label_to_target_type[new_target_type_label]
        event_id = ensure_event(target_period, target_type)
        participant_count = len(new_inst_values)

        poll = insert(
            "poll_summaries",
            {
                "event_id": event_id,
                "source_id": smap.get(new_source),
                "poll_name": new_poll_name,
                "participant_count": participant_count,
                "min_value": new_min,
                "max_value": new_max,
                "median_value": new_median,
                "mean_value": new_mean,
                "published_at": str(new_published_at),
                "notes": new_notes,
                "raw_payload": {"institution_count_entered": participant_count},
            },
        )[0]

        if new_inst_values:
            rows = [
                {
                    "event_id": event_id,
                    "participant_id": pid,
                    "source_id": smap.get(new_source),
                    "poll_id": poll["id"],
                    "forecast_value": val,
                    "forecast_date": str(new_published_at),
                    "source_text": new_poll_name,
                    "notes": "Anket kurum kırılımı",
                }
                for pid, val in new_inst_values.items()
            ]
            insert("forecasts", rows)

        log_activity(
            "poll_create",
            "Yeni anket kaydedildi",
            f"{new_poll_name}: {participant_count} kurum",
            "poll_summaries",
            poll["id"],
        )
        invalidate_cache()
        st.success(
            f"Anket kaydedildi. {participant_count} kurum tahmini eklendi."
            if participant_count else "Anket özeti kaydedildi."
        )

# ---------------------------------------------------------------------------
# Düzenleme sekmesi
# ---------------------------------------------------------------------------

with tab_edit:
    st.caption(
        "Önceden girilmiş bir anketi seç; özet değerlerini güncelleyebilir, eksik kurum "
        "ekleyebilir, mevcut kurum tahminlerini değiştirebilir veya silebilirsin."
    )

    polls = fetch("v_poll_summaries", order="published_at", desc=True, limit=1000)

    if not polls:
        st.info("Henüz düzenlenecek anket yok. **Yeni Anket** sekmesinden bir anket ekle.")
    else:
        def poll_label(p: dict) -> str:
            return (
                f"{p.get('published_at') or '-'} · "
                f"{p.get('source_name') or 'Kaynak yok'} · "
                f"{p.get('poll_name') or '-'} · "
                f"{p.get('event_label') or '-'}"
            )

        selected_poll = st.selectbox(
            "Düzenlenecek anket", polls, format_func=poll_label, key="edit_poll_select",
        )

        existing_forecasts = get_poll_forecasts(selected_poll["id"])
        forecast_by_participant: dict[str, dict] = {}
        extra_duplicates = []
        for row in sorted(
            existing_forecasts,
            key=lambda r: str(r.get("forecast_date") or ""),
            reverse=True,
        ):
            pid = row.get("participant_id")
            if pid and pid not in forecast_by_participant:
                forecast_by_participant[pid] = row
            else:
                extra_duplicates.append(row)

        with st.form("edit_poll_form"):
            st.markdown("##### Anket özeti")
            c1, c2, c3 = st.columns(3)
            with c1:
                source_names = list(smap.keys())
                current_source_name = selected_poll.get("source_name") or (
                    source_names[0] if source_names else ""
                )
                source_index = (
                    source_names.index(current_source_name)
                    if current_source_name in source_names
                    else 0
                )
                edit_source = st.selectbox(
                    "Anketi yayımlayan kaynak",
                    source_names,
                    index=source_index if source_names else None,
                )
                edit_poll_name = st.text_input(
                    "Anket adı", value=selected_poll.get("poll_name") or "",
                )
            with c2:
                current_year = int(selected_poll.get("target_year") or date.today().year)
                current_month = int(selected_poll.get("target_month") or date.today().month)
                edit_year = st.number_input(
                    "Hedef yıl", min_value=2000, max_value=2100,
                    value=current_year, step=1,
                )
                edit_month_name = st.selectbox(
                    "Hedef ay", month_names, index=max(0, current_month - 1),
                )
            with c3:
                current_type = selected_poll.get("target_type") or "policy_rate"
                current_label = TARGET_TYPE_LABELS.get(current_type, current_type)
                edit_target_type_label = st.selectbox(
                    "Gösterge",
                    target_type_labels_list,
                    index=(
                        target_type_labels_list.index(current_label)
                        if current_label in target_type_labels_list else 0
                    ),
                )
                edit_published_at = st.date_input(
                    "Yayın tarihi",
                    value=pd.to_datetime(selected_poll.get("published_at") or date.today()).date(),
                )

            c4, c5, c6, c7, c8 = st.columns(5)
            edit_min = c4.text_input(
                "Min",
                value=("" if selected_poll.get("min_value") is None else str(selected_poll.get("min_value"))),
            )
            edit_max = c5.text_input(
                "Max",
                value=("" if selected_poll.get("max_value") is None else str(selected_poll.get("max_value"))),
            )
            edit_median = c6.text_input(
                "Medyan",
                value=("" if selected_poll.get("median_value") is None else str(selected_poll.get("median_value"))),
            )
            edit_mean = c7.text_input(
                "Ortalama",
                value=("" if selected_poll.get("mean_value") is None else str(selected_poll.get("mean_value"))),
            )
            edit_pcount = c8.text_input(
                "Katılımcı sayısı",
                value=("" if selected_poll.get("participant_count") is None else str(selected_poll.get("participant_count"))),
            )
            edit_notes = st.text_area(
                "Anket notu / haber metni", value=selected_poll.get("notes") or "",
            )

            st.markdown("##### Kurum tahminleri")
            st.caption(
                "Boş bırakırsan yeni tahmin eklenmez. Mevcut bir değeri silmek için "
                "sağdaki **Sil** kutusunu işaretle."
            )

            edited_values: dict[str, str] = {}
            delete_ids: list[str] = []
            cols = st.columns(3)
            for i, p in enumerate(insts):
                row = forecast_by_participant.get(p["id"])
                existing_value = (
                    "" if not row else str(row.get("forecast_value") or "")
                )
                with cols[i % 3]:
                    st.markdown(f"**{p['name']}**")
                    value_text = st.text_input(
                        "Tahmin",
                        value=existing_value,
                        key=f"edit_value_{p['id']}",
                        label_visibility="collapsed",
                    )
                    if row:
                        if st.checkbox("Sil", key=f"delete_{row['id']}"):
                            delete_ids.append(row["id"])
                    edited_values[p["id"]] = value_text

            edit_submit = st.form_submit_button("Değişiklikleri kaydet", type="primary")

        if edit_submit:
            try:
                target_type = label_to_target_type[edit_target_type_label]
                target_period = target_period_from_year_month(
                    int(edit_year), MONTHS_TR[edit_month_name],
                )
                event_id = ensure_event(target_period, target_type)
                source_id = smap.get(edit_source)

                for fid in delete_ids:
                    delete_forecast(fid)

                saved_count = 0
                for pid, value_text in edited_values.items():
                    existing = forecast_by_participant.get(pid)
                    if existing and existing["id"] in delete_ids:
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
                        forecast_date=str(edit_published_at),
                        source_text=edit_poll_name,
                        notes="Anket kurum kırılımı / düzenlendi",
                    )
                    saved_count += 1

                participant_count = int(to_float_or_none(edit_pcount) or saved_count)
                update_poll_summary(
                    selected_poll["id"],
                    {
                        "event_id": event_id,
                        "source_id": source_id,
                        "poll_name": edit_poll_name.strip() or "Anket",
                        "participant_count": participant_count,
                        "min_value": to_float_or_none(edit_min),
                        "max_value": to_float_or_none(edit_max),
                        "median_value": to_float_or_none(edit_median),
                        "mean_value": to_float_or_none(edit_mean),
                        "published_at": str(edit_published_at),
                        "notes": edit_notes.strip() if edit_notes else None,
                        "raw_payload": {
                            "edited_from_poll_edit": True,
                            "institution_count_saved": saved_count,
                        },
                    },
                )
                log_activity(
                    "poll_edit",
                    "Anket düzenlendi",
                    f"{edit_poll_name}: {saved_count} kurum kaydedildi, {len(delete_ids)} silindi",
                    "poll_summaries",
                    selected_poll["id"],
                )
                invalidate_cache()
                st.success(
                    f"Anket güncellendi. {saved_count} kurum tahmini kaydedildi, "
                    f"{len(delete_ids)} kayıt silindi."
                )
                st.rerun()
            except Exception as exc:
                st.error("Kayıt sırasında hata oluştu.")
                st.code(str(exc))

        if extra_duplicates:
            st.warning(
                "Bu ankette aynı kurum için birden fazla kayıt var. Ekranda en yeni "
                "kayıt düzenlenir. Eski duplicate kayıtları aşağıda görebilirsin."
            )
            st.dataframe(
                pd.DataFrame(extra_duplicates),
                use_container_width=True,
                hide_index=True,
            )

        if not existing_forecasts:
            st.info("Bu ankete bağlı kurum tahmini henüz yok.")
        else:
            st.markdown("##### Bu ankete bağlı kurum kırılımı")
            current = pd.DataFrame(existing_forecasts)
            name_map = {p["id"]: p["name"] for p in participants}
            current["participant_name"] = current["participant_id"].map(name_map)
            st.dataframe(
                current[["participant_name", "forecast_value", "forecast_date", "notes", "id"]],
                use_container_width=True,
                hide_index=True,
            )

# ---------------------------------------------------------------------------
# Sayfa altında son anketler tablosu
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("Son anketler")
st.dataframe(
    pd.DataFrame(fetch("v_poll_summaries", order="published_at", desc=True, limit=200)),
    use_container_width=True,
    hide_index=True,
)
