"""Ortak AgGrid bileşeni.

Tüm tablo görünümleri ve düzenleme ekranları bu modülü kullanmalı.
UUID gizleme, Türkçe kolon başlıkları, satır seçimi, inline edit
desteği tek yerden yönetilir.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

try:
    from st_aggrid import AgGrid, ColumnsAutoSizeMode, DataReturnMode, GridOptionsBuilder, GridUpdateMode
    from st_aggrid.shared import JsCode
    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False


# Tablo/view kolonu → Türkçe başlık eşlemesi.
# Buraya yeni kolon eklendikçe genişletilebilir.
COLUMN_LABELS = {
    "id": "ID",
    "created_at": "Oluşturulma",
    "updated_at": "Güncellenme",
    "captured_at": "Yakalanma",

    # Katılımcı
    "name": "Ad",
    "type": "Tip",
    "institution_name": "Bağlı kurum",
    "title": "Unvan",
    "expertise": "Uzmanlık",
    "is_active": "Aktif",
    "notes": "Not",

    # Kaynak
    "publisher": "Yayıncı",
    "url": "URL",
    "reliability_score": "Güven skoru",

    # Forecast
    "forecast_value": "Tahmin",
    "forecast_date": "Tahmin tarihi",
    "target_period": "Hedef dönem",
    "target_year": "Yıl",
    "target_month": "Ay",
    "target_type": "Gösterge",
    "target_type_label": "Gösterge",
    "event_label": "Olay",
    "participant_name": "Katılımcı",
    "participant_type": "Katılımcı tipi",
    "participant_type_label": "Katılımcı tipi",
    "source_name": "Kaynak",
    "source_publisher": "Yayıncı",
    "source_text": "Kaynak açıklaması",
    "source_url": "URL",
    "raw_text": "Ham metin",
    "poll_name": "Anket",
    "actual_value": "Gerçekleşme",
    "abs_error": "Mutlak hata",
    "horizon_days": "Ufuk (gün)",
    "confidence": "Güven",
    "is_latest_for_participant_event": "Son revizyon",

    # Poll
    "min_value": "Min",
    "max_value": "Max",
    "median_value": "Medyan",
    "mean_value": "Ortalama",
    "participant_count": "Katılımcı sayısı",
    "published_at": "Yayın tarihi",
    "raw_payload": "Ham veri",

    # Actuals
    "released_at": "Açıklanma",
    "provider": "Sağlayıcı",
    "external_series_code": "Seri kodu",

    # Activity log
    "activity_type": "Aktivite",
    "details": "Detay",
    "entity_table": "İlgili tablo",
    "entity_id": "İlgili ID",

    # Foreign keys
    "event_id": "Olay ID",
    "participant_id": "Katılımcı ID",
    "source_id": "Kaynak ID",
    "poll_id": "Anket ID",
}

# Default'ta gizlenen kolonlar (developer toggle'ı ile gösterilebilir).
HIDDEN_COLUMNS_DEFAULT = {
    "id",
    "event_id",
    "participant_id",
    "source_id",
    "poll_id",
    "entity_id",
    "raw_payload",
    "created_at",
    "updated_at",
    "captured_at",
}


def _label(col: str) -> str:
    return COLUMN_LABELS.get(col, col.replace("_", " ").title())


def show_grid(
    df: pd.DataFrame,
    *,
    key: str,
    editable_columns: Optional[list[str]] = None,
    selectable: bool = False,
    selection_mode: str = "single",
    hide_columns: Optional[list[str]] = None,
    show_id_toggle: bool = True,
    height: int = 400,
    column_widths: Optional[dict[str, int]] = None,
) -> dict:
    """Türkçe başlıklı, UUID-gizli, opsiyonel düzenlenebilir grid.

    Args:
        df: Gösterilecek DataFrame.
        key: Streamlit widget key (sayfa içinde benzersiz).
        editable_columns: Inline düzenlenebilir kolonların listesi.
        selectable: Satır seçimi açık olsun mu.
        selection_mode: "single" veya "multiple".
        hide_columns: Gizlenecek ekstra kolonlar.
        show_id_toggle: ID kolonlarını gösterme/gizleme switch'i çıkar.
        height: Grid yüksekliği (px).
        column_widths: {kolon: piksel} özel genişlik.

    Returns:
        AgGrid'in dönüş objesi (data, selected_rows, vb.). aggrid yoksa
        st.dataframe ile minimum görüntü gösterir ve {} döner.
    """
    if df is None or df.empty:
        st.info("Görüntülenecek veri yok.")
        return {}

    # ID gösterme toggle
    show_ids = False
    if show_id_toggle:
        show_ids = st.toggle(
            "🔧 ID kolonlarını göster (developer)", value=False, key=f"{key}_show_ids",
        )

    if not AGGRID_AVAILABLE:
        st.warning(
            "streamlit-aggrid kurulu değil. requirements.txt'e ekleyip "
            "`pip install streamlit-aggrid` çalıştır."
        )
        cols_to_show = [c for c in df.columns if show_ids or c not in HIDDEN_COLUMNS_DEFAULT]
        if hide_columns:
            cols_to_show = [c for c in cols_to_show if c not in hide_columns]
        renamed = df[cols_to_show].rename(columns={c: _label(c) for c in cols_to_show})
        st.dataframe(renamed, use_container_width=True, hide_index=True)
        return {"data": df}

    # AgGrid yapılandırması
    gob = GridOptionsBuilder.from_dataframe(df)
    gob.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        editable=False,
    )

    editable_set = set(editable_columns or [])
    hide_set = set(hide_columns or [])

    for col in df.columns:
        is_id_like = col in HIDDEN_COLUMNS_DEFAULT
        hidden = (is_id_like and not show_ids) or col in hide_set

        config: dict[str, Any] = {
            "headerName": _label(col),
            "hide": hidden,
            "editable": col in editable_set,
        }

        if column_widths and col in column_widths:
            config["width"] = column_widths[col]

        # Bool kolonlar için checkbox
        if df[col].dtype == bool:
            config["cellRenderer"] = "agCheckboxCellRenderer"
            if col in editable_set:
                config["cellEditor"] = "agCheckboxCellEditor"

        # Sayı kolonları için sağa yaslı, formatlı
        if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
            config["type"] = ["numericColumn"]

        gob.configure_column(col, **config)

    if selectable:
        gob.configure_selection(
            selection_mode=selection_mode,
            use_checkbox=(selection_mode == "multiple"),
        )

    grid_options = gob.build()

    return AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED if editable_columns else GridUpdateMode.NO_UPDATE,
        data_return_mode=DataReturnMode.AS_INPUT,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        height=height,
        allow_unsafe_jscode=True,
        key=key,
        theme="streamlit",
    )


def diff_rows(original: pd.DataFrame, edited: pd.DataFrame, id_col: str = "id") -> pd.DataFrame:
    """İki DataFrame arasındaki değişen satırları döner (id'lerine göre eşleşen).

    Yalnızca farklı olan satırları içeren DataFrame üretir; toplu update için kullanılır.
    AgGrid edit sonrası kolon sırasını/tiplerini değiştirebilir, bu yüzden:
      - Ortak kolonları al
      - Edited dataframe'i original'ın kolon sırasına göre yeniden indeksle
      - Hücre bazında string-cast karşılaştırma yap (NaN ve tip farklarını önler)
    """
    if id_col not in original.columns or id_col not in edited.columns:
        return pd.DataFrame()

    # Edit edilemeyen kolonları (datetime, dict gibi) güvenli karşılaştırmak için
    # her iki tarafı da string'e çeviriyoruz. Bu sadece diff tespiti için;
    # gerçek update payload'ı edited'tan alınıyor.
    common_cols = [c for c in original.columns if c in edited.columns and c != id_col]
    if not common_cols:
        return pd.DataFrame()

    orig = original[[id_col] + common_cols].copy()
    edit = edited[[id_col] + common_cols].copy()

    # ID kolonu null olan satırları çıkar (yeni eklenmiş, henüz kaydedilmemiş)
    orig = orig.dropna(subset=[id_col])
    edit = edit.dropna(subset=[id_col])

    if orig.empty or edit.empty:
        return pd.DataFrame()

    orig_ix = orig.set_index(id_col)
    edit_ix = edit.set_index(id_col)

    # Sadece her iki tarafta da olan ID'leri karşılaştır
    common_ids = orig_ix.index.intersection(edit_ix.index)
    if len(common_ids) == 0:
        return pd.DataFrame()

    orig_ix = orig_ix.loc[common_ids]
    edit_ix = edit_ix.loc[common_ids]

    # String'e cast et + NaN'ları boş string'e çevir (NaN != NaN sorununu önle)
    orig_str = orig_ix.fillna("").astype(str)
    edit_str = edit_ix.fillna("").astype(str)

    # Hücre bazında fark
    diff_mask = (orig_str != edit_str).any(axis=1)
    changed_ids = common_ids[diff_mask]

    if len(changed_ids) == 0:
        return pd.DataFrame()

    # Orijinal tipleri korumak için edited'tan döndür
    return edit_ix.loc[changed_ids].reset_index()
