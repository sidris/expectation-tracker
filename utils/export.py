"""Excel export ve ortak filtre bileşenleri."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

# Sözlükler tek kaynaktan import edilir.
from utils.domain import TARGET_TYPE_LABELS, PARTICIPANT_TYPE_LABELS


def add_display_labels(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    if "target_type" in out.columns:
        out["target_type_label"] = out["target_type"].map(TARGET_TYPE_LABELS).fillna(out["target_type"])
    if "participant_type" in out.columns:
        out["participant_type_label"] = out["participant_type"].map(PARTICIPANT_TYPE_LABELS).fillna(out["participant_type"])
    if "target_period" in out.columns:
        out["target_period"] = pd.to_datetime(out["target_period"], errors="coerce")
        out["target_year"] = out["target_period"].dt.year
    if "forecast_date" in out.columns:
        out["forecast_date"] = pd.to_datetime(out["forecast_date"], errors="coerce")
        out["forecast_year"] = out["forecast_date"].dt.year
    return out


def excel_download_button(df: pd.DataFrame, file_name: str, label: str = "Excel indir"):
    if df is None or df.empty:
        st.caption("İndirilecek veri yok.")
        return
    output = BytesIO()
    export_df = df.copy()
    for col in export_df.select_dtypes(include=["datetimetz"]).columns:
        export_df[col] = export_df[col].astype(str)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="veri")
    st.download_button(
        label=f"📥 {label}",
        data=output.getvalue(),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _date_range_filter(dff: pd.DataFrame, col: str, label: str, widget_col, key: str) -> pd.DataFrame:
    if col not in dff.columns:
        return dff
    dff[col] = pd.to_datetime(dff[col], errors="coerce")
    min_d, max_d = dff[col].min(), dff[col].max()
    if pd.isna(min_d) or pd.isna(max_d):
        return dff
    selected = widget_col.date_input(label, value=(min_d.date(), max_d.date()), key=key)
    if isinstance(selected, tuple) and len(selected) == 2:
        start, end = pd.to_datetime(selected[0]), pd.to_datetime(selected[1])
        dff = dff[(dff[col] >= start) & (dff[col] <= end)]
    return dff


def apply_common_filters(df: pd.DataFrame, key_prefix: str = "") -> pd.DataFrame:
    if df.empty:
        return df
    dff = add_display_labels(df)
    with st.expander("🔎 Filtreler", expanded=True):
        c1, c2, c3 = st.columns(3)
        if "target_type" in dff.columns:
            label_to_value = {TARGET_TYPE_LABELS.get(v, v): v for v in sorted([v for v in dff["target_type"].dropna().unique()])}
            selected_labels = c1.multiselect("Gösterge", list(label_to_value.keys()), default=list(label_to_value.keys()), key=f"{key_prefix}_target_type")
            selected = [label_to_value[x] for x in selected_labels]
            if selected:
                dff = dff[dff["target_type"].isin(selected)]
        if "participant_type" in dff.columns:
            label_to_value = {PARTICIPANT_TYPE_LABELS.get(v, v): v for v in sorted([v for v in dff["participant_type"].dropna().unique()])}
            selected_labels = c2.multiselect("Katılımcı tipi", list(label_to_value.keys()), default=list(label_to_value.keys()), key=f"{key_prefix}_participant_type")
            selected = [label_to_value[x] for x in selected_labels]
            if selected:
                dff = dff[dff["participant_type"].isin(selected)]
        if "participant_name" in dff.columns:
            vals = sorted([v for v in dff["participant_name"].dropna().unique()])
            selected = c3.multiselect("Katılımcı", vals, default=[], key=f"{key_prefix}_participant")
            if selected:
                dff = dff[dff["participant_name"].isin(selected)]

        c4, c5, c6 = st.columns(3)
        if "source_name" in dff.columns:
            vals = sorted([v for v in dff["source_name"].dropna().unique()])
            selected = c4.multiselect("Kaynak", vals, default=[], key=f"{key_prefix}_source")
            if selected:
                dff = dff[dff["source_name"].isin(selected)]
        if "target_year" in dff.columns and dff["target_year"].notna().any():
            years = sorted([int(y) for y in dff["target_year"].dropna().unique()])
            selected_years = c5.multiselect("Hedef yıl", years, default=years, key=f"{key_prefix}_target_year")
            if selected_years:
                dff = dff[dff["target_year"].isin(selected_years)]
        if "forecast_date" in dff.columns:
            only_latest = c6.checkbox("Sadece son tahminler", value=True, key=f"{key_prefix}_latest")
            if only_latest and {"participant_name", "target_period", "target_type"}.issubset(dff.columns):
                sort_cols = [c for c in ["participant_name", "target_period", "target_type", "forecast_date", "created_at"] if c in dff.columns]
                dff = dff.sort_values(sort_cols).drop_duplicates(["participant_name", "target_period", "target_type"], keep="last")

        c7, c8 = st.columns(2)
        dff = _date_range_filter(dff, "target_period", "Hedef dönem aralığı", c7, f"{key_prefix}_period_range")
        dff = _date_range_filter(dff, "forecast_date", "Tahminin açıklandığı tarih aralığı", c8, f"{key_prefix}_forecast_date_range")

        q = st.text_input("Serbest arama", placeholder="Katılımcı, kaynak, not, ham metin...", key=f"{key_prefix}_q")
        if q:
            text_cols = [c for c in dff.columns if dff[c].dtype == "object"]
            if text_cols:
                mask = dff[text_cols].astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)
                dff = dff[mask]
    return dff
