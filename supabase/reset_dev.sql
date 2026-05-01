-- GELİŞTİRME / BOŞ PROJE İÇİN SIFIRLAMA SQLİ
-- Dikkat: Bu uygulamanın tablolarındaki verileri siler.

drop view if exists v_revision_history cascade;
drop view if exists v_consensus_analysis cascade;
drop view if exists v_source_scores cascade;
drop view if exists v_participant_profiles cascade;
drop view if exists v_poll_summaries cascade;
drop view if exists v_leaderboard cascade;
drop view if exists v_latest_forecasts cascade;
drop view if exists v_forecasts cascade;

drop table if exists activity_log cascade;
drop table if exists raw_captures cascade;
drop table if exists source_quality_reviews cascade;
drop table if exists actuals cascade;
drop table if exists poll_summaries cascade;
drop table if exists forecasts cascade;
drop table if exists forecast_events cascade;
drop table if exists sources cascade;
drop table if exists participants cascade;

drop type if exists source_type cascade;
drop type if exists participant_type cascade;
drop type if exists target_type cascade;
