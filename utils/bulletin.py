"""Monthly survey bulletin: vector lollipops and a directly downloadable PDF."""
from datetime import date
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import math
import pandas as pd

MONTHS = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']

def number(value):
    if value is None or pd.isna(value): return '—'
    return f'{float(value):.2f}'.replace('.', ',')

def month_data(polls, forecasts, period):
    """Use one latest observation per source; preserve same-month year-end revisions."""
    monthly_files = {(r.get('raw_payload') or {}).get('file') for r in polls
                     if r['target_period'] == period and r['target_type'] == 'monthly_cpi'} - {None}
    selected = []
    for r in polls:
        raw = r.get('raw_payload') or {}
        if r['target_type'] in ['monthly_cpi','annual_cpi'] and r['target_period'] == period:
            selected.append(r)
        elif r['target_type'] == 'year_end_cpi' and (r['target_period'][:4] == period[:4] or (r['source_name']=='TCMB PKA' and int(r['target_period'][:4])==int(period[:4])+1)):
            if raw.get('file') in monthly_files or str(r.get('published_at') or '')[:7] == period[:7]:
                selected.append(r)
    chosen = {}
    for r in sorted(selected, key=lambda r: (bool((r.get('raw_payload') or {}).get('file')), str(r.get('published_at') or ''), str(r.get('created_at') or ''))):
        chosen[(r['source_name'],r['target_type'],r['target_period'])] = r
    selected = list(chosen.values())
    ids = {r['id'] for r in selected}
    answers = [r for r in forecasts if r.get('poll_id') in ids and r.get('forecast_value') is not None]
    return selected, answers

