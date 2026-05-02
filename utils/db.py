"""Supabase erişim katmanı.

Tüm tablolar/view'lar buradaki fonksiyonlarla okunur/yazılır.
Sayfalar doğrudan supabase client kullanmamalıdır.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

import streamlit as st
from supabase import create_client


@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def fetch(
    table: str,
    *,
    order: Optional[str] = None,
    desc: bool = False,
    limit: int = 10000,
    filters: Optional[dict[str, Any]] = None,
    in_filters: Optional[dict[str, Iterable[Any]]] = None,
) -> list[dict]:
    """Tablo/view'dan veri çeker.

    Args:
        table: Tablo veya view adı.
        order: Sıralanacak kolon.
        desc: True ise azalan sırada.
        limit: Maksimum satır sayısı.
        filters: {kolon: değer} eşitlik filtreleri.
        in_filters: {kolon: [değer, ...]} IN filtreleri.

    Filtreler veritabanı tarafında uygulanır; Python'a gelen veri zaten
    filtrelenmiş olur — büyük tablolarda bu önemli.
    """
    q = get_client().table(table).select("*")
    if filters:
        for k, v in filters.items():
            if v is None:
                q = q.is_(k, "null")
            else:
                q = q.eq(k, v)
    if in_filters:
        for k, vs in in_filters.items():
            vs = list(vs)
            if vs:
                q = q.in_(k, vs)
    if order:
        q = q.order(order, desc=desc)
    if limit:
        q = q.limit(limit)
    return q.execute().data


@st.cache_data(ttl=300, show_spinner=False)
def fetch_cached(
    table: str,
    order: Optional[str] = None,
    desc: bool = False,
    limit: int = 10000,
) -> list[dict]:
    """fetch'in 5 dakikalık cache'li versiyonu.

    Sadece okuma-ağırlıklı, değişmeyen sayfalarda kullan.
    Yazma sonrası `st.cache_data.clear()` çağırılmalı.
    """
    return fetch(table, order=order, desc=desc, limit=limit)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def insert(table: str, payload: dict | list[dict]) -> list[dict]:
    return get_client().table(table).insert(payload).execute().data


def upsert(
    table: str,
    payload: dict | list[dict],
    on_conflict: Optional[str] = None,
) -> list[dict]:
    client = get_client()
    q = client.table(table).upsert(payload, on_conflict=on_conflict) if on_conflict \
        else client.table(table).upsert(payload)
    return q.execute().data


def update(table: str, payload: dict, *, eq: dict[str, Any]) -> list[dict]:
    """payload'ı eq filtresine uyan satırlara uygular."""
    q = get_client().table(table).update(payload)
    for k, v in eq.items():
        q = q.eq(k, v)
    return q.execute().data


def delete(table: str, *, eq: dict[str, Any]) -> None:
    """eq filtresine uyan satırları siler."""
    q = get_client().table(table).delete()
    for k, v in eq.items():
        q = q.eq(k, v)
    q.execute()


def invalidate_cache() -> None:
    """Yazma işleminden sonra cache'i temizle."""
    st.cache_data.clear()
