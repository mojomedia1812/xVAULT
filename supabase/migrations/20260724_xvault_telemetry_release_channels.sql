alter table public.xvault_installations
  add column if not exists addon_id text,
  add column if not exists addon_variant text not null default 'stable';

alter table public.xvault_sessions
  add column if not exists addon_id text,
  add column if not exists addon_variant text not null default 'stable';

alter table public.xvault_events
  add column if not exists addon_id text,
  add column if not exists addon_variant text not null default 'stable';

create index if not exists idx_xvault_installations_variant_version
  on public.xvault_installations(addon_variant, addon_version);

create index if not exists idx_xvault_events_variant_version
  on public.xvault_events(addon_variant, addon_version, occurred_at desc);

create index if not exists idx_xvault_events_install_occurred
  on public.xvault_events(install_id_hash, occurred_at desc, id desc);

create or replace function public.xvault_normalize_addon_variant(
  p_addon_id text,
  p_addon_version text,
  p_addon_variant text
)
returns text
language sql
immutable
as $$
  select case
    when left(
      nullif(
        trim(
          regexp_replace(
            regexp_replace(coalesce(p_addon_version, ''), '(?i)^(alpha|alpa)[\s_-]*', ''),
            '(?i)[\s_-]*(alpha|alpa)$',
            ''
          )
        ),
        ''
      ),
      32
    ) = '2026.07.23.3' then 'stable'
    when lower(coalesce(p_addon_id, '')) = 'plugin.video.xvaultalpha' then 'alpha'
    when lower(coalesce(p_addon_id, '')) = 'plugin.video.xvault' then 'stable'
    when lower(coalesce(p_addon_variant, '')) in ('alpha', 'alpa') then 'alpha'
    when lower(coalesce(p_addon_version, '')) like '%alpha%' or lower(coalesce(p_addon_version, '')) like '%alpa%' then 'alpha'
    else 'stable'
  end
$$;

create or replace function public.xvault_normalize_addon_id(
  p_addon_id text,
  p_addon_version text,
  p_addon_variant text
)
returns text
language sql
immutable
as $$
  select case
    when left(
      nullif(
        trim(
          regexp_replace(
            regexp_replace(coalesce(p_addon_version, ''), '(?i)^(alpha|alpa)[\s_-]*', ''),
            '(?i)[\s_-]*(alpha|alpa)$',
            ''
          )
        ),
        ''
      ),
      32
    ) = '2026.07.23.3' then 'plugin.video.xvault'
    when lower(coalesce(p_addon_id, '')) in ('plugin.video.xvault', 'plugin.video.xvaultalpha') then lower(p_addon_id)
    when public.xvault_normalize_addon_variant(p_addon_id, p_addon_version, p_addon_variant) = 'alpha' then 'plugin.video.xvaultalpha'
    else 'plugin.video.xvault'
  end
$$;

create or replace function public.xvault_normalize_addon_version(p_addon_version text)
returns text
language sql
immutable
as $$
  select left(
    nullif(
      trim(
        regexp_replace(
          regexp_replace(coalesce(p_addon_version, ''), '(?i)^(alpha|alpa)[\s_-]*', ''),
          '(?i)[\s_-]*(alpha|alpa)$',
          ''
        )
      ),
      ''
    ),
    32
  )
$$;

create or replace function public.xvault_version_label(p_addon_version text, p_addon_variant text)
returns text
language sql
immutable
as $$
  select case
    when coalesce(p_addon_variant, 'stable') = 'alpha' then 'Alpha ' || coalesce(nullif(public.xvault_normalize_addon_version(p_addon_version), ''), 'unbekannt')
    else coalesce(nullif(public.xvault_normalize_addon_version(p_addon_version), ''), 'unbekannt')
  end
$$;

update public.xvault_installations
set
  addon_id = public.xvault_normalize_addon_id(addon_id, addon_version, addon_variant),
  addon_variant = public.xvault_normalize_addon_variant(addon_id, addon_version, addon_variant),
  addon_version = public.xvault_normalize_addon_version(addon_version),
  updated_at = now();

update public.xvault_sessions
set
  addon_id = public.xvault_normalize_addon_id(addon_id, addon_version, addon_variant),
  addon_variant = public.xvault_normalize_addon_variant(addon_id, addon_version, addon_variant),
  addon_version = public.xvault_normalize_addon_version(addon_version),
  updated_at = now();

