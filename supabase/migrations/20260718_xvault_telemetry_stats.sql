create or replace function public.xvault_stats_summary()
returns jsonb
language sql
security definer
set search_path = public
as $$
  with
  totals as (
    select
      count(*)::integer as total_installations,
      count(*) filter (where is_online and last_seen >= now() - interval '15 minutes')::integer as online_installations,
      count(*) filter (where is_online)::integer as reported_online_installations,
      count(*) filter (where first_seen >= now() - interval '24 hours')::integer as installations_24h,
      count(*) filter (where first_seen >= now() - interval '7 days')::integer as installations_7d,
      count(*) filter (where first_seen >= now() - interval '30 days')::integer as installations_30d,
      max(last_seen) as last_seen
    from public.xvault_installations
  ),
  session_totals as (
    select
      count(*)::integer as total_sessions,
      count(*) filter (where is_online and last_seen >= now() - interval '15 minutes')::integer as online_sessions,
      count(*) filter (where started_at >= now() - interval '24 hours')::integer as sessions_24h,
      avg(extract(epoch from coalesce(stopped_at, last_seen) - started_at)) filter (
        where coalesce(stopped_at, last_seen) >= started_at
      )::integer as average_session_seconds
    from public.xvault_sessions
  ),
  event_totals as (
    select
      count(*)::integer as total_events,
      count(*) filter (where occurred_at >= now() - interval '24 hours')::integer as events_24h,
      count(*) filter (where event_name = 'heartbeat' and occurred_at >= now() - interval '15 minutes')::integer as heartbeats_15m
    from public.xvault_events
  )
  select jsonb_build_object(
    'generated_at', now(),
    'online_window_minutes', 15,
    'heartbeat_interval_minutes', 10,
    'totals', jsonb_build_object(
      'installations', coalesce((select total_installations from totals), 0),
      'online_installations', coalesce((select online_installations from totals), 0),
      'reported_online_installations', coalesce((select reported_online_installations from totals), 0),
      'installations_24h', coalesce((select installations_24h from totals), 0),
      'installations_7d', coalesce((select installations_7d from totals), 0),
      'installations_30d', coalesce((select installations_30d from totals), 0),
      'sessions', coalesce((select total_sessions from session_totals), 0),
      'online_sessions', coalesce((select online_sessions from session_totals), 0),
      'sessions_24h', coalesce((select sessions_24h from session_totals), 0),
      'average_session_seconds', coalesce((select average_session_seconds from session_totals), 0),
      'events', coalesce((select total_events from event_totals), 0),
      'events_24h', coalesce((select events_24h from event_totals), 0),
      'heartbeats_15m', coalesce((select heartbeats_15m from event_totals), 0),
      'last_seen', (select last_seen from totals)
    ),
    'os_classes', coalesce((
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
      from (
        select coalesce(nullif(os_class, ''), 'unknown') as label, count(*)::integer as value_count
        from public.xvault_installations
        group by 1
      ) grouped
    ), '[]'::jsonb),
    'device_classes', coalesce((
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
      from (
        select coalesce(nullif(device_class, ''), 'unknown') as label, count(*)::integer as value_count
        from public.xvault_installations
        group by 1
      ) grouped
    ), '[]'::jsonb),
    'kodi_versions', coalesce((
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
      from (
        select coalesce(nullif(kodi_version, ''), 'unbekannt') as label, count(*)::integer as value_count
        from public.xvault_installations
        group by 1
      ) grouped
    ), '[]'::jsonb),
    'xvault_versions', coalesce((
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
      from (
        select coalesce(nullif(addon_version, ''), 'unbekannt') as label, count(*)::integer as value_count
        from public.xvault_installations
        group by 1
      ) grouped
    ), '[]'::jsonb),
    'events_by_type', coalesce((
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
      from (
        select event_name as label, count(*)::integer as value_count
        from public.xvault_events
        group by 1
      ) grouped
    ), '[]'::jsonb),
    'daily_activity', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'day', days.day,
          'installations', coalesce(installs.value_count, 0),
          'starts', coalesce(starts.value_count, 0),
          'stops', coalesce(stops.value_count, 0),
          'heartbeats', coalesce(heartbeats.value_count, 0),
          'active_installations', coalesce(active.value_count, 0)
        )
        order by days.day
      )
      from (
        select generate_series((current_date - interval '29 days')::date, current_date, interval '1 day')::date as day
      ) days
      left join (
        select first_seen::date as day, count(*)::integer as value_count
        from public.xvault_installations
        where first_seen >= current_date - interval '29 days'
        group by 1
      ) installs on installs.day = days.day
      left join (
        select occurred_at::date as day, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'app_start' and occurred_at >= current_date - interval '29 days'
        group by 1
      ) starts on starts.day = days.day
      left join (
        select occurred_at::date as day, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'app_stop' and occurred_at >= current_date - interval '29 days'
        group by 1
      ) stops on stops.day = days.day
      left join (
        select occurred_at::date as day, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'heartbeat' and occurred_at >= current_date - interval '29 days'
        group by 1
      ) heartbeats on heartbeats.day = days.day
      left join (
        select occurred_at::date as day, count(distinct install_id_hash)::integer as value_count
        from public.xvault_events
        where occurred_at >= current_date - interval '29 days'
        group by 1
      ) active on active.day = days.day
    ), '[]'::jsonb)
  );
$$;

revoke all on function public.xvault_stats_summary() from public;
grant execute on function public.xvault_stats_summary() to anon, authenticated;
