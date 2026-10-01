"""Resumable survey import; existing conflicting values are never overwritten."""
from utils.db import fetch, insert
from utils.domain import ensure_event
from utils.pdf_import import canonical_name, normalize
from datetime import date
import math

def import_surveys(payload):
    counts = {'summaries': 0, 'forecasts': 0, 'skipped': 0}
    participants = fetch('participants')
    sources = fetch('sources')
    for row in payload['summaries'] + payload['forecasts']:
        date.fromisoformat(row['target_period'])
        if row.get('published_at'): date.fromisoformat(row['published_at'])
        for key in ['forecast_value','median_value','mean_value','min_value','max_value']:
            if row.get(key) is not None and not math.isfinite(float(row[key])):
                raise ValueError('Tahminler sonlu sayılar olmalı.')
        if 'participant_name' in row and (not row['participant_name'].strip() or row.get('forecast_value') is None):
            raise ValueError('Kurum adı ve tahmin değeri boş olamaz.')
        if row.get('min_value') is not None and row.get('max_value') is not None and row['min_value'] > row['max_value']:
            raise ValueError('En düşük değer en yüksek değeri aşamaz.')
    for row in payload['summaries']:
        if not row.get('published_at') and row['source_name'] != 'TCMB PKA':
            raise ValueError('PKA dışındaki özetlerin yayın tarihi girilmeli.')
    def resolve(table, name, existing, institution=False):
        matches = [r for r in existing if (not institution or r['type'] == 'institution') and
                   normalize(canonical_name(r['name']) if institution else r['name']) == normalize(name)]
        if len(matches) > 1:
            raise ValueError(f'{name}: veritabanında birden fazla eşleşme var; önce kayıtları düzenleyin.')
        if matches: return matches[0]['id']
        created = insert(table, {'name': name, 'type': 'institution' if institution else 'survey'})[0]
        existing.append(created)
        return created['id']
    for name in {r['participant_name'] for r in payload['forecasts']}:
        matches = [r for r in participants if r['type'] == 'institution' and normalize(canonical_name(r['name'])) == normalize(name)]
        if len(matches) > 1: raise ValueError(f'{name}: birden fazla kurum kaydı eşleşiyor.')
    for row in payload['summaries']:
        event = ensure_event(row['target_period'], row['target_type'])
        source = resolve('sources', row['source_name'], sources)
        key = dict(event_id=event, source_id=source, published_at=row['published_at'],
                   poll_name=f"{row['source_name']} beklenti anketi [PDF: {row['file']}]")
        values = {k: row.get(k) for k in ['median_value','mean_value','min_value','max_value','participant_count']}
        if values['participant_count'] is not None:
            count = float(values['participant_count'])
            if not math.isfinite(count) or not count.is_integer() or count < 0:
                raise ValueError('Katılımcı sayısı negatif olmayan tam sayı olmalı.')
            values['participant_count'] = int(count)
        import_notes = row.get('notes','')
        def differences(p):
            return {k: {'existing': p.get(k), 'pdf': v} for k,v in values.items()
                    if v is not None and (float(p[k]) if p.get(k) is not None else None) != v}
        old = fetch('poll_summaries', filters=key)
        if not old and row.get('published_at'):
            candidates = fetch('poll_summaries', filters=dict(event_id=event, source_id=source))
            if row['target_type'] in ['year_end_cpi', 'year_end_policy_rate']:
                candidates = [p for p in candidates if p.get('published_at') and
                    0 <= (date.fromisoformat(row['published_at'])-date.fromisoformat(p['published_at'])).days <= 7]
            if len(candidates) > 1:
                raise ValueError(f"{row['source_name']} {row['target_period']}: birden fazla anket var; tarih eşleştirmesi gerekli.")
            if candidates and not differences(candidates[0]):
                old = candidates
            elif candidates:
                import_notes += f" Mevcut anket {candidates[0]['id']} ile değer farkı; PDF ayrı kaynak gözlemi olarak saklandı. Farklar: {differences(candidates[0])}"
        if len(old)>1: raise ValueError('Aynı anket birden fazla kayıtla eşleşiyor.')
        if old:
            if differences(old[0]):
                raise ValueError(f"{row['file']} {row['source_name']}: mevcut özet farklı; üzerine yazılmadı.")
            poll = old[0]
            counts['skipped'] += 1
        else:
            poll = insert('poll_summaries', dict(**key, **values, notes=import_notes, raw_payload=row))[0]
            counts['summaries'] += 1
        for f in payload['forecasts']:
            if any(f[k] != row[k] for k in ['file','source_name','target_type','target_period']): continue
            pid = resolve('participants', f['participant_name'], participants, True)
            forecast_key = dict(poll_id=poll['id'], participant_id=pid)
            existing = fetch('forecasts', filters=forecast_key)
            if existing:
                if len(existing)>1 or float(existing[0]['forecast_value']) != f['forecast_value']:
                    raise ValueError(f"{f['participant_name']}: mevcut tahmin farklı; üzerine yazılmadı.")
                counts['skipped'] += 1
                continue
            insert('forecasts', dict(**forecast_key, event_id=event, source_id=source,
                   forecast_date=poll['published_at'], forecast_value=f['forecast_value'],
                   source_text=f['file'], raw_text=f['original_name'], notes=f"PDF sayfa {f['page']}; rapor tarihi: {f.get('report_date', f['published_at'])}; tahmin tarihi mevcut anketten veya rapordan alındı, özgün kurum açıklamasıyla doğrulanmadı. Kaynak değerinde hata olabilir."))
            counts['forecasts'] += 1
    return counts
