import streamlit as st
import pandas as pd
from datetime import date
from utils.db import fetch, upsert
from utils.evds_sync import fetch_market_data_adapter, sync_actuals_from_market_data, auto_sync_actuals_once_per_day
from utils.ui import inject_theme

inject_theme()
st.title("✅ Gerçekleşmeler")
st.caption("Bu sayfa açıldığında EVDS/BIS gerçekleşmeleri günde en fazla bir kez otomatik senkronize edilir. Manuel buton sadece kontrol/önizleme için duruyor.")

# Geçmiş + içinde bulunduğumuz ay: gelecekte veri gelmez, ama sorgu aralığı geniş tutulabilir.
auto_start = date(2024, 1, 1)
auto_end = date.today()
with st.spinner("EVDS/BIS gerçekleşmeleri kontrol ediliyor..."):
    synced_count, auto_err = auto_sync_actuals_once_per_day(auto_start, auto_end)
if auto_err:
    st.warning(auto_err)
else:
    st.success(f"Otomatik kontrol tamamlandı. {synced_count} kayıt yazıldı/güncellendi.")

st.info("Gelecek aylar için gerçekleşme görünmemesi normaldir. 2026 tahminleri girilebilir; gerçekleşme sadece veri açıklandıktan sonra oluşur.")

tab_manual, tab_auto = st.tabs(["Manuel kayıt", "EVDS/BIS kontrol ve yeniden sync"])

with tab_manual:
    events = fetch("forecast_events", order="target_period")
    emap = {f"{e['target_period']} / {e['target_type']}": e["id"] for e in events}

    with st.form("actual"):
        event_label = st.selectbox("Dönem / gösterge", list(emap.keys()) if emap else [])
        actual_value = st.number_input("Gerçekleşme", step=0.01, format="%.4f")
        released_at = st.date_input("Açıklanma tarihi", value=date.today())
        source_url = st.text_input("Kaynak URL")
        ok = st.form_submit_button("Kaydet")

    if ok and event_label:
        upsert(
            "actuals",
            {
                "event_id": emap[event_label],
                "actual_value": actual_value,
                "released_at": str(released_at),
                "source_url": source_url,
                "provider": "manual",
            },
            on_conflict="event_id",
        )
        st.success("Gerçekleşme kaydedildi.")

with tab_auto:
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("Başlangıç", value=date(2024, 1, 1), key="evds_start")
    with c2:
        end_date = st.date_input("Bitiş", value=date.today(), key="evds_end")

    df, err = fetch_market_data_adapter(start_date, end_date)
    if err:
        st.warning(err)
    elif not df.empty:
        st.dataframe(df, use_container_width=True)
        if st.button("Bu aralığı yeniden Supabase actuals tablosuna yaz"):
            count = sync_actuals_from_market_data(df)
            st.success(f"{count} gerçekleşme kaydı Supabase'e yazıldı/güncellendi.")

st.subheader("Kayıtlı gerçekleşmeler")
st.dataframe(pd.DataFrame(fetch("actuals")), use_container_width=True)
