"""EVDS ve BIS'ten gerçekleşme verisi çekme — ortak çekirdek.

Bu modül hem Streamlit (utils/evds_sync.py) hem GitHub Actions
(scripts/sync_actuals.py) tarafından kullanılır. Saf Python; Streamlit
bağımlılığı yoktur, secrets'a erişmez.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Optional

import pandas as pd
import requests


def evds_to_pct(evds_client, series_code: str, fetch_start: str, fetch_end: str) -> pd.DataFrame:
    """EVDS endeks serisinden aylık/yıllık % değişim üretir."""
    raw = evds_client.get_data(
        [series_code], startdate=fetch_start, enddate=fetch_end, frequency=5,
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


def fetch_inflation(
    evds_client,
    start_date: date | str,
    end_date: date | str,
    *,
    series_old: str,
    series_new: str,
    new_series_cutoff: str = "2026-01",
) -> pd.DataFrame:
    """Eski ve yeni TÜFE serilerini birleştirip aralığa kırpar."""
    ts_start = pd.Timestamp(start_date)
    ts_end = pd.Timestamp(end_date)

    fetch_start_old = (ts_start - pd.DateOffset(months=13)).replace(day=1).strftime("%d-%m-%Y")
    df_old = evds_to_pct(evds_client, series_old, fetch_start_old, "01-12-2025")

    fetch_end_new = ts_end.replace(day=1).strftime("%d-%m-%Y")
    df_new = evds_to_pct(evds_client, series_new, "01-01-2025", fetch_end_new)
    if not df_new.empty:
        df_new = df_new[df_new["Donem"] >= new_series_cutoff].copy()

    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["Donem"], keep="last")
    df = df.sort_values("Donem").reset_index(drop=True)

    cutoff_start = ts_start.strftime("%Y-%m")
    cutoff_end = ts_end.strftime("%Y-%m")
    df = df[(df["Donem"] >= cutoff_start) & (df["Donem"] <= cutoff_end)].copy()

    for c in ["Aylık TÜFE", "Yıllık TÜFE"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").round(2)
    df = df.dropna(subset=["Aylık TÜFE", "Yıllık TÜFE"], how="all").reset_index(drop=True)
    return df


def fetch_policy_rate(start_date: date | str, end_date: date | str) -> pd.DataFrame:
    """BIS WS_CBPOL serisinden TR politika faizi (aylık)."""
    s = pd.Timestamp(start_date).strftime("%Y-%m-%d")
    e = pd.Timestamp(end_date).strftime("%Y-%m-%d")
    url = f"https://stats.bis.org/api/v1/data/WS_CBPOL/D.TR?format=csv&startPeriod={s}&endPeriod={e}"
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        return pd.DataFrame()
    temp = pd.read_csv(io.StringIO(r.content.decode("utf-8")), usecols=["TIME_PERIOD", "OBS_VALUE"])
    temp["dt"] = pd.to_datetime(temp["TIME_PERIOD"])
    temp["Donem"] = temp["dt"].dt.strftime("%Y-%m")
    temp["PPK Faizi"] = pd.to_numeric(temp["OBS_VALUE"], errors="coerce")
    return temp.sort_values("dt").groupby("Donem").last().reset_index()[["Donem", "PPK Faizi"]]


def merge_market_data(df_inf: pd.DataFrame, df_pol: pd.DataFrame) -> pd.DataFrame:
    """Enflasyon ve faiz dataframe'lerini Donem üzerinden birleştirir."""
    if not df_inf.empty and not df_pol.empty:
        out = pd.merge(df_inf, df_pol, on="Donem", how="left")
        out["PPK Faizi"] = out["PPK Faizi"].ffill()
    elif not df_inf.empty:
        out = df_inf.copy()
    elif not df_pol.empty:
        out = df_pol.copy()
    else:
        return pd.DataFrame(columns=["Donem", "Aylık TÜFE", "Yıllık TÜFE", "PPK Faizi", "SortDate"])

    for c in ["Aylık TÜFE", "Yıllık TÜFE", "PPK Faizi"]:
        if c not in out.columns:
            out[c] = None
    out["SortDate"] = pd.to_datetime(out["Donem"] + "-01")
    return out.sort_values("SortDate").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Supabase yazma kısmı (DB-bağımlı; test edilebilir tutmak için ayrı)
# ---------------------------------------------------------------------------

ACTUALS_MAPPING_TEMPLATE = {
    "Aylık TÜFE":  ("monthly_cpi", "EVDS"),
    "Yıllık TÜFE": ("annual_cpi",  "EVDS"),
    "PPK Faizi":   ("policy_rate", "BIS"),
}


def build_actuals_payloads(df: pd.DataFrame, *, evds_series_code: str, bis_series_code: str = "WS_CBPOL/D.TR"):
    """DataFrame'i actuals tablosuna yazılacak (target_period, target_type, payload) listesine çevirir.

    Yield ile döner; çağıran taraf ensure_event çağırıp upsert eder.
    """
    series_lookup = {
        "Aylık TÜFE": evds_series_code,
        "Yıllık TÜFE": evds_series_code,
        "PPK Faizi": bis_series_code,
    }
    for _, row in df.iterrows():
        target_period = f"{row['Donem']}-01"
        for col, (target_type, provider) in ACTUALS_MAPPING_TEMPLATE.items():
            val = row.get(col)
            if pd.isna(val):
                continue
            yield target_period, target_type, {
                "actual_value": float(val),
                "released_at": target_period,
                "provider": provider,
                "external_series_code": series_lookup[col],
                "notes": "Otomatik veri senkronizasyonu",
            }
