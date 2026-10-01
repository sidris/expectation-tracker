"""Printable survey report and comparable institution ranking."""
from html import escape
import pandas as pd
import streamlit as st
from utils.db import fetch
from utils.domain import TARGET_TYPE_LABELS
from utils.export import excel_download_button
from utils.ui import inject_theme

inject_theme()
st.title('Rapor Üret')
st.caption('Seçilen gösterge ve dönem için anket özetleri, kurum cevapları ve tahmin hataları.')
polls = pd.DataFrame(fetch('v_poll_summaries'))
forecasts = pd.DataFrame(fetch('v_forecasts'))
if polls.empty:
    st.info('Rapor üretmek için önce anket ekleyin.'); st.stop()
kind = st.selectbox('Gösterge', list(TARGET_TYPE_LABELS), format_func=TARGET_TYPE_LABELS.get)
periods = sorted(polls.loc[polls.target_type == kind, 'target_period'].unique())
selected = st.multiselect('Hedef dönemler', periods, default=periods[-3:])
polls = polls[(polls.target_type == kind) & polls.target_period.isin(selected)]
st.subheader('Anket özetleri')
poll_columns = [c for c in ['target_period','published_at','source_name','poll_name','median_value','mean_value','min_value','max_value','participant_count','notes'] if c in polls]
st.dataframe(polls[poll_columns], hide_index=True, use_container_width=True)
tables = [('Anket özetleri', polls[poll_columns])]
if not forecasts.empty:
    forecasts = forecasts[(forecasts.target_type == kind) & forecasts.target_period.isin(selected)].copy()
    st.caption('Sıralama her kurum ve hedef dönem için son tahmini kullanır. Reuters/Matriks tekrarları ayrı puan oluşturmaz.')
    minimum = st.number_input('Sıralama için en az gerçekleşmiş dönem', 1, 100, 3)
    common = st.checkbox('Kurumları yalnızca ortak dönemlerde karşılaştır', value=True)
    eligible = forecasts.dropna(subset=['participant_id','actual_value']).sort_values(['forecast_date','created_at']).drop_duplicates(['participant_id','event_id'], keep='last')
    counts = eligible.groupby('participant_id').event_id.nunique()
    eligible = eligible[eligible.participant_id.isin(counts[counts >= minimum].index)]
    if common and not eligible.empty:
        institution_count = eligible.participant_id.nunique()
        shared = eligible.groupby('event_id').participant_id.nunique()
        eligible = eligible[eligible.event_id.isin(shared[shared == institution_count].index)]
    if not eligible.empty:
        eligible['error'] = eligible.forecast_value.astype(float) - eligible.actual_value.astype(float)
        eligible['absolute_error'] = eligible.error.abs()
        eligible['squared_error'] = eligible.error**2
        ranking = eligible.groupby(['participant_id','participant_name']).agg(Dönem=('event_id','nunique'), MAE=('absolute_error','mean'), RMSE=('squared_error',lambda s: s.mean()**0.5), Sapma=('error','mean')).reset_index()
        ranking = ranking[ranking['Dönem'] >= minimum].drop(columns='participant_id').sort_values('MAE')
        st.subheader('Tahminci sıralaması')
        st.dataframe(ranking, hide_index=True)
        tables.append(('Tahminci sıralaması',ranking))
        st.caption('MAE ve RMSE yüzde puan cinsindedir; düşük değer daha iyidir. Pozitif sapma fazla tahmini gösterir. Tahmin ufukları bu sıralamada eşitlenmez.')
    else: st.info('Seçilen koşullarda sıralama için yeterli gerçekleşme yok.')
    columns = [c for c in ['target_period','forecast_date','participant_name','source_name','forecast_value','actual_value','abs_error'] if c in forecasts]
    tables.append(('Kurum cevapları',forecasts[columns]))
    excel_download_button(forecasts[columns], 'tahminler.xlsx')
title = 'Beklenti Raporu — ' + TARGET_TYPE_LABELS[kind]
html = '<!doctype html><html lang="tr"><meta charset="utf-8"><title>'+escape(title)+'</title><style>body{font:14px Arial;margin:32px;color:#18202b}table{border-collapse:collapse;width:100%;margin-bottom:24px}th,td{padding:6px;border-bottom:1px solid #ddd;text-align:left}h2{margin-top:28px}@media print{thead{display:table-header-group}tr{break-inside:avoid}}</style><h1>'+escape(title)+'</h1><p>Hedef dönemler: '+escape(', '.join(selected))+'</p><p>Sıralama: son tahmin, en az '+str(minimum if not forecasts.empty else 3)+' dönem. Hata birimi: yüzde puan. Tahmin ufukları eşitlenmez.</p>'
html += ''.join('<h2>'+escape(label)+'</h2>'+frame.to_html(index=False,escape=True,na_rep='—') for label,frame in tables)
st.download_button('Yazdırılabilir rapor indir (HTML)', html, 'beklenti-raporu.html', 'text/html')
st.caption('İndirilen raporu tarayıcıda açıp Yazdır → PDF olarak kaydet seçeneğiyle PDF oluşturabilirsiniz.')
