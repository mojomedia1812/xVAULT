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
      coalesce(nullif(latest_event.addon_version, ''), 'unbekannt') as addon_version,
      count(*)::integer as value_count
    from days
    join public.xvault_installations installations
      on installations.first_seen::date <= days.day
    left join lateral (
      select events.addon_version
      from public.xvault_events events
      where events.install_id_hash = installations.install_id_hash
        and events.occurred_at < (days.day + interval '1 day')
        and coalesce(nullif(events.addon_version, ''), '') <> ''
      order by events.occurred_at desc, events.id desc
      limit 1
    ) latest_event on true
    group by days.day, coalesce(nullif(latest_event.addon_version, ''), 'unbekannt')
  ),
  current_versions as (
    select
      coalesce(nullif(addon_version, ''), 'unbekannt') as addon_version,
      count(*)::integer as value_count
    from public.xvault_installations
    group by 1
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
