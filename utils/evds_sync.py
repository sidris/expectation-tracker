from __future__ import annotations

import io
from datetime import date
from typing import Optional

import pandas as pd
import requests
import streamlit as st

from utils.db import get_client, upsert


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


EVDS_API_KEY = _secret("EVDS_API_KEY", "")
EVDS_TUFE_OLD = _secret("EVDS_TUFE_OLD", "TP.FE.OKTG01")
EVDS_TUFE_NEW = _secret("EVDS_TUFE_NEW", EVDS_TUFE_OLD)


def _evds_to_pct(evds_client, series_code: str, fetch_start: str, fetch_end: str) -> pd.DataFrame:
    """EVDS endeks serisini çeker; aylık/yıllık yüzde değişim ve Donem kolonlu df döner."""
    try:
        raw = evds_client.get_data(
            [series_code],
            startdate=fetch_start,
            enddate=fetch_end,
            frequency=5,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()

        raw["dt"] = pd.to_datetime(raw["Tarih"], format="%Y-%m", errors="coerce")
        raw = raw.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

        val_col = [c for c in raw.columns if c not in ("Tarih", "dt")][0]
        raw[val_col] = pd.to_numeric(raw[val_col], errors="coerce")
        raw = raw.dropna(subset=[val_col])

        raw["Aylık TÜFE"] = raw[val_col].pct_change(1) * 100
        raw["Yıllık TÜFE"] = raw[val_col].pct_change(12) * 100
        raw["Donem"] = raw["dt"].dt.strftime("%Y-%m")
        return raw[["Donem", "Aylık TÜFE", "Yıllık TÜFE"]].copy()
    except Exception as exc:
        st.warning(f"EVDS TÜFE verisi okunamadı: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=600)
def fetch_market_data_adapter(start_date: date | str, end_date: date | str) -> tuple[pd.DataFrame, Optional[str]]:
    """TÜFE'yi EVDS'ten, politika faizini BIS'ten çekerek aylık gerçekleşme datası döndürür."""
    empty_df = pd.DataFrame(columns=["Donem", "Aylık TÜFE", "Yıllık TÜFE", "PPK Faizi", "SortDate"])

    if not EVDS_API_KEY:
        return empty_df, "EVDS_API_KEY yok. Streamlit Secrets içine EVDS_API_KEY ekleyin."

    df_inf = pd.DataFrame()
    try:
        from evds import evdsAPI

        evds_client = evdsAPI(EVDS_API_KEY)
        ts_start = pd.Timestamp(start_date)
        ts_end = pd.Timestamp(end_date)

        fetch_start_old = (ts_start - pd.DateOffset(months=13)).replace(day=1).strftime("%d-%m-%Y")
        fetch_end_old = "01-12-2025"
        df_old = _evds_to_pct(evds_client, EVDS_TUFE_OLD, fetch_start_old, fetch_end_old)

        fetch_end_new = ts_end.replace(day=1).strftime("%d-%m-%Y")
        df_new = _evds_to_pct(evds_client, EVDS_TUFE_NEW, "01-01-2025", fetch_end_new)
        if not df_new.empty:
            df_new = df_new[df_new["Donem"] >= "2026-01"].copy()

        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=["Donem"], keep="last")
        df_combined = df_combined.sort_values("Donem").reset_index(drop=True)

        cutoff = ts_start.strftime("%Y-%m")
        end_cutoff = ts_end.strftime("%Y-%m")
        df_inf = df_combined[(df_combined["Donem"] >= cutoff) & (df_combined["Donem"] <= end_cutoff)].copy()

        df_inf["Aylık TÜFE"] = pd.to_numeric(df_inf["Aylık TÜFE"], errors="coerce").round(2)
        df_inf["Yıllık TÜFE"] = pd.to_numeric(df_inf["Yıllık TÜFE"], errors="coerce").round(2)
        df_inf = df_inf.dropna(subset=["Aylık TÜFE", "Yıllık TÜFE"]).reset_index(drop=True)
    except Exception as exc:
        st.warning(f"EVDS bağlantısı kurulamadı: {exc}")

    df_pol = pd.DataFrame()
    try:
        s_bis = pd.Timestamp(start_date).strftime("%Y-%m-%d")
        e_bis = pd.Timestamp(end_date).strftime("%Y-%m-%d")
        url_bis = f"https://stats.bis.org/api/v1/data/WS_CBPOL/D.TR?format=csv&startPeriod={s_bis}&endPeriod={e_bis}"
        r_bis = requests.get(url_bis, timeout=20)
        if r_bis.status_code == 200:
            temp_bis = pd.read_csv(io.StringIO(r_bis.content.decode("utf-8")), usecols=["TIME_PERIOD", "OBS_VALUE"])
            temp_bis["dt"] = pd.to_datetime(temp_bis["TIME_PERIOD"])
            temp_bis["Donem"] = temp_bis["dt"].dt.strftime("%Y-%m")
            temp_bis["PPK Faizi"] = pd.to_numeric(temp_bis["OBS_VALUE"], errors="coerce")
            df_pol = temp_bis.sort_values("dt").groupby("Donem").last().reset_index()[["Donem", "PPK Faizi"]]
    except Exception as exc:
        st.warning(f"BIS politika faizi verisi okunamadı: {exc}")

    if not df_inf.empty and not df_pol.empty:
        master_df = pd.merge(df_inf, df_pol, on="Donem", how="left")
        master_df["PPK Faizi"] = master_df["PPK Faizi"].ffill()
    elif not df_inf.empty:
        master_df = df_inf
    elif not df_pol.empty:
        master_df = df_pol
    else:
        return empty_df, "Veri bulunamadı."

    for c in ["Aylık TÜFE", "Yıllık TÜFE", "PPK Faizi"]:
        if c not in master_df.columns:
            master_df[c] = None

    master_df["SortDate"] = pd.to_datetime(master_df["Donem"] + "-01")
    return master_df.sort_values("SortDate").reset_index(drop=True), None


def ensure_event(target_period: str, target_type: str) -> str:
    """forecast_events kaydını bulur veya oluşturur; event_id döndürür."""
    client = get_client()
    existing = (
        client.table("forecast_events")
        .select("id")
        .eq("target_period", target_period)
        .eq("target_type", target_type)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]["id"]

    inserted = client.table("forecast_events").insert(
        {"target_period": target_period, "target_type": target_type}
    ).execute().data
    return inserted[0]["id"]


def sync_actuals_from_market_data(df: pd.DataFrame) -> int:
    """Market datasını actuals tablosuna upsert eder. Her dönem için aylık/yıllık TÜFE ve PPK kaydı açar."""
    inserted = 0
    mapping = {
        "Aylık TÜFE": ("monthly_cpi", "EVDS", EVDS_TUFE_NEW or EVDS_TUFE_OLD),
        "Yıllık TÜFE": ("annual_cpi", "EVDS", EVDS_TUFE_NEW or EVDS_TUFE_OLD),
        "PPK Faizi": ("policy_rate", "BIS", "WS_CBPOL/D.TR"),
    }

    for _, row in df.iterrows():
        target_period = f"{row['Donem']}-01"
        for col, (target_type, provider, series_code) in mapping.items():
            val = row.get(col)
            if pd.isna(val):
                continue
            event_id = ensure_event(target_period, target_type)
            payload = {
                "event_id": event_id,
                "actual_value": float(val),
                "released_at": target_period,
                "provider": provider,
                "external_series_code": series_code,
                "notes": "Otomatik veri senkronizasyonu",
            }
            upsert("actuals", payload, on_conflict="event_id")
            inserted += 1
    return inserted
