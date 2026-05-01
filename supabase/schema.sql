
create extension if not exists pgcrypto;

do $$ begin
  create type target_type as enum ('monthly_cpi','annual_cpi','year_end_cpi','policy_rate','year_end_policy_rate');
exception when duplicate_object then null; end $$;

do $$ begin
  create type participant_type as enum ('person','institution','media_poll');
exception when duplicate_object then null; end $$;

do $$ begin
  create type source_type as enum ('tv','column','report','survey','news','manual','other');
exception when duplicate_object then null; end $$;

create table if not exists participants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type participant_type not null,
  institution_name text,
  title text,
  country text default 'TR',
  notes text,
  is_active boolean default true,
  created_at timestamptz default now(),
  unique(name, type)
);

create table if not exists sources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type source_type not null default 'manual',
  publisher text,
  url text,
  published_at timestamptz,
  captured_at timestamptz default now(),
  notes text
);

create table if not exists forecast_events (
  id uuid primary key default gen_random_uuid(),
  target_period date not null,
  target_type target_type not null,
  created_at timestamptz default now(),
  unique(target_period, target_type)
);

create table if not exists forecasts (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references forecast_events(id) on delete cascade,
  participant_id uuid references participants(id),
  source_id uuid references sources(id),
  forecast_value numeric not null,
  forecast_date date not null default current_date, -- tahminin açıklandığı tarih; tarih aralığı filtrelerinde kullanılır
  confidence text,
  is_latest_for_participant boolean default true,
  raw_text text,
  notes text,
  created_at timestamptz default now()
);

create table if not exists poll_summaries (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references forecast_events(id) on delete cascade,
  source_id uuid references sources(id),
  poll_name text not null,
  participant_count int,
  min_value numeric,
  max_value numeric,
  median_value numeric,
  mean_value numeric,
  year_end_cpi numeric, -- sene sonu enflasyon/TÜFE beklentisi
  monthly_cpi numeric,
  annual_cpi numeric,
  year_end_policy_rate numeric, -- sene sonu PPK/politika faizi beklentisi
  raw_payload jsonb,
  published_at date,
  notes text,
  created_at timestamptz default now()
);

create table if not exists actuals (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references forecast_events(id) on delete cascade,
  actual_value numeric not null,
  released_at date,
  source_url text,
  notes text,
  created_at timestamptz default now(),
  unique(event_id)
);

create or replace view v_forecasts as
select
  f.*,
  e.target_period,
  extract(year from e.target_period)::int as target_year,
  e.target_type,
  to_char(e.target_period, 'YYYY-MM') || ' / ' || e.target_type::text as event_label,
  p.name as participant_name,
  p.type as participant_type,
  s.name as source_name,
  a.actual_value,
  abs(f.forecast_value - a.actual_value) as abs_error,
  (e.target_period - f.forecast_date) as horizon_days
from forecasts f
join forecast_events e on e.id = f.event_id
left join participants p on p.id = f.participant_id
left join sources s on s.id = f.source_id
left join actuals a on a.event_id = f.event_id;

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
having count(*) >= 2;

create index if not exists idx_forecast_events_period_type on forecast_events(target_period, target_type);
create index if not exists idx_forecasts_event_participant_date on forecasts(event_id, participant_id, forecast_date desc);
create index if not exists idx_actuals_event on actuals(event_id);

alter table participants enable row level security;
alter table sources enable row level security;
alter table forecast_events enable row level security;
alter table forecasts enable row level security;
alter table poll_summaries enable row level security;
alter table actuals enable row level security;

-- MVP: authenticated/anon read-write. Prod'da auth.uid bazlı daraltın.
create policy "read participants" on participants for select using (true);
create policy "write participants" on participants for all using (true) with check (true);
create policy "read sources" on sources for select using (true);
create policy "write sources" on sources for all using (true) with check (true);
create policy "read events" on forecast_events for select using (true);
create policy "write events" on forecast_events for all using (true) with check (true);
create policy "read forecasts" on forecasts for select using (true);
create policy "write forecasts" on forecasts for all using (true) with check (true);
create policy "read polls" on poll_summaries for select using (true);
create policy "write polls" on poll_summaries for all using (true) with check (true);
create policy "read actuals" on actuals for select using (true);
create policy "write actuals" on actuals for all using (true) with check (true);

create or replace view v_poll_summaries as
select
  ps.*,
  e.target_period,
  extract(year from e.target_period)::int as target_year,
  e.target_type,
  to_char(e.target_period, 'YYYY-MM') || ' / ' || e.target_type::text as event_label,
  s.name as source_name,
  s.publisher as source_publisher
from poll_summaries ps
join forecast_events e on e.id = ps.event_id
left join sources s on s.id = ps.source_id;

create index if not exists idx_forecasts_forecast_date on forecasts(forecast_date);
create index if not exists idx_poll_summaries_published_at on poll_summaries(published_at);

-- v5: güven skoru, aktivite akışı, otomatik metin çıkarımı ve gelişmiş analizler
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
),
base as (
  select
    vf.*,
    c.consensus_mean,
    c.consensus_median
  from v_forecasts vf
  left join consensus c on c.event_id = vf.event_id
)
select *,
       round((forecast_value - consensus_mean)::numeric, 4) as deviation_from_mean,
       round((forecast_value - consensus_median)::numeric, 4) as deviation_from_median,
       round(abs(forecast_value - consensus_mean)::numeric, 4) as abs_deviation_from_mean
from base;

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
