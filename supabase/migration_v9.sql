-- v9 migration: mevcut veriyi silmeden EVDS fix, anket-kurum bağlantısı ve revizyon view'lerini günceller.

alter table forecasts add column if not exists poll_id uuid references poll_summaries(id) on delete set null;
alter table forecasts add column if not exists source_text text;
alter table forecasts add column if not exists source_url text;
alter table actuals add column if not exists provider text default 'manual';
alter table actuals add column if not exists external_series_code text;

-- actuals tablosunda event_id başına tek gerçekleşme kalmalı. Önce olası mükerrerleri temizle.
with ranked as (
  select id, row_number() over (partition by event_id order by created_at desc, id desc) as rn
  from actuals
)
delete from actuals a
using ranked r
where a.id = r.id and r.rn > 1;

alter table actuals drop constraint if exists actuals_event_id_key;
alter table actuals add constraint actuals_event_id_key unique (event_id);

create index if not exists idx_forecasts_poll_id on forecasts(poll_id);
create index if not exists idx_forecasts_forecast_date on forecasts(forecast_date);
create index if not exists idx_poll_summaries_published_at on poll_summaries(published_at);

create or replace view v_forecasts as
select
  f.*,
  e.target_period,
  extract(year from e.target_period)::int as target_year,
  extract(month from e.target_period)::int as target_month,
  e.target_type,
  to_char(e.target_period, 'YYYY-MM') || ' / ' || e.target_type::text as event_label,
  p.name as participant_name,
  p.type as participant_type,
  s.name as source_name,
  ps.poll_name,
  a.actual_value,
  abs(f.forecast_value - a.actual_value) as abs_error,
  (e.target_period - f.forecast_date) as horizon_days
from forecasts f
join forecast_events e on e.id = f.event_id
left join participants p on p.id = f.participant_id
left join sources s on s.id = f.source_id
left join poll_summaries ps on ps.id = f.poll_id
left join actuals a on a.event_id = f.event_id;

create or replace view v_poll_summaries as
select
  ps.*,
  e.target_period,
  extract(year from e.target_period)::int as target_year,
  extract(month from e.target_period)::int as target_month,
  e.target_type,
  to_char(e.target_period, 'YYYY-MM') || ' / ' || e.target_type::text as event_label,
  s.name as source_name,
  s.publisher as source_publisher
from poll_summaries ps
join forecast_events e on e.id = ps.event_id
left join sources s on s.id = ps.source_id;

create or replace view v_latest_forecasts as
select distinct on (event_id, participant_id)
  *
from v_forecasts
where participant_id is not null
order by event_id, participant_id, forecast_date desc, created_at desc;

create or replace view v_revision_history as
select
  vf.*,
  lag(vf.forecast_value) over (partition by vf.participant_id, vf.event_id order by vf.forecast_date, vf.created_at) previous_value,
  round((vf.forecast_value - lag(vf.forecast_value) over (partition by vf.participant_id, vf.event_id order by vf.forecast_date, vf.created_at))::numeric, 4) revision_delta,
  row_number() over (partition by vf.participant_id, vf.event_id order by vf.forecast_date, vf.created_at) revision_no
from v_forecasts vf;

create or replace view v_leaderboard as
select
  participant_id,
  participant_name,
  participant_type,
  target_type,
  count(*) filter (where actual_value is not null) as scored_count,
  avg(abs_error) as mean_abs_error,
  percentile_cont(0.5) within group (order by abs_error) as median_abs_error,
  max(target_period) as last_scored_period
from v_latest_forecasts
where actual_value is not null
group by 1,2,3,4
having count(*) >= 2;
