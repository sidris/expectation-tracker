"""Veri Havuzu — tüm verileri gör, filtrele, düzenle, indir."""
from io import BytesIO

import pandas as pd
import streamlit as st

from utils.db import fetch, invalidate_cache
from utils.export import apply_common_filters, excel_download_button
from utils.forecast_helpers import delete_forecast, update_forecast
from utils.grid import show_grid
from utils.ui import inject_theme

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>🗃️ Veri Havuzu</h1>
      <p>Sistemdeki tüm tahmin, anket, gerçekleşme, katılımcı ve kaynak verilerini
         filtrele, düzenle ve Excel olarak indir.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "Tahminler", "Anket özetleri", "Gerçekleşmeler",
    "Katılımcılar", "Kaynaklar", "Tüm Excel paketi",
])

# ---------------------------------------------------------------------------
# Tahminler — düzenleme destekli
# ---------------------------------------------------------------------------

with tabs[0]:
    df = pd.DataFrame(fetch("v_forecasts"))
    if df.empty:
        st.info("Henüz tahmin yok.")
    else:
        dff = apply_common_filters(df, key_prefix="pool_forecasts")

        # Görüntülenecek kolonlar (UUID'ler grid'in kendisi gizler)
        display_order = [
            "id",
            "participant_name", "target_type_label", "target_period",
            "forecast_value", "forecast_date",
            "actual_value", "abs_error",
            "source_name", "poll_name",
            "source_text", "source_url", "notes",
            "horizon_days", "is_latest_for_participant_event",
            "event_id", "participant_id", "source_id", "poll_id",
            "created_at",
        ]
        cols_present = [c for c in display_order if c in dff.columns]
        # Geri kalan kolonları da en sona ekle (ham veri vb.)
        cols_present += [c for c in dff.columns if c not in cols_present]
        df_show = dff[cols_present].copy()

        excel_download_button(dff, "tahmin_havuzu.xlsx", "Tahmin havuzunu Excel indir")

        st.caption(
            "💡 **Tahmin değerlerini ve notları doğrudan tabloda düzenleyebilirsin.** "
            "Hücreye çift tıkla, değiştir, **Kaydet**'e bas. ID/dönem gibi yapısal "
            "alanlar değiştirilemez (yanlış girilen bir kaydı silip Tek Tahmin Girişi'nden yeniden ekle)."
        )

        result = show_grid(
            df_show,
            key="forecasts_grid",
            editable_columns=[
                "forecast_value", "forecast_date",
                "source_text", "source_url", "notes",
            ],
            selectable=True,
            selection_mode="multiple",
            height=520,
        )

        edited_df = pd.DataFrame(result.get("data", df_show))
        selected = result.get("selected_rows", [])
        if isinstance(selected, pd.DataFrame):
            selected = selected.to_dict(orient="records")
        selected = selected or []

        c1, c2, _ = st.columns([1.5, 1.5, 3])
        save_btn = c1.button(
            "💾 Tahmin değişikliklerini kaydet",
            type="primary", use_container_width=True,
        )
        del_btn = c2.button(
            f"🗑️ Seçili tahminleri sil ({len(selected)})",
            use_container_width=True, disabled=not selected,
        )

        if save_btn:
            # diff_rows üzerinden gitmek yerine direkt loop — view kaynaklı,
            # sadece izinli alanlar update_forecast içinde filtreleniyor.
            from utils.grid import diff_rows
            changed = diff_rows(df_show, edited_df, id_col="id")
            if changed.empty:
                st.info("Değişiklik yok.")
            else:
                count = 0
                for _, row in changed.iterrows():
                    payload = {
                        "forecast_value": row.get("forecast_value"),
                        "forecast_date": str(row.get("forecast_date")) if pd.notna(row.get("forecast_date")) else None,
                        "source_text": row.get("source_text"),
                        "source_url": row.get("source_url"),
                        "notes": row.get("notes"),
                    }
                    update_forecast(row["id"], payload)
                    count += 1
                invalidate_cache()
                st.success(f"{count} tahmin güncellendi.")
                st.rerun()

        if del_btn and selected:
            st.session_state["forecasts_delete_confirm"] = [r["id"] for r in selected]

        if st.session_state.get("forecasts_delete_confirm"):
            ids = st.session_state["forecasts_delete_confirm"]
            st.error(f"⚠️ {len(ids)} tahmini kalıcı olarak silmek üzeresin.")
            cc1, cc2, _ = st.columns([1, 1, 3])
            if cc1.button("✅ Evet, sil", type="primary"):
                for fid in ids:
                    delete_forecast(fid)
                del st.session_state["forecasts_delete_confirm"]
                invalidate_cache()
                st.success(f"{len(ids)} tahmin silindi.")
                st.rerun()
            if cc2.button("İptal"):
                del st.session_state["forecasts_delete_confirm"]
                st.rerun()

