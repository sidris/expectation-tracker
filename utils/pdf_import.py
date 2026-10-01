"""Extract the Turkish CPI survey note format, without guessing missing data."""
import io
import re
import unicodedata
from datetime import date

MONTHS = dict(zip(['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'], range(1,13)))

def normalize(name):
    name = name.replace('ı', 'i').replace('İ', 'I')
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower())

GROUPS = {
    'QNB Türkiye': ['QNB', 'Qnb Bank Tr', 'QNB Türkiye'],
    'Albaraka Türk': ['Al Baraka', 'Albaraka', 'Albaraka Türk'],
    'Garanti BBVA': ['Garanti Bank', 'Garanti Bankası', 'Garanti BBVA Research', 'Garanti BBVA'],
    'Alternatifbank': ['ABank', 'Alternatifbank'],
    'İş Yatırım': ['Is Invest', 'İş Yatırım'],
    'İş Portföy': ['Is Portfoy', 'İş Portföy'],
    'Rota Portföy': ['Rota Portfoy Yonetimi AS', 'Rota Portföy', 'Rota Yatırım'],
    'Yatırım Finansman': ['Yatirim Fin', 'Yatırım Finansman'],
    'Şekerbank': ['Şeker Bank', 'Şekerbank'],
    'HSBC Portföy': ['HSBC Portfolio', 'HSBC Portföy', 'HSBC Hldg'],
    'Ahlatcı Yatırım': ['Ahlatçı Yatırım', 'Ahlatcı Yatırım'],
    'İnfo Yatırım': ['Info Yatırım', 'İnfo Yatırım'],
    'İntegral Yatırım': ['Integral Yatırım', 'İntegral Yatırım'],
    'ALB Yatırım': ['ALB Yatirim'],
    'Gedik Yatırım': ['Gedik Yatirim'],
}
ALIASES = {normalize(alias): canonical for canonical, aliases in GROUPS.items() for alias in [canonical, *aliases]}

def canonical_name(name):
    return ALIASES.get(normalize(name), name.strip())

def number(value):
    return None if value == '-' else float(value.replace(',', '.'))

def parse_pdf(data, filename):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [p.extract_text() or '' for p in pdf.pages]
    text = '\n'.join(pages)
    first = pages[0]
    month = next((m for m in MONTHS if first.startswith(m + ' ')), None)
    stamp = re.search(r'(\d{1,2}) (' + '|'.join(MONTHS) + r') (\d{4})', first)
    if not month or not stamp:
        raise ValueError(f'{filename}: hedef ay veya rapor tarihi okunamadı.')
    day, publication_month, year = stamp.groups()
    published = date(int(year), MONTHS[publication_month], int(day)).isoformat()
    target_year = int(re.search(re.escape(month) + r' (\d{4}) Aylık', first).group(1))
    period = date(target_year, MONTHS[month], 1).isoformat()
    summaries, forecasts, warnings = [], [], []
    kind = None
    source_pattern = r'(Bloomberg HT|Reuters|Matriks|CNBC-e|CNBCE-e|AA Finans|For[Ii]nvest)\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d,.-]+)(?:\s+(\d+|-))?'
    for line in first.splitlines():
        if 'Aylık Enflasyon' in line: kind = 'monthly_cpi'
        elif 'Yıllık Enflasyon' in line: kind = 'annual_cpi'
        elif 'Yıl Sonu Enflasyon' in line: kind = 'year_end_cpi'
        match = re.fullmatch(source_pattern, line.strip())
        if match and kind:
            source, median, maximum, minimum, count = match.groups()
            source = {'CNBCE-e':'CNBC-e', 'ForInvest':'Forinvest'}.get(source, source)
            summaries.append(dict(file=filename, page=1, source_name=source, target_type=kind,
                target_period=f'{target_year}-12-01' if kind == 'year_end_cpi' else period,
                published_at=published, median_value=number(median), max_value=number(maximum),
                min_value=number(minimum), participant_count=int(count) if count and count != '-' else None))
    for index, page in enumerate(pages):
        header = re.search(r'(Reuters|Matriks) Anketi Kurum Bazında', page)
        if not header: continue
        for line in page.splitlines():
            match = re.fullmatch(r'(.+?)\s+(\d+,\d+)', line.strip())
            if match:
                raw, value = match.groups()
                forecasts.append(dict(file=filename, page=index+1, source_name=header.group(1),
                    target_type='monthly_cpi', target_period=period, published_at=published,
                    report_date=published, date_basis='report_date_unverified',
                    original_name=raw, participant_name=canonical_name(raw), forecast_value=number(value)))
    pka = re.search(r'beklentisi (\d+,\d+);.*?yüzde (\d+,\d+).*?ise (\d+,\d+)', text, re.S)
    if pka:
        for target, target_period, value in [('monthly_cpi', period, pka[1]), ('year_end_cpi', f'{target_year}-12-01', pka[2]), ('year_end_cpi', f'{target_year+1}-12-01', pka[3])]:
            summaries.append(dict(file=filename, page=len(pages), source_name='TCMB PKA', target_type=target,
                target_period=target_period, published_at=None, mean_value=number(value),
                notes='PKA yayın tarihi raporda belirtilmiyor; rapor tarihi: ' + published))
    for summary in summaries:
        if summary['target_type'] != 'monthly_cpi' or summary['source_name'] not in ['Reuters','Matriks']: continue
        count = sum(f['source_name'] == summary['source_name'] for f in forecasts)
        if summary['participant_count'] != count:
            warnings.append(f"{filename} {summary['source_name']}: özet katılımcı sayısı {summary['participant_count']}, kurum satırı {count}.")
    if not summaries or not forecasts:
        raise ValueError(f'{filename}: tablolar eksik; taranmış PDF için OCR gerekebilir.')
    return dict(summaries=summaries, forecasts=forecasts, warnings=warnings)
