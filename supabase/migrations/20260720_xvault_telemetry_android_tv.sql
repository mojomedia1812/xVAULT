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
  v_addon_version text;
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
  v_addon_version := left(coalesce(ctx ->> 'addon_version', ''), 32);
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
    v_addon_version,
    v_kodi_version,
    v_os_class,
    v_device_class
  );

  return jsonb_build_object(
    'success', true,
    'installation_created', install_created,
    'event', event_name,
    'online', event_name <> 'app_stop'
  );
end;
$$;

revoke all on function public.xvault_ingest(jsonb) from public;
grant execute on function public.xvault_ingest(jsonb) to anon, authenticated;

-- The existing telemetry schema stores only the normalized class, not raw model
-- values. Android rows still marked as unknown are neither Fire TV, Tablet nor
-- Mobile in the old client logic and are treated as Android TV / TV box.
update public.xvault_installations
set device_class = 'Android TV',
    updated_at = now()
where os_class = 'Android'
  and coalesce(nullif(device_class, ''), 'unknown') = 'unknown';

update public.xvault_sessions
set device_class = 'Android TV',
    updated_at = now()
where os_class = 'Android'
  and coalesce(nullif(device_class, ''), 'unknown') = 'unknown';

update public.xvault_events
set device_class = 'Android TV'
where os_class = 'Android'
  and coalesce(nullif(device_class, ''), 'unknown') = 'unknown';