def build_pdf(polls, answers, period, report_date):
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
    from reportlab.lib.pagesizes import A4
    fontdir = Path(reportlab.__file__).parent / 'fonts'
    for name, file in [('Bulletin','Vera.ttf'),('BulletinBold','VeraBd.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont(name, str(fontdir/file)))
    pdfmetrics.registerFontFamily('Bulletin', normal='Bulletin', bold='BulletinBold')
    ink, accent = colors.HexColor('#23344b'), colors.HexColor('#225c90')
    style = ParagraphStyle('body', fontName='Bulletin', fontSize=9, leading=14, textColor=ink, spaceAfter=10)
    heading = ParagraphStyle('heading', parent=style, fontName='BulletinBold', fontSize=16, leading=22, spaceAfter=16)
    sub = ParagraphStyle('sub', parent=style, fontName='BulletinBold', fontSize=11, leading=16, spaceBefore=12)
    month = MONTHS[int(period[5:7])-1] + ' ' + period[:4]
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=45)
    story = [Paragraph(escape(month+' TÜFE Beklenti Anketlerine İlişkin Bilgi Notu'), heading), Paragraph('Rapor tarihi: '+escape(str(report_date)), style)]
    monthly = [r for r in polls if r['target_type']=='monthly_cpi' and r.get('median_value') is not None]
    if monthly:
        vals = [float(r['median_value']) for r in monthly]
        story.append(Paragraph(f'Mevcut anketlerin aylık TÜFE medyan beklentileri %{number(min(vals))} ile %{number(max(vals))} arasındadır. Anket özetleri ve kurum bazında beklentiler aşağıda sunulmaktadır.', style))
    def table(rows, widths):
        data = [[Paragraph(escape(str(v)), style) for v in row] for row in rows]
        t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf2f7')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),3),('LINEBELOW',(0,0),(-1,0),0.7,accent),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#dde3e9'))]))
        return t
    for kind, label in [('monthly_cpi','Aylık enflasyon beklentileri'),('annual_cpi','Yıllık enflasyon beklentileri'),('year_end_cpi','Yıl sonu enflasyon beklentileri')]:
        rows = [r for r in polls if r['target_type']==kind and r['target_period'][:4]==period[:4]]
        if not rows: continue
        story.append(Paragraph(label, sub))
        cells = [['Anket','Medyan','Ortalama','En düşük','En yüksek','Katılımcı']]
        cells += [[r['source_name'],number(r.get('median_value')),number(r.get('mean_value')),number(r.get('min_value')),number(r.get('max_value')),str(int(r['participant_count'])) if r.get('participant_count') is not None else '—'] for r in sorted(rows,key=lambda r:r['source_name'])]
        story.append(table(cells,[125,62,66,64,64,70]))
    story.append(Spacer(1,12))
    next_pka=[r for r in polls if r['source_name']=='TCMB PKA' and r['target_type']=='year_end_cpi' and int(r['target_period'][:4])==int(period[:4])+1]
    for r in next_pka: story.append(Paragraph(f'PKA gelecek yıl sonu ({r["target_period"][:4]}) TÜFE beklentisi: %{number(r.get("mean_value"))}.',style))
    story.append(Paragraph('Boş değerler sıfır değildir. PKA değerleri ortalamadır; medyanlarla aynı ölçü olarak yorumlanmamalıdır. Yıl sonu tablosu bu anket dönemine ait gözlemleri gösterir.',style))
    class Lollipop(Flowable):
        def __init__(self, rows, median, actual):
            Flowable.__init__(self); self.rows=rows; self.median=median; self.actual=actual
            self.width=511; self.height=42+len(rows)*19
        def draw(self):
            c=self.canv; left,right=175,470
            values=[float(r['forecast_value']) for r in self.rows]+[v for v in [self.median,self.actual] if v is not None]
            lo,hi=min(0,min(values)),max(0,max(values)); span=hi-lo or 1
            x=lambda v:left+(float(v)-lo)/span*(right-left)
            top=self.height-12; bottom=28
            for v in [lo,lo+span/2,hi]:
                c.setStrokeColor(colors.HexColor('#e1e7ec')); c.line(x(v),bottom,x(v),top+4)
                c.setFillColor(ink); c.setFont('Bulletin',8); c.drawCentredString(x(v),10,number(v))
            for val,col in [(self.median,accent),(self.actual,colors.HexColor('#aa4b24'))]:
                if val is not None:
                    c.setStrokeColor(col); c.setDash(3,3); c.line(x(val),bottom,x(val),top+4); c.setDash()
            for i,r in enumerate(self.rows):
                y=top-i*19; c.setFont('Bulletin',8); c.setFillColor(ink)
                name=r['participant_name']
                while pdfmetrics.stringWidth(name,'Bulletin',8)>164: name=name[:-2]+'…'
                c.drawString(0,y-3,name); c.setStrokeColor(accent); c.setLineWidth(1.3)
                c.line(x(0),y,x(r['forecast_value']),y); c.setFillColor(accent); c.circle(x(r['forecast_value']),y,3.4,fill=1,stroke=0)
                c.setFillColor(ink); c.drawString(right+9,y-3,number(r['forecast_value']))
    for poll in sorted([p for p in polls if p['target_type']=='monthly_cpi'],key=lambda p:p['source_name']):
        rows=sorted([r for r in answers if r['poll_id']==poll['id']],key=lambda r:float(r['forecast_value']))
        if not rows: continue
        actuals={float(r['actual_value']) for r in rows if r.get('actual_value') is not None and not pd.isna(r['actual_value'])}
        actual=next(iter(actuals)) if len(actuals)==1 else None
        for start in range(0,len(rows),24):
            story.append(PageBreak()); story.append(Paragraph(escape(poll['source_name']+' — '+month+' aylık TÜFE beklentileri')+(' (devam)' if start else ''),heading))
            story.append(Paragraph('Mavi kesikli çizgi: anket medyanı'+('; turuncu kesikli çizgi: gerçekleşme.' if actual is not None else '. Gerçekleşme henüz kayıtlı değil.'),style))
            story.append(Lollipop(rows[start:start+24],poll.get('median_value'),actual))
            story.append(Spacer(1,12))
            story.append(Paragraph('Anket yayın tarihi: '+escape(str(poll.get('published_at') or 'bilinmiyor'))+'. Beklentiler yüzde cinsindedir.',style))
    notes = [r['source_name']+': '+str(r['notes']) for r in polls if r.get('notes')]
    if notes:
        story.append(PageBreak()); story.append(Paragraph('Kaynak ve veri notları',heading))
        for text in notes: story.append(Paragraph(escape(text),style))
    def footer(c,d):
        c.setFont('Bulletin',8); c.setFillColor(ink); c.drawString(42,25,month+' | Beklenti Tracker'); c.drawRightString(A4[0]-42,25,str(d.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()

def render_bulletin():
    import streamlit as st
    import plotly.graph_objects as go
    from utils.db import fetch
    raw={r['id']:r for r in fetch('poll_summaries')}
    polls=[dict(r,raw_payload=raw.get(r['id'],{}).get('raw_payload')) for r in fetch('v_poll_summaries')]
    forecasts=fetch('v_forecasts')
    periods=sorted({r['target_period'] for r in polls if r['target_type']=='monthly_cpi'})
    st.subheader('Aylık anket bilgi notu')
    st.caption('Özet tablolar ve kurum bazında lolipop grafikler, tek PDF dosyasında.')
    if not periods: st.info('Önce aylık TÜFE anketi girin.'); return
    a,b=st.columns(2)
    period=a.selectbox('Rapor dönemi',periods,index=len(periods)-1,format_func=lambda p:MONTHS[int(p[5:7])-1]+' '+p[:4])
    report_date=b.date_input('Rapor tarihi',value=date.today())
    selected,answers=month_data(polls,forecasts,period)
    sources=sorted({r['source_name'] for r in selected})
    selected_sources=st.multiselect('Rapora dahil edilecek anketler',sources,default=sources)
    selected=[r for r in selected if r['source_name'] in selected_sources]
    ids={r['id'] for r in selected}; answers=[r for r in answers if r['poll_id'] in ids]
    st.caption('Her kaynak için bir gözlem kullanılır; aynı dönemden PDF kaydı varsa öncelik ona verilir. Kaynak notları rapora eklenir.')
    if not selected: st.info('En az bir anket seçin.'); return
    source=st.selectbox('Grafik önizlemesi',sorted({r['source_name'] for r in answers if r['target_type']=='monthly_cpi'}),index=0) if answers else None
    chartrows=sorted([r for r in answers if r['source_name']==source and r['target_type']=='monthly_cpi'],key=lambda r:float(r['forecast_value']))
    if chartrows:
        fig=go.Figure()
        for r in chartrows: fig.add_shape(type='line',x0=0,x1=r['forecast_value'],y0=r['participant_name'],y1=r['participant_name'],line=dict(color='#225c90',width=2))
        fig.add_trace(go.Scatter(x=[r['forecast_value'] for r in chartrows],y=[r['participant_name'] for r in chartrows],mode='markers+text',text=[number(r['forecast_value']) for r in chartrows],textposition='middle right',marker=dict(size=9,color='#225c90'),cliponaxis=False))
        fig.update_layout(height=max(350,len(chartrows)*25),xaxis_title='Aylık TÜFE beklentisi (%)',yaxis=dict(autorange='reversed'),showlegend=False,margin=dict(l=10,r=55,t=20,b=40),paper_bgcolor='white',plot_bgcolor='white')
        st.plotly_chart(fig,use_container_width=True)
    pdf=build_pdf(selected,answers,period,report_date)
    st.download_button('Bilgi notunu PDF indir',pdf,f'tufe-beklenti-{period[:7]}.pdf','application/pdf',type='primary')
    st.caption('Yayın tarihleri ve gerçekleşmeler mevcut kayıtlardan alınır; rapor tarihi ayrı tutulur.')
