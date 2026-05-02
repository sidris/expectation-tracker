from __future__ import annotations

from typing import Any, Optional

from utils.db import get_client


def to_float_or_none(value: Any) -> Optional[float]:
    """Formdan gelen boş/metinsel değeri numeric ya da None'a çevirir."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        raise ValueError(f"Sayısal değer bekleniyor: {value}")


def update_poll_summary(poll_id: str, payload: dict) -> list[dict]:
    return get_client().table("poll_summaries").update(payload).eq("id", poll_id).execute().data


def get_poll_forecasts(poll_id: str) -> list[dict]:
    return (
        get_client()
        .table("forecasts")
        .select("id, participant_id, forecast_value, forecast_date, notes, source_text")
        .eq("poll_id", poll_id)
        .execute()
        .data
    )


def upsert_poll_forecast(
    *,
    poll_id: str,
    event_id: str,
    participant_id: str,
    source_id: str | None,
    forecast_value: float,
    forecast_date: str,
    source_text: str | None = None,
    notes: str | None = None,
) -> str:
    """Poll içindeki kurum tahminini günceller; yoksa oluşturur.

    Unique constraint'e ihtiyaç duymaz. Böylece eski verileri bozmaz.
    Eğer aynı poll+participant için geçmişte duplicate oluşmuşsa en yeni kaydı günceller,
    diğerlerini elle silmek için ekrandaki silme kutuları kullanılabilir.
    """
    client = get_client()
    existing = (
        client.table("forecasts")
        .select("id, created_at")
        .eq("poll_id", poll_id)
        .eq("participant_id", participant_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    payload = {
        "poll_id": poll_id,
        "event_id": event_id,
        "participant_id": participant_id,
        "source_id": source_id,
        "forecast_value": forecast_value,
        "forecast_date": forecast_date,
        "source_text": source_text,
        "notes": notes,
    }
    if existing:
        forecast_id = existing[0]["id"]
        client.table("forecasts").update(payload).eq("id", forecast_id).execute()
        return forecast_id
    created = client.table("forecasts").insert(payload).execute().data
    return created[0]["id"] if created else ""


def delete_forecast(forecast_id: str) -> None:
    get_client().table("forecasts").delete().eq("id", forecast_id).execute()
