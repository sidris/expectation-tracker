"""Streamlit tarafı EVDS/BIS sync — Streamlit secrets, cache, log entegrasyonu.

Asıl veri çekme mantığı utils/evds_core.py'da.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from utils.db import upsert
from utils.domain import ensure_event, log_activity
from utils.evds_core import (
    build_actuals_payloads,
    fetch_inflation,
    fetch_policy_rate,
    merge_market_data,
)


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


EVDS_API_KEY = _secret("EVDS_API_KEY", "")
EVDS_TUFE_OLD = _secret("EVDS_TUFE_OLD", "TP.FE.OKTG01")
EVDS_TUFE_NEW = _secret("EVDS_TUFE_NEW", EVDS_TUFE_OLD)


@st.cache_data(ttl=3600)
def fetch_market_data_adapter(
    start_date: date | str, end_date: date | str
) -> tuple[pd.DataFrame, Optional[str]]:
    """TÜFE'yi EVDS'ten, politika faizini BIS'ten çekerek aylık gerçekleşme datası döner."""
    empty_df = pd.DataFrame(columns=["Donem", "Aylık TÜFE", "Yıllık TÜFE", "PPK Faizi", "SortDate"])

    if not EVDS_API_KEY:
        return empty_df, "EVDS_API_KEY yok. Streamlit Secrets içine EVDS_API_KEY ekleyin."

    df_inf = pd.DataFrame()
    try:
        from evds import evdsAPI

        evds_client = evdsAPI(EVDS_API_KEY)
        df_inf = fetch_inflation(
            evds_client, start_date, end_date,
            series_old=EVDS_TUFE_OLD, series_new=EVDS_TUFE_NEW,
        )
    except Exception as exc:
        st.warning(f"EVDS bağlantısı kurulamadı: {exc}")

    df_pol = pd.DataFrame()
    try:
        df_pol = fetch_policy_rate(start_date, end_date)
    except Exception as exc:
        st.warning(f"BIS politika faizi verisi okunamadı: {exc}")

    out = merge_market_data(df_inf, df_pol)
    if out.empty:
        return empty_df, "Veri bulunamadı."
    return out, None


def sync_actuals_from_market_data(df: pd.DataFrame) -> int:
    """Market datasını actuals tablosuna upsert eder."""
    count = 0
    for target_period, target_type, payload in build_actuals_payloads(
        df, evds_series_code=(EVDS_TUFE_NEW or EVDS_TUFE_OLD),
    ):
        event_id = ensure_event(target_period, target_type)
        payload["event_id"] = event_id
        upsert("actuals", payload, on_conflict="event_id")
        count += 1
    if count:
        log_activity("actuals_sync", "Gerçekleşmeler otomatik güncellendi",
                     f"{count} kayıt yazıldı/güncellendi.")
    return count


@st.cache_data(ttl=86400, show_spinner=False)
def auto_sync_actuals_once_per_day(
    start_date: date | str, end_date: date | str
) -> tuple[int, str | None]:
    """Sayfa açılışında günde en fazla bir kez otomatik sync."""
    df, err = fetch_market_data_adapter(start_date, end_date)
    if err:
        return 0, err
    if df.empty:
        return 0, "Veri bulunamadı."
    return sync_actuals_from_market_data(df), None
