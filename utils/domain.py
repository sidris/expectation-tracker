"""Domain sabitleri ve yardımcı fonksiyonlar.

Bu dosya proje genelinde tek kaynaktır (single source of truth).
TARGET_TYPE_LABELS, MONTHS_TR gibi sözlükler başka yerde tekrar TANIMLANMAMALI;
gerekiyorsa buradan import edilmeli.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from utils.db import get_client, insert, upsert

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

MONTHS_TR = {
    "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6,
    "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12,
}

TARGET_TYPES = [
    "monthly_cpi",
    "annual_cpi",
    "year_end_cpi",
    "policy_rate",
    "year_end_policy_rate",
]

TARGET_TYPE_LABELS = {
    "monthly_cpi": "Aylık TÜFE",
    "annual_cpi": "Yıllık TÜFE",
    "year_end_cpi": "Sene sonu enflasyon/TÜFE",
    "policy_rate": "PPK politika faizi",
    "year_end_policy_rate": "Sene sonu PPK/politika faizi",
}

# Her gösterge tipinin doğal birim adımı.
# UI'da number_input step'i için; karşılaştırılabilir analizde scale farkı için.
TARGET_TYPE_STEP = {
    "monthly_cpi": 0.1,
    "annual_cpi": 0.1,
    "year_end_cpi": 0.1,
    "policy_rate": 0.25,
    "year_end_policy_rate": 0.25,
}

# Anket/poll özetlerine göre giriş yapılan ölçeği gruplar
# (boxplot, comparison gibi yerlerde "elma elma" karşılaştırması için).
TARGET_TYPE_GROUP = {
    "monthly_cpi": "cpi_pct",
    "annual_cpi": "cpi_pct",
    "year_end_cpi": "cpi_pct",
    "policy_rate": "rate_pct",
    "year_end_policy_rate": "rate_pct",
}

PARTICIPANT_TYPES = ["person", "institution"]

PARTICIPANT_TYPE_LABELS = {
    "person": "Kişi",
    "institution": "Kurum",
    # Geriye dönük uyumluluk için tutuluyor; yeni veride kullanılmamalı.
    "media_poll": "Medya / anket kaynağı (eski)",
}


# ---------------------------------------------------------------------------
# Tarih yardımcıları
# ---------------------------------------------------------------------------

def target_period_from_year_month(year: int, month: int) -> str:
    return str(date(int(year), int(month), 1))


def month_index(month_name: str) -> int:
    return MONTHS_TR[month_name]


# ---------------------------------------------------------------------------
# DB yardımcıları
# ---------------------------------------------------------------------------

def ensure_event(target_period: str, target_type: str) -> str:
    """forecast_events tablosunda satır varsa id'yi döner, yoksa upsert ile oluşturur."""
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
    return upsert(
        "forecast_events",
        {"target_period": target_period, "target_type": target_type},
        on_conflict="target_period,target_type",
    )[0]["id"]


def log_activity(
    activity_type: str,
    title: str,
    details: str = "",
    entity_table: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> None:
    """Aktivite logu yazar. Hata olursa ana akışı bozmaz."""
    try:
        insert(
            "activity_log",
            {
                "activity_type": activity_type,
                "title": title,
                "details": details,
                "entity_table": entity_table,
                "entity_id": entity_id,
            },
        )
    except Exception:
        pass
