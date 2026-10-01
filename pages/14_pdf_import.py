"""PDF-shaped editable tables and checked, resumable import."""
import json
import pandas as pd
import streamlit as st
from utils.pdf_import import parse_pdf, canonical_name
from utils.import_survey import import_surveys
from utils.db import invalidate_cache
from utils.ui import inject_theme
from utils.survey_data import load_survey_data

inject_theme()
st.title('PDF / Tablo ile Anket Girişi')
st.caption('Kurumlar satırlarda, tahminler tablolarda. Boş değerler sıfır olarak kaydedilmez.')
mode = st.radio('Veri kaynağı', ['Hazır Ocak–Ağustos 2026 paketi', 'Yeni PDF / JSON yükle'], horizontal=True)
files = []
if mode == 'Yeni PDF / JSON yükle':
    files = st.file_uploader('Bilgi notları (PDF) veya hazırlanmış JSON', type=['pdf','json'], accept_multiple_files=True)
    if not files:
        st.info('Ocak–Ağustos veri paketini veya aynı düzende yeni PDF’leri yükleyin.')
        st.stop()
payload = {'summaries':[], 'forecasts':[], 'warnings':[]}
if mode == 'Hazır Ocak–Ağustos 2026 paketi':
    payload = load_survey_data()
try:
    for file in files:
        parsed = json.loads(file.getvalue()) if file.name.endswith('.json') else parse_pdf(file.getvalue(), file.name)
        for key in payload: payload[key].extend(parsed.get(key,[]))
except Exception as error:
    st.error(str(error)); st.stop()
for warning in payload['warnings']: st.warning(warning)
st.info('Yayın/tahmin tarihleri rapordan alınmıştır; kurumların özgün açıklama tarihleriyle doğrulanmamıştır. Bilinen tarihleri düzeltin; rapor tarihi ayrıca korunur. PKA yayın tarihi bilinmiyor. HSBC Hldg → HSBC Portföy ve Rota Yatırım → Rota Portföy eşleşmeleri uygulanır. Kaynakta olası hatalar varsa özgün dosyayı koruyarak düzeltin.')
include_pka = st.checkbox('PKA özetlerini de aktar (bilinmeyen yayın tarihleri boş kalır)', value=True)
if not include_pka:
    payload['summaries'] = [r for r in payload['summaries'] if r['source_name'] != 'TCMB PKA']
st.subheader('Anket özetleri')
summaries = st.data_editor(pd.DataFrame(payload['summaries']), hide_index=True, use_container_width=True,
    disabled=['file','page','source_name','target_type','target_period'], key='pdf_summaries')
st.subheader('Kurum cevapları')
forecasts = st.data_editor(pd.DataFrame(payload['forecasts']), hide_index=True, use_container_width=True,
    disabled=['file','page','source_name','target_type','target_period','original_name','report_date','date_basis'], key='pdf_forecasts')
def records(frame):
    return json.loads(frame.to_json(orient='records', force_ascii=False))
edited = dict(summaries=records(summaries), forecasts=records(forecasts), warnings=payload['warnings'])
for row in edited['forecasts']: row['participant_name'] = canonical_name(row['participant_name'])
st.download_button('Kontrol edilmiş JSON indir', json.dumps(edited, ensure_ascii=False, indent=2), 'anketler.json', 'application/json')
checked = st.checkbox('Kurum eşleşmelerini, değerleri ve yayın tarihlerini kontrol ettim.')
if st.button('Supabase’e aktar', type='primary', disabled=not checked):
    try:
        for row in edited['summaries'] + edited['forecasts']:
            if not row.get('published_at') and row['source_name'] != 'TCMB PKA': raise ValueError('PKA dışındaki yayın tarihlerini girin.')
            if row.get('published_at'): pd.Timestamp(row['published_at'])
            if row.get('forecast_value') is None and row in edited['forecasts']: raise ValueError('Tahmin değeri boş olamaz.')
        result = import_surveys(edited)
        invalidate_cache()
        st.success(f"{result['summaries']} özet, {result['forecasts']} tahmin eklendi; {result['skipped']} mevcut kayıt atlandı.")
    except Exception as error:
        invalidate_cache()
        st.error(str(error))
        st.info('Aktarım kısmen tamamlanmış olabilir. Sorunu düzelterek tekrar çalıştırın; aynı değerli mevcut kayıtlar atlanır.')
