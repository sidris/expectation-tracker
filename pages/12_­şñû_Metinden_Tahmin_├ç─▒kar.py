import streamlit as st
import pandas as pd
from utils.db import fetch, insert
from utils.extract import parse_capture
from utils.ui import inject_theme

inject_theme()
st.title("🤖 Metinden Tahmin Çıkar")
st.caption("TV notu, haber metni veya köşe yazısından sayıları ve olası gösterge tipini ön ayrıştırır.")
sources = fetch("sources", order="name")
smap = {s["name"]: s["id"] for s in sources}
source = st.selectbox("Kaynak", [""] + list(smap.keys()))
text = st.text_area("Ham metin", height=220, placeholder="Örn: Deutsche Bank yıl sonu enflasyon beklentisini yüzde 38,5 olarak açıkladı...")
if st.button("Ön ayrıştır") and text:
    parsed = parse_capture(text)
    insert("raw_captures", {"source_id": smap.get(source) if source else None, "capture_text": text, "parsed_payload": parsed, "status": "parsed"})
    st.json(parsed)
    st.info("Bu kayıt ham havuza eklendi. Değeri kontrol edip Tahmin Girişi sayfasından kesin tahmin olarak kaydedin.")

st.markdown("### Son ham kayıtlar")
st.dataframe(pd.DataFrame(fetch("raw_captures", order="captured_at", limit=200)), use_container_width=True, hide_index=True)
