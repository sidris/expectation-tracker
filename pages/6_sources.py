"""Kaynaklar — ekle, düzenle, sil."""
import pandas as pd
import streamlit as st

from utils.db import fetch, insert, invalidate_cache
from utils.forecast_helpers import delete_source, update_source
from utils.grid import diff_rows, show_grid
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>📰 Kaynaklar</h1>
      <p>Tahmin verisinin geldiği kanallar: Reuters, Bloomberg HT, Matriks,
         köşe yazıları, TV programları.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

SOURCE_TYPES = ["news", "survey", "tv", "column", "report", "manual", "other"]
SOURCE_TYPE_LABELS = {
    "news": "Haber ajansı / portal",
    "survey": "Anket sahibi",
    "tv": "TV programı",
    "column": "Köşe yazısı",
    "report": "Rapor",
    "manual": "Manuel giriş",
    "other": "Diğer",
}
label_to_type = {v: k for k, v in SOURCE_TYPE_LABELS.items()}

tab_list, tab_add = st.tabs(["📋 Liste & Düzenle", "➕ Yeni Ekle"])

with tab_list:
    raw_df = pd.DataFrame(fetch("sources", order="name"))

    if raw_df.empty:
        st.info("Henüz kaynak yok. **Yeni Ekle** sekmesinden başla.")
    else:
        display_cols = [
            c for c in ["id", "name", "type", "publisher", "url", "reliability_score", "notes"]
            if c in raw_df.columns
        ]
        df = raw_df[display_cols].copy()

        st.caption(
            "Hücreye çift tıklayıp düzenle. Değişiklikler **Kaydet** butonuna basınca DB'ye yazılır."
        )

        result = show_grid(
            df,
            key="sources_grid",
            editable_columns=["name", "type", "publisher", "url", "reliability_score", "notes"],
            selectable=True,
            selection_mode="multiple",
            height=420,
        )

        edited_df = pd.DataFrame(result.get("data", df))
        selected = result.get("selected_rows", [])
        if isinstance(selected, pd.DataFrame):
            selected = selected.to_dict(orient="records")
        selected = selected or []

        c1, c2, _ = st.columns([1.2, 1.2, 3])
        save_btn = c1.button("💾 Değişiklikleri kaydet", type="primary", use_container_width=True)
        del_btn = c2.button(
            f"🗑️ Sil ({len(selected)})",
            use_container_width=True, disabled=not selected,
        )

        if save_btn:
            changed = diff_rows(df, edited_df, id_col="id")
            if changed.empty:
                st.info("Değişiklik yok.")
            else:
                count = 0
                for _, row in changed.iterrows():
                    payload = {k: row.get(k) for k in row.index if k != "id"}
                    update_source(row["id"], payload)
                    count += 1
                invalidate_cache()
                st.success(f"{count} kaynak güncellendi.")
                st.rerun()

        if del_btn and selected:
            st.session_state["sources_delete_confirm"] = [r["id"] for r in selected]

        if st.session_state.get("sources_delete_confirm"):
            ids = st.session_state["sources_delete_confirm"]
            st.error(
                f"⚠️ {len(ids)} kaynağı silmek üzeresin. Bu kaynağa bağlı tahminler "
                "**source_id alanı NULL'a düşürülerek** korunur (anket bağı bozulabilir)."
            )
            cc1, cc2, _ = st.columns([1, 1, 3])
            if cc1.button("✅ Evet, sil", type="primary"):
                for sid in ids:
                    delete_source(sid)
                del st.session_state["sources_delete_confirm"]
                invalidate_cache()
                st.success(f"{len(ids)} kaynak silindi.")
                st.rerun()
            if cc2.button("İptal"):
                del st.session_state["sources_delete_confirm"]
                st.rerun()

with tab_add:
    with st.form("new_source"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(
                "Kaynak adı",
                placeholder="Bloomberg HT, Reuters, Matriks...",
            )
            stype_label = st.selectbox("Tip", [SOURCE_TYPE_LABELS[t] for t in SOURCE_TYPES])
        with c2:
            publisher = st.text_input("Yayıncı")
            url = st.text_input("URL")
        notes = st.text_area("Not")
        ok = st.form_submit_button("Kaydet", type="primary")

    if ok and name:
        insert(
            "sources",
            {
                "name": name,
                "type": label_to_type.get(stype_label, "other"),
                "publisher": publisher,
                "url": url,
                "notes": notes,
            },
        )
        invalidate_cache()
        st.success("Kaynak kaydedildi.")
        st.rerun()
    elif ok and not name:
        st.error("Ad zorunlu.")
