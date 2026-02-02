-- mart_risk_dashboard: Cross-portfolio risk summary

{{ config(
    materialized='table',
    tags=['marts']
) }}

with portfolio_risk as (
    select * from {{ ref('int_portfolio_risk') }}
),

counterparty_exposure as (
    select * from {{ ref('int_counterparty_exposure') }}
),

counterparties as (
    select * from {{ ref('stg_counterparties') }}
),

positions as (
    select * from {{ ref('stg_positions') }}
),

market_data as (
    select * from {{ ref('stg_market_data') }}
),

latest_prices as (
    select
        instrument_id,
        close_price,
        row_number() over (partition by instrument_id order by date desc) as rn
    from market_data
),

latest_only as (
    select
        instrument_id,
        close_price
    from latest_prices
    where rn = 1
),

position_values as (
    select
        p.portfolio_id,
        p.position_id,
        p.instrument_id,
        p.quantity,
        m.close_price,
        p.quantity * m.close_price as position_value
    from positions p
    inner join latest_only m
        on p.instrument_id = m.instrument_id
),

-- Assign counterparty based on portfolio_id hash (same logic as int_counterparty_exposure)
position_counterparty as (
    select
        pv.*,
        'CP' || lpad(cast((abs(hash(pv.portfolio_id)) % 100) + 1 as varchar), 3, '0') as counterparty_id
    from position_values pv
),

portfolio_top_counterparty as (
    select
        pc.portfolio_id,
        pc.counterparty_id,
        sum(pc.position_value) as counterparty_exposure,
        row_number() over (partition by pc.portfolio_id order by sum(pc.position_value) desc) as rn
    from position_counterparty pc
    group by pc.portfolio_id, pc.counterparty_id
),

portfolio_top_only as (
    select
        portfolio_id,
        counterparty_id,
        counterparty_exposure
    from portfolio_top_counterparty
    where rn = 1
)

select
    pr.portfolio_id,
    pr.total_value,
    pr.avg_volatility,
    pr.position_count,
    pr.max_single_position_pct,
    pto.counterparty_id as top_counterparty,
    pto.counterparty_exposure as top_counterparty_exposure,
    ce.utilization_pct as counterparty_utilization_pct
from portfolio_risk pr
left join portfolio_top_only pto
    on pr.portfolio_id = pto.portfolio_id
left join counterparty_exposure ce
    on pto.counterparty_id = ce.counterparty_id
