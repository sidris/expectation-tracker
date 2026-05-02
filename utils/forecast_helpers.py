"""Forecast (tahmin) kayıtları için düzenleme/silme yardımcıları.

poll_helpers.py'nin paraleli; anket dışı kayıtlar dahil tüm forecasts
için kullanılır.
"""
from __future__ import annotations

from typing import Any

from utils.db import delete as db_delete, update as db_update


# Kullanıcının düzenleyebileceği alanlar.
# Diğerleri (id, event_id, participant_id, created_at vb.) salt-okunur.
EDITABLE_FORECAST_FIELDS = {
    "forecast_value",
    "forecast_date",
    "source_text",
    "source_url",
    "raw_text",
    "notes",
}


def update_forecast(forecast_id: str, payload: dict[str, Any]) -> list[dict]:
    """Tahmin kaydını günceller. Sadece izin verilen alanları kabul eder."""
    safe_payload = {k: v for k, v in payload.items() if k in EDITABLE_FORECAST_FIELDS}
    if not safe_payload:
        return []
    return db_update("forecasts", safe_payload, eq={"id": forecast_id})


def delete_forecast(forecast_id: str) -> None:
    db_delete("forecasts", eq={"id": forecast_id})


def update_participant(participant_id: str, payload: dict[str, Any]) -> list[dict]:
    safe = {
        k: v
        for k, v in payload.items()
        if k in {"name", "type", "institution_name", "title", "expertise", "notes", "is_active"}
    }
    if not safe:
        return []
    return db_update("participants", safe, eq={"id": participant_id})


def delete_participant(participant_id: str) -> None:
    """Katılımcıyı siler. NOT: bağlı tahminler de silinir (FK cascade'e bağlı).

    Güvenli alternatif: deactivate_participant kullan.
    """
    db_delete("participants", eq={"id": participant_id})


def deactivate_participant(participant_id: str) -> list[dict]:
    """Katılımcıyı silmek yerine pasifleştirir. Mevcut tahminler korunur."""
    return db_update("participants", {"is_active": False}, eq={"id": participant_id})


def update_source(source_id: str, payload: dict[str, Any]) -> list[dict]:
    safe = {
        k: v
        for k, v in payload.items()
        if k in {"name", "type", "publisher", "url", "notes", "reliability_score"}
    }
    if not safe:
        return []
    return db_update("sources", safe, eq={"id": source_id})


def delete_source(source_id: str) -> None:
    db_delete("sources", eq={"id": source_id})
