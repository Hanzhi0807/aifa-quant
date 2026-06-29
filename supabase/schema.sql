-- AIFA Quant cloud dashboard schema.
-- Run this once in the Supabase SQL editor before using scripts/push_to_supabase.py.

create table if not exists public.allowed_emails (
    email text primary key,
    note text,
    created_at timestamptz not null default now()
);

create table if not exists public.daily_signals (
    id bigserial primary key,
    trade_date date not null,
    symbol text not null,
    name text,
    score double precision not null default 0,
    rank integer not null,
    profile text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint daily_signals_trade_symbol_profile_key unique (trade_date, symbol, profile)
);

create table if not exists public.portfolio (
    id bigserial primary key,
    trade_date date not null,
    symbol text not null,
    name text,
    action text not null default 'hold',
    weight double precision not null default 0,
    reason text,
    profile text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint portfolio_trade_symbol_profile_key unique (trade_date, symbol, profile)
);

create index if not exists daily_signals_profile_date_rank_idx
    on public.daily_signals (profile, trade_date desc, rank asc);

create index if not exists portfolio_profile_date_weight_idx
    on public.portfolio (profile, trade_date desc, weight desc);

create or replace function public.is_allowed_dashboard_user()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.allowed_emails
        where lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
    );
$$;

grant execute on function public.is_allowed_dashboard_user() to authenticated;

alter table public.allowed_emails enable row level security;
alter table public.daily_signals enable row level security;
alter table public.portfolio enable row level security;

drop policy if exists daily_signals_select_allowed on public.daily_signals;
create policy daily_signals_select_allowed
on public.daily_signals
for select
to authenticated
using (public.is_allowed_dashboard_user());

drop policy if exists portfolio_select_allowed on public.portfolio;
create policy portfolio_select_allowed
on public.portfolio
for select
to authenticated
using (public.is_allowed_dashboard_user());

-- Service role bypasses RLS for writes. Do not expose SUPABASE_SERVICE_ROLE_KEY in frontend code or Vercel.
-- Add invited readers with:
-- insert into public.allowed_emails (email, note) values ('reader@example.com', 'friend');
