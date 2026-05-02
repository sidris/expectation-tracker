"""Expectation Tracker — ana giriş.

Sayfalar pages/ klasöründen otomatik yüklenir.
Streamlit'in dosya numarasına göre sıralaması sayfa sırasını belirler.
"""
import streamlit as st

from utils.ui import inject_theme

st.set_page_config(
    page_title="Expectation Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

st.markdown(
    """
    <div class="hero">
      <h1>📈 Expectation Tracker</h1>
      <p>Türkiye enflasyon ve PPK politika faizi beklentilerini izleme sistemi.
         Sol menüden bir sayfa seçerek başla.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Hızlı erişim")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        """
        **Veri girişi**
        - 📊 Anket Yönetimi — Reuters/Matriks anketleri
        - ✍️ Tek Tahmin Girişi — anket dışı tahminler
        - 👥 Katılımcılar
        - 📰 Kaynaklar
        - 🤖 Metinden Tahmin Çıkar
        """
    )

with c2:
    st.markdown(
        """
        **Analiz**
        - 📈 Dashboard
        - 🔁 Revizyon Takibi
        - 👤 Tahminci Profili
        - 📌 Konsensus Analizi
        - ⭐ Kaynak Güven Skoru
        """
    )

with c3:
    st.markdown(
        """
        **Operasyon**
        - ✅ Gerçekleşmeler — EVDS/BIS sync
        - 🗃️ Veri Havuzu — Excel export
        - 🕘 Aktivite Akışı
        """
    )

st.caption(
    "Veriler Supabase'de saklanır. EVDS ve BIS gerçekleşme verileri günlük "
    "GitHub Actions ile otomatik güncellenir."
)
