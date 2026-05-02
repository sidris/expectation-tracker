-- v12 safe migration: Poll edit ekranı için gerekli küçük tamamlamalar.
-- Veri silmez. Tablo drop/truncate yoktur.

alter table forecasts add column if not exists poll_id uuid references poll_summaries(id) on delete set null;
alter table forecasts add column if not exists source_text text;
alter table forecasts add column if not exists source_url text;

create index if not exists idx_forecasts_poll_id on forecasts(poll_id);
create index if not exists idx_forecasts_poll_participant on forecasts(poll_id, participant_id);
create index if not exists idx_poll_summaries_event_id on poll_summaries(event_id);
create index if not exists idx_poll_summaries_source_id on poll_summaries(source_id);

-- View'ları veri silmeden güvenli şekilde yenile.
drop view if exists v_source_scores cascade;
drop view if exists v_revision_history cascade;
drop view if exists v_consensus_analysis cascade;
drop view if exists v_participant_profiles cascade;
drop view if exists v_poll_summaries cascade;
drop view if exists v_leaderboard cascade;
drop view if exists v_latest_forecasts cascade;
drop view if exists v_forecasts cascade;

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
  s.publisher as source_publisher,
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

create or replace view v_leaderboard as
select
  participant_id,
  participant_name,
  participant_type,
  target_type,
  count(*) filter (where actual_value is not null) as scored_count,
  avg(abs_error) as mean_abs_error,
  min(abs_error) as best_abs_error
from v_latest_forecasts
where actual_value is not null
  and participant_id is not null
group by participant_id, participant_name, participant_type, target_type;

create or replace view v_participant_profiles as
select
  p.id participant_id,
  p.name participant_name,
  p.type participant_type,
  count(f.id) forecast_count,
  count(distinct f.event_id) event_count,
  avg(abs(f.forecast_value - a.actual_value)) avg_abs_error,
  min(abs(f.forecast_value - a.actual_value)) best_error,
  max(f.forecast_date) last_forecast_date
from participants p
left join forecasts f on f.participant_id = p.id
left join actuals a on a.event_id = f.event_id
group by p.id, p.name, p.type;

create or replace view v_revision_history as
select
  vf.*,
  row_number() over (partition by participant_id, event_id order by forecast_date, created_at) as revision_no,
  lag(forecast_value) over (partition by participant_id, event_id order by forecast_date, created_at) as previous_forecast,
  forecast_value - lag(forecast_value) over (partition by participant_id, event_id order by forecast_date, created_at) as revision_delta
from v_forecasts vf
where participant_id is not null;

create or replace view v_consensus_analysis as
with base as (
  select * from v_latest_forecasts where participant_id is not null
), medians as (
  select
    event_id,
    percentile_cont(0.5) within group (order by forecast_value) as consensus_median,
    avg(forecast_value) as consensus_mean,
    min(forecast_value) as consensus_min,
    max(forecast_value) as consensus_max,
    count(*) as consensus_count
  from base
  group by event_id
)
select
  b.*,
  m.consensus_median,
  m.consensus_mean,
  m.consensus_min,
  m.consensus_max,
  m.consensus_count,
  b.forecast_value - m.consensus_median as deviation_from_median
from base b
join medians m on m.event_id = b.event_id;

create or replace view v_source_scores as
select
  s.id source_id,
  s.name source_name,
  s.type source_type,
  coalesce(s.reliability_score, 3.0) base_reliability_score,
  count(f.id) forecast_count,
  count(f.id) filter (where a.actual_value is not null) scored_count,
  avg(abs(f.forecast_value - a.actual_value)) avg_abs_error,
  case
    when count(f.id) filter (where a.actual_value is not null) = 0 then coalesce(s.reliability_score, 3.0)
    else greatest(0, least(5, 5 - avg(abs(f.forecast_value - a.actual_value))))
  end calculated_score
from sources s
left join forecasts f on f.source_id = s.id
left join actuals a on a.event_id = f.event_id
group by s.id, s.name, s.type, s.reliability_score;
