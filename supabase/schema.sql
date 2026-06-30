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
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_daily_signals_updated_at on public.daily_signals;
create trigger set_daily_signals_updated_at
before update on public.daily_signals
for each row execute function public.set_updated_at();

drop trigger if exists set_portfolio_updated_at on public.portfolio;
create trigger set_portfolio_updated_at
before update on public.portfolio
for each row execute function public.set_updated_at();

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

-- ----------------------------------------------------------------------------
-- Round-3 additions: per-stock SHAP, run metadata, risk exposure, metrics.
-- ----------------------------------------------------------------------------

create table if not exists public.stock_shap (
    id bigserial primary key,
    symbol text not null,
    feature text not null,
    shap_value double precision not null,
    prediction_date date not null,
    profile text not null default 'balanced',
    created_at timestamptz not null default now()
);

create index if not exists stock_shap_symbol_profile_idx
    on public.stock_shap (symbol, profile, prediction_date desc);

create table if not exists public.signal_runs (
    id bigserial primary key,
    run_date date not null,
    model_version text,
    profile text,
    status text default 'success',
    metrics jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.portfolio_risk (
    id bigserial primary key,
    profile text not null,
    calc_date date not null,
    industry_concentration jsonb,
    market_cap_quantile jsonb,
    beta double precision,
    style_exposures jsonb,
    industry_cap_breach boolean default false,
    industry_cap_threshold double precision default 0.25,
    created_at timestamptz not null default now(),
    constraint portfolio_risk_profile_date_key unique (profile, calc_date)
);

create table if not exists public.paper_metrics (
    id bigserial primary key,
    profile text not null,
    calc_date date not null,
    cumulative_return double precision,
    annual_return double precision,
    max_drawdown double precision,
    sharpe double precision,
    monthly_turnover double precision,
    backtest_method text,
    pbo double precision,
    oos_rank_ic double precision,
    created_at timestamptz not null default now(),
    constraint paper_metrics_profile_date_key unique (profile, calc_date)
);

alter table public.stock_shap enable row level security;
alter table public.signal_runs enable row level security;
alter table public.portfolio_risk enable row level security;
alter table public.paper_metrics enable row level security;

drop policy if exists stock_shap_select_allowed on public.stock_shap;
create policy stock_shap_select_allowed
on public.stock_shap for select to authenticated
using (public.is_allowed_dashboard_user());

drop policy if exists signal_runs_select_allowed on public.signal_runs;
create policy signal_runs_select_allowed
on public.signal_runs for select to authenticated
using (public.is_allowed_dashboard_user());

drop policy if exists portfolio_risk_select_allowed on public.portfolio_risk;
create policy portfolio_risk_select_allowed
on public.portfolio_risk for select to authenticated
using (public.is_allowed_dashboard_user());

drop policy if exists paper_metrics_select_allowed on public.paper_metrics;
create policy paper_metrics_select_allowed
on public.paper_metrics for select to authenticated
using (public.is_allowed_dashboard_user());

