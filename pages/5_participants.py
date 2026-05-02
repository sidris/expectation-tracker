"""Katılımcılar (kişi ve kurumlar) — ekle, düzenle, sil/deaktif et."""
import pandas as pd
import streamlit as st

from utils.db import fetch, insert, invalidate_cache
from utils.domain import PARTICIPANT_TYPES, PARTICIPANT_TYPE_LABELS
from utils.forecast_helpers import (
    deactivate_participant,
    delete_participant,
    update_participant,
)
from utils.grid import diff_rows, show_grid
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>👥 Katılımcılar</h1>
      <p>Tahmin verisi gelen kişi ve kurumlar (Albaraka, QNB, Deutsche Bank,
         köşe yazarları vb.). Listeden seçip düzenleyebilir veya silebilirsin.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

label_to_type = {v: k for k, v in PARTICIPANT_TYPE_LABELS.items() if k in PARTICIPANT_TYPES}
type_labels = list(label_to_type.keys())

tab_list, tab_add = st.tabs(["📋 Liste & Düzenle", "➕ Yeni Ekle"])

# ---------------------------------------------------------------------------
# Liste & düzenle
# ---------------------------------------------------------------------------

with tab_list:
    raw_df = pd.DataFrame(fetch("participants", order="name"))

    if raw_df.empty:
        st.info("Henüz katılımcı yok. **Yeni Ekle** sekmesinden başla.")
    else:
        # Görünür alanlar
        display_cols = [
            c for c in ["id", "name", "type", "institution_name", "title", "is_active", "notes"]
            if c in raw_df.columns
        ]
        df = raw_df[display_cols].copy()

        st.caption(
            "Hücreye çift tıklayıp düzenle. **Tip** kolonu sistem değeri (`person`/`institution`) "
            "olarak tutulur. Değişiklikler **Kaydet** butonuna basınca DB'ye yazılır."
        )

        result = show_grid(
            df,
            key="participants_grid",
            editable_columns=["name", "type", "institution_name", "title", "is_active", "notes"],
            selectable=True,
            selection_mode="multiple",
            height=420,
        )

        edited_df = pd.DataFrame(result.get("data", df))
        selected = result.get("selected_rows", [])
        if isinstance(selected, pd.DataFrame):
            selected = selected.to_dict(orient="records")
        selected = selected or []

        c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2])
        save_btn = c1.button("💾 Değişiklikleri kaydet", type="primary", use_container_width=True)
        deact_btn = c2.button(
            f"🚫 Pasifleştir ({len(selected)})",
            use_container_width=True, disabled=not selected,
        )
        del_btn = c3.button(
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
                    update_participant(row["id"], payload)
                    count += 1
                invalidate_cache()
                st.success(f"{count} katılımcı güncellendi.")
                st.rerun()

        if deact_btn and selected:
            for row in selected:
                deactivate_participant(row["id"])
            invalidate_cache()
            st.success(f"{len(selected)} katılımcı pasifleştirildi.")
            st.rerun()

        if del_btn and selected:
            confirm_key = "participants_delete_confirm"
            st.session_state[confirm_key] = [r["id"] for r in selected]

        if st.session_state.get("participants_delete_confirm"):
            ids = st.session_state["participants_delete_confirm"]
            st.error(
                f"⚠️ {len(ids)} katılımcıyı **kalıcı olarak silmek üzeresin**. "
                "Bu kişilerin/kurumların tüm tahminleri de silinecek (FK cascade). "
                "Sadece pasifleştirmek için **Pasifleştir** kullan."
            )
            cc1, cc2, _ = st.columns([1, 1, 3])
            if cc1.button("✅ Evet, sil", type="primary"):
                for pid in ids:
                    delete_participant(pid)
                del st.session_state["participants_delete_confirm"]
                invalidate_cache()
                st.success(f"{len(ids)} katılımcı silindi.")
                st.rerun()
            if cc2.button("İptal"):
                del st.session_state["participants_delete_confirm"]
                st.rerun()

# ---------------------------------------------------------------------------
# Yeni ekle
# ---------------------------------------------------------------------------

with tab_add:
    with st.form("new_participant"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Ad / kurum adı")
            ptype_label = st.selectbox("Tip", type_labels)
        with c2:
            institution_name = st.text_input("Bağlı kurum / yayın")
            title = st.text_input("Unvan")
        notes = st.text_area("Not")
        ok = st.form_submit_button("Kaydet", type="primary")

    if ok and name:
        insert(
            "participants",
            {
                "name": name,
                "type": label_to_type.get(ptype_label, "person"),
                "institution_name": institution_name,
                "title": title,
                "notes": notes,
            },
        )
        invalidate_cache()
        st.success("Katılımcı kaydedildi.")
        st.rerun()
    elif ok and not name:
        st.error("Ad zorunlu.")
