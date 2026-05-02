"""GitHub Actions için günlük EVDS/BIS gerçekleşme sync.

Veri çekme ve dönüştürme mantığı utils/evds_core.py'da.
Bu dosya sadece env var okuma + Supabase yazma sorumluluğu taşır.

Required secrets:
    SUPABASE_URL, SUPABASE_KEY, EVDS_API_KEY
Optional:
    EVDS_TUFE_OLD, EVDS_TUFE_NEW, SYNC_START, SYNC_END
"""
from __future__ import annotations

import os
import sys
from datetime import date

# Repo kökünü path'e ekle ki utils import edilebilsin.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evds import evdsAPI
from supabase import create_client

from utils.evds_core import (
    build_actuals_payloads,
    fetch_inflation,
    fetch_policy_rate,
    merge_market_data,
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
EVDS_API_KEY = os.environ["EVDS_API_KEY"]
EVDS_TUFE_OLD = os.environ.get("EVDS_TUFE_OLD", "TP.FE.OKTG01")
EVDS_TUFE_NEW = os.environ.get("EVDS_TUFE_NEW", EVDS_TUFE_OLD)

client = create_client(SUPABASE_URL, SUPABASE_KEY)


def ensure_event(target_period: str, target_type: str) -> str:
    res = (
        client.table("forecast_events")
        .select("id")
        .eq("target_period", target_period)
        .eq("target_type", target_type)
        .limit(1)
        .execute()
        .data
    )
    if res:
        return res[0]["id"]
    return (
        client.table("forecast_events")
        .upsert(
            {"target_period": target_period, "target_type": target_type},
            on_conflict="target_period,target_type",
        )
        .execute()
        .data[0]["id"]
    )


def main():
    start = os.environ.get("SYNC_START", "2024-01-01")
    end = os.environ.get("SYNC_END", str(date.today()))

    evds_client = evdsAPI(EVDS_API_KEY)
    df_inf = fetch_inflation(
        evds_client, start, end,
        series_old=EVDS_TUFE_OLD, series_new=EVDS_TUFE_NEW,
    )
    df_pol = fetch_policy_rate(start, end)
    df = merge_market_data(df_inf, df_pol)
    print(f"Fetched rows: {len(df)}")

    count = 0
    for target_period, target_type, payload in build_actuals_payloads(
        df, evds_series_code=(EVDS_TUFE_NEW or EVDS_TUFE_OLD),
    ):
        event_id = ensure_event(target_period, target_type)
        payload["event_id"] = event_id
        payload["notes"] = "GitHub Actions otomatik veri senkronizasyonu"
        client.table("actuals").upsert(payload, on_conflict="event_id").execute()
        count += 1
    print(f"Synced actual rows: {count}")


if __name__ == "__main__":
    main()
