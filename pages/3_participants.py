import streamlit as st
from utils.db import insert, fetch

st.title("👥 Katılımcılar")

# Mevcut katılımcıları çek
participants = fetch("participants", order="name")

with st.form("participant_form"):

    name = st.text_input("Ad / kurum adı")

    ptype = st.selectbox(
        "Tip",
        ["person", "institution"]
    )

    institution_name = st.text_input("Kurum (kişiler için)")
    title = st.text_input("Ünvan")
    notes = st.text_area("Not")

    submitted = st.form_submit_button("Kaydet")

    if submitted:

        if not name.strip():
            st.error("İsim boş olamaz")
        else:
            # 🔥 DUPLICATE KONTROL
            existing = [
                p for p in participants
                if p["name"].strip().lower() == name.strip().lower()
            ]

            if existing:
                st.warning("⚠️ Bu katılımcı zaten kayıtlı.")
            else:
                try:
                    insert("participants", {
                        "name": name.strip(),
                        "type": ptype,
                        "institution_name": institution_name.strip() if institution_name else None,
                        "title": title.strip() if title else None,
                        "notes": notes.strip() if notes else None
                    })

                    st.success("✅ Katılımcı eklendi")

                except Exception as e:
                    st.error("❌ Kayıt sırasında hata oluştu")
                    st.code(str(e))

# --- Liste gösterimi ---
st.markdown("### Kayıtlı katılımcılar")

if participants:
    for p in participants:
        st.write(f"- {p['name']} ({p['type']})")
else:
    st.info("Henüz katılımcı yok")