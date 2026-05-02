-- v10 repair migration: bozuk/eksik view'ları güvenli sırayla yeniden oluşturur.
-- Veri silmez. Sadece view'ları drop/create yapar ve eksik kolon/tabloları tamamlar.

create extension if not exists pgcrypto;

alter table forecasts add column if not exists poll_id uuid references poll_summaries(id) on delete set null;
alter table forecasts add column if not exists source_text text;
alter table forecasts add column if not exists source_url text;
alter table actuals add column if not exists provider text default 'manual';
alter table actuals add column if not exists external_series_code text;
alter table sources add column if not exists reliability_score numeric default 3.0 check (reliability_score >= 0 and reliability_score <= 5);
alter table sources add column if not exists reliability_notes text;
alter table participants add column if not exists profile_url text;
alter table participants add column if not exists expertise text;

create table if not exists source_quality_reviews (
  id uuid primary key default gen_random_uuid(),
  source_id uuid references sources(id) on delete cascade,
  review_date date default current_date,
  accuracy_score numeric check (accuracy_score >= 0 and accuracy_score <= 5),
  speed_score numeric check (speed_score >= 0 and speed_score <= 5),
  transparency_score numeric check (transparency_score >= 0 and transparency_score <= 5),
  notes text,
  created_at timestamptz default now()
);

create table if not exists raw_captures (
  id uuid primary key default gen_random_uuid(),
  source_id uuid references sources(id),
  captured_at timestamptz default now(),
  capture_text text not null,
  parsed_payload jsonb,
  status text default 'new',
  notes text
);

create table if not exists activity_log (
  id uuid primary key default gen_random_uuid(),
  activity_type text not null,
  title text not null,
  details text,
  entity_table text,
  entity_id uuid,
  created_at timestamptz default now()
);

-- actuals event başına tek gerçek değer olacak şekilde düzelt
with ranked as (
  select id, row_number() over (partition by event_id order by created_at desc, id desc) as rn
  from actuals
)
delete from actuals a
using ranked r
where a.id = r.id and r.rn > 1;

alter table actuals drop constraint if exists actuals_event_id_key;
alter table actuals add constraint actuals_event_id_key unique (event_id);

-- Eski/bozuk view'ları bağımlılık sırasına takılmadan sil
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
  percentile_cont(0.5) within group (order by abs_error) as median_abs_error,
  max(target_period) as last_scored_period
from v_latest_forecasts
where actual_value is not null
group by 1,2,3,4
having count(*) >= 1;

create or replace view v_participant_profiles as
select
  p.id participant_id,
  p.name participant_name,
  p.type participant_type,
  p.institution_name,
  p.title,
  p.expertise,
  p.profile_url,
  count(f.id) total_forecasts,
  count(f.id) filter (where a.actual_value is not null) scored_forecasts,
  round(avg(abs(f.forecast_value - a.actual_value)) filter (where a.actual_value is not null), 4) avg_abs_error,
  min(f.forecast_date) first_forecast_date,
  max(f.forecast_date) last_forecast_date
from participants p
left join forecasts f on f.participant_id = p.id
left join actuals a on a.event_id = f.event_id
group by p.id;

create or replace view v_consensus_analysis as
with consensus as (
  select
    vf.event_id,
    avg(vf.forecast_value) as consensus_mean,
    percentile_cont(0.5) within group (order by vf.forecast_value) as consensus_median
  from v_forecasts vf
  group by vf.event_id
)
select
  vf.*,
  c.consensus_mean,
  c.consensus_median,
  round((vf.forecast_value - c.consensus_mean)::numeric, 4) as deviation_from_mean,
  round((vf.forecast_value - c.consensus_median)::numeric, 4) as deviation_from_median,
  round(abs(vf.forecast_value - c.consensus_mean)::numeric, 4) as abs_deviation_from_mean
from v_forecasts vf
left join consensus c on c.event_id = vf.event_id;

create or replace view v_revision_history as
select
  vf.*,
  lag(vf.forecast_value) over (partition by vf.participant_id, vf.event_id order by vf.forecast_date, vf.created_at) previous_value,
  round((vf.forecast_value - lag(vf.forecast_value) over (partition by vf.participant_id, vf.event_id order by vf.forecast_date, vf.created_at))::numeric, 4) revision_delta,
  row_number() over (partition by vf.participant_id, vf.event_id order by vf.forecast_date, vf.created_at) revision_no
from v_forecasts vf;

create or replace view v_source_scores as
select
  s.id source_id,
  s.name source_name,
  s.type source_type,
  s.publisher,
  s.reliability_score,
  count(f.id) forecast_count,
  round(avg(abs(f.forecast_value - a.actual_value)) filter (where a.actual_value is not null), 4) avg_abs_error,
  round(avg(q.accuracy_score), 2) manual_accuracy_score,
  round(avg(q.speed_score), 2) manual_speed_score,
  round(avg(q.transparency_score), 2) manual_transparency_score
from sources s
left join forecasts f on f.source_id = s.id
left join actuals a on a.event_id = f.event_id
left join source_quality_reviews q on q.source_id = s.id
group by s.id;

create index if not exists idx_forecast_events_period_type on forecast_events(target_period, target_type);
create index if not exists idx_forecasts_event_participant_date on forecasts(event_id, participant_id, forecast_date desc);
create index if not exists idx_forecasts_poll_id on forecasts(poll_id);
create index if not exists idx_forecasts_forecast_date on forecasts(forecast_date);
create index if not exists idx_poll_summaries_published_at on poll_summaries(published_at);
create index if not exists idx_actuals_event on actuals(event_id);