update public.xvault_events
set
  addon_id = public.xvault_normalize_addon_id(addon_id, addon_version, addon_variant),
  addon_variant = public.xvault_normalize_addon_variant(addon_id, addon_version, addon_variant),
  addon_version = public.xvault_normalize_addon_version(addon_version);

-- These early 2026.07.23.x builds only existed on the alpha path. They may
-- have been seen before addon_id/addon_variant existed as dedicated columns.
update public.xvault_installations
set addon_id = 'plugin.video.xvaultalpha',
    addon_variant = 'alpha',
    updated_at = now()
where addon_version in ('2026.07.23.4', '2026.07.23.5', '2026.07.23.6');

update public.xvault_sessions
set addon_id = 'plugin.video.xvaultalpha',
    addon_variant = 'alpha',
    updated_at = now()
where addon_version in ('2026.07.23.4', '2026.07.23.5', '2026.07.23.6');

update public.xvault_events
set addon_id = 'plugin.video.xvaultalpha',
    addon_variant = 'alpha'
where addon_version in ('2026.07.23.4', '2026.07.23.5', '2026.07.23.6');

create or replace function public.xvault_ingest(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  raw_install_id text := coalesce(payload ->> 'install_id', '');
  raw_session_id text := coalesce(payload ->> 'session_id', '');
  event_name text := lower(regexp_replace(coalesce(payload ->> 'event', ''), '[^a-z0-9_:-]+', '_', 'g'));
  event_group text := lower(regexp_replace(coalesce(payload ->> 'event_group', 'lifecycle'), '[^a-z0-9_:-]+', '_', 'g'));
  ctx jsonb := coalesce(payload -> 'context', '{}'::jsonb);
  install_hash text;
  session_hash text;
  v_raw_addon_version text;
  v_addon_version text;
  v_addon_id text;
  v_addon_variant text;
  v_kodi_version text;
  v_os_class text;
  v_device_class text;
  v_end_reason text;
  affected_rows integer;
  install_created boolean := false;
  now_ts timestamptz := now();
begin
  if raw_install_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then
    return jsonb_build_object('success', false, 'message', 'invalid_install_id');
  end if;

  if raw_session_id = '' then
    raw_session_id := raw_install_id;
  elsif raw_session_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then
    return jsonb_build_object('success', false, 'message', 'invalid_session_id');
  end if;

  if event_name not in ('installation_created', 'addon_updated', 'app_start', 'app_stop', 'heartbeat') then
    return jsonb_build_object('success', false, 'message', 'event_not_allowed');
  end if;

  install_hash := encode(digest(raw_install_id, 'sha256'), 'hex');
  session_hash := encode(digest(raw_session_id, 'sha256'), 'hex');
  v_raw_addon_version := left(coalesce(ctx ->> 'addon_version', ''), 64);
  v_addon_id := public.xvault_normalize_addon_id(ctx ->> 'addon_id', v_raw_addon_version, ctx ->> 'addon_variant');
  v_addon_variant := public.xvault_normalize_addon_variant(v_addon_id, v_raw_addon_version, ctx ->> 'addon_variant');
  v_addon_version := public.xvault_normalize_addon_version(v_raw_addon_version);
  v_kodi_version := left(coalesce(ctx ->> 'kodi_version', ''), 64);
  v_os_class := case lower(coalesce(ctx ->> 'os_class', ctx ->> 'os_family', ''))
    when 'windows' then 'Windows'
    when 'linux' then 'Linux'
    when 'android' then 'Android'
    when 'fireos' then 'FireOS'
    else 'unknown'
  end;
  v_device_class := case lower(replace(coalesce(ctx ->> 'device_class', ''), '_', ' '))
    when 'fire tv' then 'Fire TV'
    when 'raspberry pi' then 'Raspberry Pi'
    when 'pc' then 'PC'
    when 'tablet' then 'Tablet'
    when 'mobile' then 'Mobile'
    when 'android tv' then 'Android TV'
    when 'google tv' then 'Android TV'
    when 'tv box' then 'Android TV'
    when 'set top box' then 'Android TV'
    else 'unknown'
  end;
  if v_os_class = 'Android' and v_device_class = 'unknown' then
    v_device_class := 'Android TV';
  end if;
  v_end_reason := left(lower(regexp_replace(coalesce(payload ->> 'end_reason', ''), '[^a-z0-9_:-]+', '_', 'g')), 64);
  if v_end_reason = '' then
    v_end_reason := null;
  end if;

  insert into public.xvault_installations (
    install_id_hash,
    first_seen,
    last_seen,
    is_online,
    current_session_id_hash,
    addon_id,
    addon_variant,
    addon_version,
    kodi_version,
    os_class,
    device_class
  )
  values (
    install_hash,
    now_ts,
    now_ts,
    event_name <> 'app_stop',
    session_hash,
    v_addon_id,
    v_addon_variant,
    v_addon_version,
    v_kodi_version,
    v_os_class,
    v_device_class
  )
  on conflict (install_id_hash) do nothing;

  get diagnostics affected_rows = row_count;
  install_created := affected_rows > 0;

  update public.xvault_installations
  set
    last_seen = now_ts,
    is_online = event_name <> 'app_stop',
    current_session_id_hash = session_hash,
    addon_id = v_addon_id,
    addon_variant = v_addon_variant,
    addon_version = coalesce(nullif(v_addon_version, ''), public.xvault_installations.addon_version),
    kodi_version = coalesce(nullif(v_kodi_version, ''), public.xvault_installations.kodi_version),
    os_class = v_os_class,
    device_class = v_device_class,
    updated_at = now_ts
  where install_id_hash = install_hash;

  insert into public.xvault_sessions (
    session_id_hash,
    install_id_hash,
    started_at,
    last_seen,
    is_online,
    addon_id,
    addon_variant,
    addon_version,
    kodi_version,
    os_class,
    device_class
  )
  values (
    session_hash,
    install_hash,
    now_ts,
    now_ts,
    event_name <> 'app_stop',
    v_addon_id,
    v_addon_variant,
    v_addon_version,
    v_kodi_version,
    v_os_class,
    v_device_class
  )
  on conflict (session_id_hash) do update
  set
    last_seen = excluded.last_seen,
    is_online = event_name <> 'app_stop',
    stopped_at = case when event_name = 'app_stop' then now_ts else public.xvault_sessions.stopped_at end,
    end_reason = case when event_name = 'app_stop' then v_end_reason else public.xvault_sessions.end_reason end,
    addon_id = v_addon_id,
    addon_variant = v_addon_variant,
    addon_version = coalesce(nullif(v_addon_version, ''), public.xvault_sessions.addon_version),
    kodi_version = coalesce(nullif(v_kodi_version, ''), public.xvault_sessions.kodi_version),
    os_class = v_os_class,
    device_class = v_device_class,
    updated_at = now_ts;

  insert into public.xvault_events (
    install_id_hash,
    session_id_hash,
    event_name,
    event_group,
    occurred_at,
    addon_id,
    addon_variant,
    addon_version,
    kodi_version,
    os_class,
    device_class
  )
  values (
    install_hash,
    session_hash,
    event_name,
    event_group,
    now_ts,
    v_addon_id,
    v_addon_variant,
    v_addon_version,
    v_kodi_version,
    v_os_class,
    v_device_class
  );

  return jsonb_build_object(
    'success', true,
    'installation_created', install_created,
    'event', event_name,
    'online', event_name <> 'app_stop',
    'addon_variant', v_addon_variant
  );
end;
$$;

revoke all on function public.xvault_ingest(jsonb) from public;
grant execute on function public.xvault_ingest(jsonb) to anon, authenticated;

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
    'xvault_channels', coalesce((
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
      from (
        select case addon_variant when 'alpha' then 'Alpha' else 'Stable' end as label, count(*)::integer as value_count
        from public.xvault_installations
        group by 1
      ) grouped
    ), '[]'::jsonb),
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
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count, 'variant', addon_variant) order by value_count desc, label)
      from (
        select
          public.xvault_version_label(addon_version, addon_variant) as label,
          addon_variant,
          count(*)::integer as value_count
        from public.xvault_installations
        group by 1, 2
      ) grouped
    ), '[]'::jsonb),
    'events_by_type', coalesce((
      select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
      from (
        select event_name as label, count(*)::integer as value_count
        from public.xvault_events
        group by 1
      ) grouped
    ), '[]'::jsonb)
  );
