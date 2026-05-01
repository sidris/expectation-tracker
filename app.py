import streamlit as st
from utils.ui import inject_theme

st.set_page_config(page_title="Beklenti Takip Sistemi", page_icon="📊", layout="wide")
inject_theme()

st.markdown("""
<div class="hero">
  <h1>📊 Beklenti Takip Sistemi</h1>
  <p>Enflasyon ve TCMB PPK faiz beklentileri için kayıt, filtreleme, Excel çıktı, dashboard ve tahminci performansı.</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Ana odak", "TÜFE & PPK")
c2.metric("Katılımcı türleri", "Kişi / Kurum / Medya")
c3.metric("Çıktı", "Excel + Dashboard")

st.markdown("""
<div class="soft-card">
<h3>Önerilen ek modüller</h3>
<ul>
<li><b>Revizyon takibi:</b> Aynı kişi/kurumun aynı hedef dönem için ilk ve son tahminini karşılaştır.</li>
<li><b>Konsensüs sapması:</b> Her tahmini anket medyanına göre ölç.</li>
<li><b>Kaynak güven skoru:</b> TV, rapor, haber ve manuel duyumları kalite seviyesine göre etiketle.</li>
<li><b>Alarm sistemi:</b> Yeni PPK/TÜFE beklentisi girildiğinde Telegram’dan özet gönder.</li>
<li><b>Tahminci profili:</b> Kişi/kurum bazında geçmiş başarı, yanılma yönü ve en iyi olduğu gösterge.</li>
</ul>
</div>
""", unsafe_allow_html=True)
