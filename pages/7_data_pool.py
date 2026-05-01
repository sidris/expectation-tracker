import streamlit as st
import pandas as pd
from utils.db import fetch
from utils.export import apply_common_filters, excel_download_button

st.title("🗃️ Veri Havuzu")
st.caption("Sistemdeki tüm tahmin, anket, gerçekleşme, katılımcı ve kaynak verilerini tek yerden görün ve Excel olarak indirin.")

tabs = st.tabs(["Tahminler", "Anket özetleri", "Gerçekleşmeler", "Katılımcılar", "Kaynaklar", "Tüm Excel Paketi"])

with tabs[0]:
    df = pd.DataFrame(fetch("v_forecasts"))
    dff = apply_common_filters(df, key_prefix="pool_forecasts") if not df.empty else df
    excel_download_button(dff, "tahmin_havuzu.xlsx", "Tahmin havuzunu Excel indir")
    st.dataframe(dff, use_container_width=True)

with tabs[1]:
    df = pd.DataFrame(fetch("v_poll_summaries"))
    dff = apply_common_filters(df, key_prefix="pool_polls") if not df.empty else df
    excel_download_button(dff, "anket_ozetleri.xlsx", "Anket özetlerini Excel indir")
    st.dataframe(dff, use_container_width=True)

with tabs[2]:
    df = pd.DataFrame(fetch("actuals"))
    excel_download_button(df, "gerceklesmeler.xlsx", "Gerçekleşmeleri Excel indir")
    st.dataframe(df, use_container_width=True)

with tabs[3]:
    df = pd.DataFrame(fetch("participants", order="name"))
    excel_download_button(df, "katilimcilar.xlsx", "Katılımcıları Excel indir")
    st.dataframe(df, use_container_width=True)

with tabs[4]:
    df = pd.DataFrame(fetch("sources", order="captured_at"))
    excel_download_button(df, "kaynaklar.xlsx", "Kaynakları Excel indir")
    st.dataframe(df, use_container_width=True)

with tabs[5]:
    datasets = {
        "tahminler": pd.DataFrame(fetch("v_forecasts")),
        "anket_ozetleri": pd.DataFrame(fetch("v_poll_summaries")),
        "gerceklesmeler": pd.DataFrame(fetch("actuals")),
        "katilimcilar": pd.DataFrame(fetch("participants")),
        "kaynaklar": pd.DataFrame(fetch("sources")),
        "leaderboard": pd.DataFrame(fetch("v_leaderboard")),
    }
    from io import BytesIO
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