$$;

revoke all on function public.xvault_stats_summary() from public;
grant execute on function public.xvault_stats_summary() to anon, authenticated;

create or replace function public.xvault_local_bucket(p_value timestamptz, p_bucket text)
returns timestamptz
language sql
stable
as $$
  select case lower(coalesce(p_bucket, 'day'))
    when 'hour' then date_trunc('hour', p_value at time zone 'Europe/Berlin') at time zone 'Europe/Berlin'
    when 'week' then date_trunc('week', p_value at time zone 'Europe/Berlin') at time zone 'Europe/Berlin'
    when 'month' then date_trunc('month', p_value at time zone 'Europe/Berlin') at time zone 'Europe/Berlin'
    else date_trunc('day', p_value at time zone 'Europe/Berlin') at time zone 'Europe/Berlin'
  end
$$;

create or replace function public.xvault_stats_summary_period(p_period text default '1m')
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  now_ts timestamptz := now();
  local_now timestamp := now() at time zone 'Europe/Berlin';
  period_key text := lower(coalesce(nullif(p_period, ''), '1m'));
  period_start timestamptz;
  period_end timestamptz;
  bucket_interval interval;
  bucket_name text;
  period_label text;
begin
  if period_key = '24h' then
    period_start := date_trunc('day', local_now) at time zone 'Europe/Berlin';
    period_end := (date_trunc('day', local_now) + interval '1 day') at time zone 'Europe/Berlin';
    bucket_interval := interval '1 hour';
    bucket_name := 'hour';
    period_label := 'Aktueller Tag';
  elsif period_key = '1w' then
    period_start := date_trunc('week', local_now) at time zone 'Europe/Berlin';
    period_end := (date_trunc('week', local_now) + interval '7 days') at time zone 'Europe/Berlin';
    bucket_interval := interval '1 day';
    bucket_name := 'day';
    period_label := 'Aktuelle Woche';
  elsif period_key = '1y' then
    period_start := date_trunc('year', local_now) at time zone 'Europe/Berlin';
    period_end := (date_trunc('year', local_now) + interval '1 year') at time zone 'Europe/Berlin';
    bucket_interval := interval '1 month';
    bucket_name := 'month';
    period_label := 'Aktuelles Jahr';
  elsif period_key = 'all' then
    select coalesce(
      least(
        coalesce((select min(first_seen) from public.xvault_installations), now_ts),
        coalesce((select min(occurred_at) from public.xvault_events), now_ts)
      ),
      now_ts
    ) into period_start;
    period_start := date_trunc('day', period_start at time zone 'Europe/Berlin') at time zone 'Europe/Berlin';
    period_end := (date_trunc('day', local_now) + interval '1 day') at time zone 'Europe/Berlin';
    bucket_interval := interval '1 week';
    bucket_name := 'week';
    period_label := 'Alle Daten';
  else
    period_key := '1m';
    period_start := date_trunc('month', local_now) at time zone 'Europe/Berlin';
    period_end := (date_trunc('month', local_now) + interval '1 month') at time zone 'Europe/Berlin';
    bucket_interval := interval '1 day';
    bucket_name := 'day';
    period_label := 'Aktueller Monat';
  end if;

  return (
    with
    buckets as (
      select generate_series(period_start, period_end - bucket_interval, bucket_interval) as bucket_start
    ),
    totals as (
      select
        count(*)::integer as total_installations,
        count(*) filter (where is_online and last_seen >= now_ts - interval '15 minutes')::integer as online_installations,
        count(*) filter (where is_online)::integer as reported_online_installations,
        count(*) filter (where first_seen >= period_start and first_seen < period_end)::integer as new_installations,
        max(last_seen) as last_seen
      from public.xvault_installations
    ),
    session_totals as (
      select
        count(*)::integer as total_sessions,
        count(*) filter (where is_online and last_seen >= now_ts - interval '15 minutes')::integer as online_sessions,
        count(*) filter (where started_at >= period_start and started_at < period_end)::integer as sessions_started,
        avg(extract(epoch from coalesce(stopped_at, last_seen) - started_at)) filter (
          where coalesce(stopped_at, last_seen) >= started_at
        )::integer as average_session_seconds
      from public.xvault_sessions
    ),
    event_totals as (
      select
        count(*)::integer as total_events,
        count(*) filter (where event_name = 'app_start' and occurred_at >= period_start and occurred_at < period_end)::integer as app_starts,
        count(*) filter (where event_name = 'app_stop' and occurred_at >= period_start and occurred_at < period_end)::integer as app_stops,
        count(*) filter (where event_name = 'heartbeat' and occurred_at >= period_start and occurred_at < period_end)::integer as heartbeats,
        count(*) filter (where event_name = 'heartbeat' and occurred_at >= now_ts - interval '15 minutes')::integer as heartbeats_15m
      from public.xvault_events
    ),
    activity as (
      select
        buckets.bucket_start,
        coalesce(installs.value_count, 0)::integer as installations,
        coalesce(installs.value_count, 0)::integer as new_installations,
        coalesce(active.value_count, 0)::integer as active_installations,
        coalesce(starts.value_count, 0)::integer as starts,
        coalesce(stops.value_count, 0)::integer as stops,
        coalesce(heartbeats.value_count, 0)::integer as heartbeats,
        coalesce(updates.value_count, 0)::integer as updates,
        coalesce(active.value_count, 0)::integer as max_online
      from buckets
      left join (
        select public.xvault_local_bucket(first_seen, bucket_name) as bucket_start, count(*)::integer as value_count
        from public.xvault_installations
        where first_seen >= period_start and first_seen < period_end
        group by 1
      ) installs on installs.bucket_start = buckets.bucket_start
      left join (
        select public.xvault_local_bucket(occurred_at, bucket_name) as bucket_start, count(distinct install_id_hash)::integer as value_count
        from public.xvault_events
        where occurred_at >= period_start and occurred_at < period_end
        group by 1
      ) active on active.bucket_start = buckets.bucket_start
      left join (
        select public.xvault_local_bucket(occurred_at, bucket_name) as bucket_start, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'app_start' and occurred_at >= period_start and occurred_at < period_end
        group by 1
      ) starts on starts.bucket_start = buckets.bucket_start
      left join (
        select public.xvault_local_bucket(occurred_at, bucket_name) as bucket_start, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'app_stop' and occurred_at >= period_start and occurred_at < period_end
        group by 1
      ) stops on stops.bucket_start = buckets.bucket_start
      left join (
        select public.xvault_local_bucket(occurred_at, bucket_name) as bucket_start, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'heartbeat' and occurred_at >= period_start and occurred_at < period_end
        group by 1
      ) heartbeats on heartbeats.bucket_start = buckets.bucket_start
      left join (
        select public.xvault_local_bucket(occurred_at, bucket_name) as bucket_start, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'addon_updated' and occurred_at >= period_start and occurred_at < period_end
        group by 1
      ) updates on updates.bucket_start = buckets.bucket_start
    ),
    history_days as (
      select generate_series(
        coalesce((select min(first_seen)::date from public.xvault_installations), current_date),
        current_date,
        interval '1 day'
      )::date as day
    ),
    full_history as (
      select
        history_days.day,
        coalesce(installs.value_count, 0)::integer as new_installations,
        coalesce(updates.value_count, 0)::integer as updates,
        coalesce(active.value_count, 0)::integer as max_online
      from history_days
      left join (
        select first_seen::date as day, count(*)::integer as value_count
        from public.xvault_installations
        group by 1
      ) installs on installs.day = history_days.day
      left join (
        select occurred_at::date as day, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'addon_updated'
        group by 1
      ) updates on updates.day = history_days.day
      left join (
        select occurred_at::date as day, count(distinct install_id_hash)::integer as value_count
        from public.xvault_events
        where event_name in ('app_start', 'heartbeat')
        group by 1
      ) active on active.day = history_days.day
    ),
    timeline_hours as (
      select generate_series(
        period_start,
        least(period_end - interval '1 hour', public.xvault_local_bucket(now_ts, 'hour')),
        interval '1 hour'
      ) as point_time
      where period_key = '24h'
    ),
    timeline_online_samples as (
      select
        timeline_hours.point_time,
        samples.sample_time
      from timeline_hours
      cross join lateral generate_series(
        timeline_hours.point_time,
        least(timeline_hours.point_time + interval '59 minutes', now_ts),
        interval '1 minute'
      ) as samples(sample_time)
      where timeline_hours.point_time <= now_ts
    ),
    timeline_online as (
      select
        timeline_online_samples.point_time,
        max(coalesce(online.value_count, 0))::integer as value_count
      from timeline_online_samples
      left join lateral (
        select count(distinct events.install_id_hash)::integer as value_count
        from public.xvault_events events
        where events.addon_variant = 'stable'
          and events.event_name in ('app_start', 'heartbeat')
          and events.occurred_at > timeline_online_samples.sample_time - interval '15 minutes'
          and events.occurred_at <= timeline_online_samples.sample_time
      ) online on true
      group by timeline_online_samples.point_time
    ),
    timeline_points as (
      select
        timeline_hours.point_time,
        coalesce(installs.value_count, 0)::integer as new_installations,
        coalesce(updates.value_count, 0)::integer as updates,
        coalesce(online.value_count, 0)::integer as max_online
      from timeline_hours
      left join (
        select public.xvault_local_bucket(first_seen, 'hour') as point_time, count(*)::integer as value_count
        from public.xvault_installations
        where first_seen >= period_start and first_seen < period_end
          and addon_variant = 'stable'
        group by 1
      ) installs on installs.point_time = timeline_hours.point_time
      left join (
        select public.xvault_local_bucket(occurred_at, 'hour') as point_time, count(*)::integer as value_count
        from public.xvault_events
        where event_name = 'addon_updated' and occurred_at >= period_start and occurred_at < period_end
          and addon_variant = 'stable'
        group by 1
      ) updates on updates.point_time = timeline_hours.point_time
      left join timeline_online online on online.point_time = timeline_hours.point_time
    ),
    hourly_samples as (
      select
        extract(hour from occurred_at at time zone 'Europe/Berlin')::integer as hour,
        (occurred_at at time zone 'Europe/Berlin')::date as local_day,
        count(distinct install_id_hash)::integer as online_count
      from public.xvault_events
      where event_name in ('app_start', 'heartbeat')
      group by 1, 2
    ),
    max_online_by_hour as (
      select
        hour,
        lpad(hour::text, 2, '0') || ':00' as label,
        max(online_count)::integer as max_online,
        min(online_count)::integer as min_online,
        round(avg(online_count))::integer as avg_online,
        count(*)::integer as samples
      from hourly_samples
      group by 1
    )
    select jsonb_build_object(
      'generated_at', now_ts,
      'period', period_key,
      'period_label', period_label,
      'period_start', period_start,
      'period_end', period_end,
      'bucket', bucket_name,
      'online_window_minutes', 15,
      'heartbeat_interval_minutes', 10,
      'totals', jsonb_build_object(
        'installations', coalesce((select total_installations from totals), 0),
        'new_installations', coalesce((select new_installations from totals), 0),
        'online_installations', coalesce((select online_installations from totals), 0),
        'reported_online_installations', coalesce((select reported_online_installations from totals), 0),
        'sessions', coalesce((select total_sessions from session_totals), 0),
        'online_sessions', coalesce((select online_sessions from session_totals), 0),
        'sessions_started', coalesce((select sessions_started from session_totals), 0),
        'average_session_seconds', coalesce((select average_session_seconds from session_totals), 0),
        'events', coalesce((select total_events from event_totals), 0),
        'app_starts', coalesce((select app_starts from event_totals), 0),
        'app_stops', coalesce((select app_stops from event_totals), 0),
        'heartbeats', coalesce((select heartbeats from event_totals), 0),
        'heartbeats_15m', coalesce((select heartbeats_15m from event_totals), 0),
        'last_seen', (select last_seen from totals)
      ),
      'xvault_channels', coalesce((
        select jsonb_agg(jsonb_build_object('label', label, 'count', value_count) order by value_count desc, label)
        from (
          select case addon_variant when 'alpha' then 'Alpha' else 'Stable' end as label, count(*)::integer as value_count
          from public.xvault_installations
          group by 1
        ) grouped
      ), '[]'::jsonb),
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
        select jsonb_agg(jsonb_build_object('label', label, 'count', value_count, 'variant', addon_variant) order by value_count desc, label)
        from (
          select
            public.xvault_version_label(addon_version, addon_variant) as label,
            addon_variant,
            count(*)::integer as value_count
          from public.xvault_installations
          group by 1, 2
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
      'activity', coalesce((
        select jsonb_agg(
          jsonb_build_object(
            'bucket_start', bucket_start,
            'label', to_char(bucket_start at time zone 'Europe/Berlin', case when bucket_name = 'hour' then 'YYYY-MM-DD HH24:00' when bucket_name = 'month' then 'YYYY-MM' else 'YYYY-MM-DD' end),
            'installations', installations,
            'new_installations', new_installations,
            'active_installations', active_installations,
            'starts', starts,
            'stops', stops,
            'heartbeats', heartbeats,
            'updates', updates,
            'max_online', max_online
          )
          order by bucket_start
        )
        from activity
      ), '[]'::jsonb),
      'full_history', coalesce((
        select jsonb_agg(
          jsonb_build_object(
            'day', day,
            'new_installations', new_installations,
            'updates', updates,
            'max_online', max_online
          )
          order by day
        )
        from full_history
      ), '[]'::jsonb),
      'timeline_points', coalesce((
        select jsonb_agg(
          jsonb_build_object(
            'point_time', point_time,
            'new_installations', new_installations,
            'updates', updates,
            'max_online', max_online
          )
          order by point_time
        )
        from timeline_points
      ), '[]'::jsonb),
      'max_online_by_hour', coalesce((
        select jsonb_agg(
          jsonb_build_object(
            'hour', hour,
            'label', label,
            'max_online', max_online,
            'min_online', min_online,
            'avg_online', avg_online,
            'samples', samples
          )
          order by hour
        )
        from max_online_by_hour
      ), '[]'::jsonb)
    )
  );
end;
$$;

revoke all on function public.xvault_stats_summary_period(text) from public;
grant execute on function public.xvault_stats_summary_period(text) to anon, authenticated;

create or replace function public.xvault_stats_lifetime_curves()
returns jsonb
language sql
security definer
set search_path = public
as $$
  with
  bounds as (
    select
      coalesce(
        least(
          coalesce((select min(first_seen)::date from public.xvault_installations), current_date),
          coalesce((select min(occurred_at)::date from public.xvault_events), current_date)
        ),
        current_date
      ) as first_day,
      current_date as last_day
  ),
  days as (
    select generate_series(first_day, last_day, interval '1 day')::date as day
    from bounds
  ),
  daily_installations as (
    select first_seen::date as day, count(*)::integer as value_count
    from public.xvault_installations
    group by 1
  ),
  installation_growth as (
    select
      days.day,
      coalesce(daily_installations.value_count, 0)::integer as new_installations,
      sum(coalesce(daily_installations.value_count, 0)) over (order by days.day)::integer as cumulative_installations
    from days
    left join daily_installations on daily_installations.day = days.day
  ),
  installation_versions_by_day as (
    select
      days.day,
      public.xvault_version_label(latest_event.addon_version, latest_event.addon_variant) as addon_version,
      latest_event.addon_variant,
      count(*)::integer as value_count
    from days
    join public.xvault_installations installations
      on installations.first_seen::date <= days.day
    left join lateral (
      select events.addon_version, events.addon_variant
      from public.xvault_events events
      where events.install_id_hash = installations.install_id_hash
        and events.occurred_at < (days.day + interval '1 day')
        and coalesce(nullif(events.addon_version, ''), '') <> ''
      order by events.occurred_at desc, events.id desc
      limit 1
    ) latest_event on true
    group by days.day, public.xvault_version_label(latest_event.addon_version, latest_event.addon_variant), latest_event.addon_variant
  ),
  current_versions as (
    select
      public.xvault_version_label(addon_version, addon_variant) as addon_version,
      addon_variant,
      count(*)::integer as value_count
    from public.xvault_installations
    group by 1, 2
  )
  select jsonb_build_object(
    'generated_at', now(),
    'first_day', (select first_day from bounds),
    'last_day', (select last_day from bounds),
    'installation_growth', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'day', day,
          'new_installations', new_installations,
          'cumulative_installations', cumulative_installations
        )
        order by day
      )
      from installation_growth
    ), '[]'::jsonb),
    'version_history', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'day', day,
          'version', addon_version,
          'variant', addon_variant,
          'count', value_count
        )
        order by day, addon_version
      )
      from installation_versions_by_day
    ), '[]'::jsonb),
    'versions', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'version', addon_version,
          'variant', addon_variant,
          'count', value_count
        )
        order by value_count desc, addon_version desc
      )
      from current_versions
    ), '[]'::jsonb)
  );
$$;

revoke all on function public.xvault_stats_lifetime_curves() from public;
grant execute on function public.xvault_stats_lifetime_curves() to anon, authenticated;
