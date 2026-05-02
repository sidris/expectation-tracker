"""Daily EVDS/BIS actuals sync for GitHub Actions.

Required repository secrets:
- SUPABASE_URL
- SUPABASE_KEY
- EVDS_API_KEY
Optional:
- EVDS_TUFE_OLD
- EVDS_TUFE_NEW
"""
from __future__ import annotations

import io
import os
from datetime import date

import pandas as pd
import requests
from evds import evdsAPI
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
EVDS_API_KEY = os.environ["EVDS_API_KEY"]
EVDS_TUFE_OLD = os.environ.get("EVDS_TUFE_OLD", "TP.FE.OKTG01")
EVDS_TUFE_NEW = os.environ.get("EVDS_TUFE_NEW", EVDS_TUFE_OLD)
client = create_client(SUPABASE_URL, SUPABASE_KEY)


def evds_to_pct(evds_client, series_code: str, fetch_start: str, fetch_end: str) -> pd.DataFrame:
    raw = evds_client.get_data([series_code], startdate=fetch_start, enddate=fetch_end, frequency=5)
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


def fetch_market_data(start_date: str, end_date: str) -> pd.DataFrame:
    evds_client = evdsAPI(EVDS_API_KEY)
    ts_start = pd.Timestamp(start_date)
    ts_end = pd.Timestamp(end_date)

    fetch_start_old = (ts_start - pd.DateOffset(months=13)).replace(day=1).strftime("%d-%m-%Y")
    df_old = evds_to_pct(evds_client, EVDS_TUFE_OLD, fetch_start_old, "01-12-2025")

    fetch_end_new = ts_end.replace(day=1).strftime("%d-%m-%Y")
    df_new = evds_to_pct(evds_client, EVDS_TUFE_NEW, "01-01-2025", fetch_end_new)
    if not df_new.empty:
        df_new = df_new[df_new["Donem"] >= "2026-01"].copy()

    df_inf = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=["Donem"], keep="last")
    df_inf = df_inf.sort_values("Donem").reset_index(drop=True)
    df_inf = df_inf[(df_inf["Donem"] >= ts_start.strftime("%Y-%m")) & (df_inf["Donem"] <= ts_end.strftime("%Y-%m"))].copy()
    for c in ["Aylık TÜFE", "Yıllık TÜFE"]:
        df_inf[c] = pd.to_numeric(df_inf[c], errors="coerce").round(2)

    s_bis = ts_start.strftime("%Y-%m-%d")
    e_bis = ts_end.strftime("%Y-%m-%d")
    url_bis = f"https://stats.bis.org/api/v1/data/WS_CBPOL/D.TR?format=csv&startPeriod={s_bis}&endPeriod={e_bis}"
    r_bis = requests.get(url_bis, timeout=20)
    df_pol = pd.DataFrame()
    if r_bis.status_code == 200:
        temp = pd.read_csv(io.StringIO(r_bis.content.decode("utf-8")), usecols=["TIME_PERIOD", "OBS_VALUE"])
        temp["dt"] = pd.to_datetime(temp["TIME_PERIOD"])
        temp["Donem"] = temp["dt"].dt.strftime("%Y-%m")
        temp["PPK Faizi"] = pd.to_numeric(temp["OBS_VALUE"], errors="coerce")
        df_pol = temp.sort_values("dt").groupby("Donem").last().reset_index()[["Donem", "PPK Faizi"]]

    if not df_inf.empty and not df_pol.empty:
        out = pd.merge(df_inf, df_pol, on="Donem", how="left")
        out["PPK Faizi"] = out["PPK Faizi"].ffill()
        return out
    if not df_inf.empty:
        return df_inf
    return df_pol


def ensure_event(target_period: str, target_type: str) -> str:
    res = client.table("forecast_events").select("id").eq("target_period", target_period).eq("target_type", target_type).limit(1).execute().data
    if res:
        return res[0]["id"]
    return client.table("forecast_events").upsert({"target_period": target_period, "target_type": target_type}, on_conflict="target_period,target_type").execute().data[0]["id"]


def sync(df: pd.DataFrame) -> int:
    mapping = {
        "Aylık TÜFE": ("monthly_cpi", "EVDS", EVDS_TUFE_NEW or EVDS_TUFE_OLD),
        "Yıllık TÜFE": ("annual_cpi", "EVDS", EVDS_TUFE_NEW or EVDS_TUFE_OLD),
        "PPK Faizi": ("policy_rate", "BIS", "WS_CBPOL/D.TR"),
    }
    count = 0
    for _, row in df.iterrows():
        target_period = f"{row['Donem']}-01"
        for col, (target_type, provider, series_code) in mapping.items():
            val = row.get(col)
            if pd.isna(val):
                continue
            event_id = ensure_event(target_period, target_type)
            client.table("actuals").upsert(
                {
                    "event_id": event_id,
                    "actual_value": float(val),
                    "released_at": target_period,
                    "provider": provider,
                    "external_series_code": series_code,
                    "notes": "GitHub Actions otomatik veri senkronizasyonu",
                },
                on_conflict="event_id",
            ).execute()
            count += 1
    return count


if __name__ == "__main__":
    start = os.environ.get("SYNC_START", "2024-01-01")
    end = os.environ.get("SYNC_END", str(date.today()))
    df = fetch_market_data(start, end)
    print(f"Fetched rows: {len(df)}")
    print(f"Synced actual rows: {sync(df)}")