# ---------------------------------------------------------------------------
# Anket özetleri (salt-okunur — düzenleme Anket Yönetimi'nde)
# ---------------------------------------------------------------------------

with tabs[1]:
    df = pd.DataFrame(fetch("v_poll_summaries"))
    if df.empty:
        st.info("Henüz anket yok.")
    else:
        dff = apply_common_filters(df, key_prefix="pool_polls")
        excel_download_button(dff, "anket_ozetleri.xlsx", "Anket özetlerini Excel indir")
        st.caption("Anketleri düzenlemek için **Anket Yönetimi** sayfasını kullan.")
        show_grid(dff, key="polls_grid", height=420)

# ---------------------------------------------------------------------------
# Gerçekleşmeler (salt-okunur — düzenleme Gerçekleşmeler'de)
# ---------------------------------------------------------------------------

with tabs[2]:
    df = pd.DataFrame(fetch("actuals", order="released_at", desc=True))
    if df.empty:
        st.info("Henüz gerçekleşme yok.")
    else:
        excel_download_button(df, "gerceklesmeler.xlsx", "Gerçekleşmeleri Excel indir")
        st.caption("Gerçekleşmeleri düzenlemek için **Gerçekleşmeler** sayfasını kullan.")
        show_grid(df, key="actuals_grid", height=420)

# ---------------------------------------------------------------------------
# Katılımcılar (salt-okunur — düzenleme Katılımcılar'da)
# ---------------------------------------------------------------------------

with tabs[3]:
    df = pd.DataFrame(fetch("participants", order="name"))
    if df.empty:
        st.info("Henüz katılımcı yok.")
    else:
        excel_download_button(df, "katilimcilar.xlsx", "Katılımcıları Excel indir")
        st.caption("Katılımcıları düzenlemek için **Katılımcılar** sayfasını kullan.")
        show_grid(df, key="participants_pool_grid", height=420)

# ---------------------------------------------------------------------------
# Kaynaklar (salt-okunur — düzenleme Kaynaklar'da)
# ---------------------------------------------------------------------------

with tabs[4]:
    df = pd.DataFrame(fetch("sources", order="captured_at", desc=True))
    if df.empty:
        st.info("Henüz kaynak yok.")
    else:
        excel_download_button(df, "kaynaklar.xlsx", "Kaynakları Excel indir")
        st.caption("Kaynakları düzenlemek için **Kaynaklar** sayfasını kullan.")
        show_grid(df, key="sources_pool_grid", height=420)

# ---------------------------------------------------------------------------
# Tüm Excel paketi
# ---------------------------------------------------------------------------

with tabs[5]:
    datasets = {
        "tahminler": pd.DataFrame(fetch("v_forecasts")),
        "anket_ozetleri": pd.DataFrame(fetch("v_poll_summaries")),
        "gerceklesmeler": pd.DataFrame(fetch("actuals")),
        "katilimcilar": pd.DataFrame(fetch("participants")),
        "kaynaklar": pd.DataFrame(fetch("sources")),
        "leaderboard": pd.DataFrame(fetch("v_leaderboard")),
    }
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, data in datasets.items():
            data.to_excel(writer, index=False, sheet_name=name[:31])
    st.download_button(
        "📦 Tüm verileri tek Excel dosyası olarak indir",
        output.getvalue(),
        "beklenti_takip_tum_veriler.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
