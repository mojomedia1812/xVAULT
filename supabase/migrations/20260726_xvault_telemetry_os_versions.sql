alter table public.xvault_installations
  add column if not exists os_version text;

alter table public.xvault_sessions
  add column if not exists os_version text;

alter table public.xvault_events
  add column if not exists os_version text;

create index if not exists idx_xvault_installations_os_version
  on public.xvault_installations(os_class, os_version);

create or replace function public.xvault_normalize_os_class(p_os_class text)
returns text
language sql
immutable
as $$
  select case lower(replace(coalesce(p_os_class, ''), '_', ' '))
    when 'windows' then 'Windows'
    when 'linux' then 'Linux'
    when 'android' then 'Android'
    when 'fireos' then 'FireOS'
    when 'fire os' then 'FireOS'
    when 'macos' then 'macOS'
    when 'mac os' then 'macOS'
    when 'osx' then 'macOS'
    when 'ios' then 'iOS'
    when 'tvos' then 'tvOS'
    when 'tv os' then 'tvOS'
    when 'xbox' then 'Xbox'
    else 'unknown'
  end
$$;

create or replace function public.xvault_normalize_device_class(p_device_class text, p_os_class text)
returns text
language sql
immutable
as $$
  select case lower(replace(coalesce(p_device_class, ''), '_', ' '))
    when 'fire tv' then 'Fire TV'
    when 'raspberry pi' then 'Raspberry Pi'
    when 'pc' then 'PC'
    when 'tablet' then 'Tablet'
    when 'mobile' then 'Mobile'
    when 'android tv' then 'Android TV'
    when 'google tv' then 'Android TV'
    when 'tv box' then 'TV Box'
    when 'set top box' then 'TV Box'
    when 'console' then 'Console'
    else case
      when public.xvault_normalize_os_class(p_os_class) = 'Android' then 'Android TV'
      when public.xvault_normalize_os_class(p_os_class) = 'FireOS' then 'Fire TV'
      when public.xvault_normalize_os_class(p_os_class) in ('Windows', 'Linux', 'macOS') then 'PC'
      when public.xvault_normalize_os_class(p_os_class) = 'tvOS' then 'TV Box'
      when public.xvault_normalize_os_class(p_os_class) = 'Xbox' then 'Console'
      else 'unknown'
    end
  end
$$;

create or replace function public.xvault_normalize_os_version(p_os_class text, p_os_version text)
returns text
language sql
immutable
as $$
  select left(
    case
      when nullif(trim(coalesce(p_os_version, '')), '') is null then ''
      when lower(trim(p_os_version)) in ('unknown', 'unbekannt') then 'unbekannt'
      when public.xvault_normalize_os_class(p_os_class) = 'FireOS'
        and lower(trim(p_os_version)) like 'fire os %' then trim(p_os_version)
      when public.xvault_normalize_os_class(p_os_class) = 'FireOS'
        and lower(trim(p_os_version)) like '%vega%' then 'Vega OS'
      when public.xvault_normalize_os_class(p_os_class) = 'FireOS'
        and trim(p_os_version) ~ '^[0-9]+$' then 'Fire OS ' || trim(p_os_version)
      when public.xvault_normalize_os_class(p_os_class) = 'Android'
        and lower(trim(p_os_version)) not like 'android%' then 'Android ' || trim(p_os_version)
      when public.xvault_normalize_os_class(p_os_class) = 'Windows'
        and lower(trim(p_os_version)) not like 'windows%' then 'Windows ' || trim(p_os_version)
      else trim(p_os_version)
    end,
    64
  )
$$;

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
  v_os_version text;
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
  v_os_class := public.xvault_normalize_os_class(coalesce(ctx ->> 'os_class', ctx ->> 'os_family', ''));
  v_os_version := public.xvault_normalize_os_version(v_os_class, ctx ->> 'os_version');
  v_device_class := public.xvault_normalize_device_class(ctx ->> 'device_class', v_os_class);
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
    os_version,
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
    v_os_version,
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
    os_version = coalesce(nullif(v_os_version, ''), public.xvault_installations.os_version),
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
    os_version,
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
    v_os_version,
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
    os_version = coalesce(nullif(v_os_version, ''), public.xvault_sessions.os_version),
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
    os_version,
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
    v_os_version,
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

create or replace function public.xvault_stats_os_versions()
returns jsonb
language sql
security definer
set search_path = public
as $$
  select jsonb_build_object(
    'generated_at', now(),
    'os_versions', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'os_class', os_class_label,
          'label', os_version_label,
          'count', value_count
        )
        order by os_class_label, value_count desc, os_version_label
      )
      from (
        select
          coalesce(nullif(os_class, ''), 'unknown') as os_class_label,
          coalesce(nullif(os_version, ''), 'Noch nicht gemeldet') as os_version_label,
          count(*)::integer as value_count
        from public.xvault_installations
        group by 1, 2
      ) grouped
    ), '[]'::jsonb)
  )
$$;

revoke all on function public.xvault_stats_os_versions() from public;
grant execute on function public.xvault_stats_os_versions() to anon, authenticated;
