"""A survey entered in the same shape as the monthly bulletin."""
from datetime import date
import json
import math
import pandas as pd
import streamlit as st
from utils.db import fetch, invalidate_cache
from utils.domain import MONTHS_TR
from utils.import_survey import import_surveys
from utils.pdf_import import canonical_name
from utils.ui import inject_theme

inject_theme()
st.title('Anket gir')
st.caption('Dönemi seçin, anket özetini ve kurum cevaplarını girin. Kaydedilen veriler aylık bilgi notuna eklenir.')
c1,c2=st.columns(2)
year=c1.number_input('Hedef yıl',2000,2100,date.today().year)
month=c2.selectbox('Hedef ay',list(MONTHS_TR),index=date.today().month-1)
period=f'{year}-{MONTHS_TR[month]:02d}-01'
c1,c2=st.columns(2)
source=c1.selectbox('Anket kaynağı',['Reuters','Matriks','Bloomberg HT','CNBC-e','AA Finans','ForInvest','TCMB PKA','Diğer'])
if source=='Diğer': source=st.text_input('Anket kaynağının adı').strip()
published=c2.date_input('Anketin açıklanma tarihi',date.today(),help='Anketin yayınlandığı tarih. Hedef ay ve rapor tarihiyle aynı olmak zorunda değildir.')
st.subheader('Anket özeti')
st.caption('Virgüllü veya noktalı sayı yazabilirsiniz. Bilinmeyen alanları boş bırakın; 0 yazmayın.')
kinds={'Aylık TÜFE':'monthly_cpi','Yıllık TÜFE':'annual_cpi','Yıl sonu TÜFE':'year_end_cpi'}
summary=st.data_editor(pd.DataFrame([{'Gösterge':k,'Medyan':'','Ortalama':'','En düşük':'','En yüksek':'','Katılımcı':''} for k in kinds]),hide_index=True,disabled=['Gösterge'],use_container_width=True,key=f'entry_summary_{source}_{period}')
st.subheader('Kurum cevapları')
st.caption('Her kurumu bir satıra yazın. Yalnızca açıklanan tahminleri doldurun; yeni satır ekleyebilir veya Excel’den yapıştırabilirsiniz. QNB, Albaraka, HSBC ve Rota adları otomatik eşleştirilir.')
answers=st.data_editor(pd.DataFrame([{'Kurum':'','Aylık TÜFE':'','Yıllık TÜFE':'','Yıl sonu TÜFE':''}]),num_rows='dynamic',hide_index=True,use_container_width=True,key=f'entry_answers_{source}_{period}')
calculate=st.checkbox('Anket özetini kurum cevaplarından hesapla',help='Yalnızca tüm katılımcıların cevapları elinizdeyse kullanın. Resmî anket özeti farklı olabilir.')
with st.expander('Kaynak ve açıklama (isteğe bağlı)'):
    citation=st.text_input('Kaynak bağlantısı veya belge adı')
    notes=st.text_area('Veri notu')
def numeric(value):
    if value is None or pd.isna(value) or str(value).strip()=='': return None
    result=float(str(value).strip().replace(',','.').replace('%',''))
    if not math.isfinite(result): raise ValueError('Sayılar sonlu olmalı.')
    return result
payload={'summaries':[],'forecasts':[],'warnings':[]}
errors=[]
file=f'manual-{source}-{period}.json'
try:
    if not source: raise ValueError('Anket kaynağının adını girin.')
    seen=set()
    for _,row in answers.iterrows():
        name='' if pd.isna(row['Kurum']) else str(row['Kurum']).strip()
        values={kind:numeric(row[label]) for label,kind in kinds.items()}
        if not name and not any(v is not None for v in values.values()): continue
        if not name: raise ValueError('Tahmin girilen satırın kurum adı boş olamaz.')
        canonical=canonical_name(name)
        if canonical in seen: raise ValueError(f'{canonical} iki satırda yer alıyor. Cevapları tek satırda birleştirin.')
        seen.add(canonical)
        for kind,value in values.items():
            if value is not None:
                payload['forecasts'].append(dict(file=file,page=1,source_name=source,target_type=kind,target_period=f'{year}-12-01' if kind=='year_end_cpi' else period,published_at=str(published),report_date=str(published),date_basis='user_entered_publication_date',participant_name=canonical,original_name=name,forecast_value=value))
    for _,row in summary.iterrows():
        kind=kinds[row['Gösterge']]
        values={key:numeric(row[label]) for key,label in [('median_value','Medyan'),('mean_value','Ortalama'),('min_value','En düşük'),('max_value','En yüksek'),('participant_count','Katılımcı')]}
        vals=[r['forecast_value'] for r in payload['forecasts'] if r['target_type']==kind]
        if calculate and vals:
            series=pd.Series(vals)
            values=dict(median_value=float(series.median()),mean_value=float(series.mean()),min_value=min(vals),max_value=max(vals),participant_count=len(vals))
        if not vals and not any(v is not None for v in values.values()): continue
        count=values['participant_count']
        if count is not None and (count<0 or not float(count).is_integer()): raise ValueError('Katılımcı sayısı negatif olmayan tam sayı olmalı.')
        low,high=values['min_value'],values['max_value']
        if low is not None and high is not None and low>high: raise ValueError('En düşük değer, en yüksek değerden büyük olamaz.')
        for key in ['median_value','mean_value']:
            v=values[key]
            if v is not None and ((low is not None and v<low) or (high is not None and v>high)): raise ValueError('Medyan/ortalama, en düşük ve en yüksek aralığında olmalı.')
        if count is not None and count<len(vals): raise ValueError('Katılımcı sayısı girilen kurum cevabı sayısından az olamaz.')
        payload['summaries'].append(dict(file=file,page=1,source_name=source,target_type=kind,target_period=f'{year}-12-01' if kind=='year_end_cpi' else period,published_at=str(published),report_date=str(published),date_basis='user_entered_publication_date',notes='Kullanıcı girişi. '+notes+' Kaynak: '+citation,**values))
except (ValueError,TypeError) as error: errors.append(str(error))
if errors:
    for error in errors: st.error(error)
elif payload['summaries']:
    st.subheader('Kaydetmeden önce kontrol')
    st.write(f'{month} {year} · {source} · {len(payload["summaries"])} gösterge · {len(payload["forecasts"])} kurum tahmini')
    if payload['forecasts']:
        preview=pd.DataFrame(payload['forecasts'])[['original_name','participant_name','target_type','forecast_value']].rename(columns={'original_name':'Girilen ad','participant_name':'Eşleşen kurum','target_type':'Gösterge','forecast_value':'Tahmin (%)'})
        st.dataframe(preview,hide_index=True,use_container_width=True)
    checked=st.checkbox('Değerleri ve açıklanma tarihini kontrol ettim.')
    if st.button('Anketi kaydet',type='primary',disabled=not checked):
        try:
            result=import_surveys(payload); invalidate_cache()
            st.success(f'Anket kaydedildi. {result["summaries"]} özet ve {result["forecasts"]} tahmin eklendi; {result["skipped"]} aynı kayıt atlandı.')
            st.page_link('pages/15_report.py',label='Aylık bilgi notunu oluştur')
        except Exception as error:
            invalidate_cache(); st.error(str(error)); st.info('Kayıt kısmen tamamlanmış olabilir. Aynı değerlerle tekrar deneyebilirsiniz; mevcut veriler üzerine yazılmaz.')
else: st.info('Anket özetinde veya kurum cevaplarında en az bir değer girin.')
