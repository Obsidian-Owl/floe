-- int_portfolio_risk: Per-portfolio risk metrics

{{ config(
    materialized='table',
    tags=['intermediate']
) }}

with positions as (
    select * from {{ ref('stg_positions') }}
),

market_data as (
    select * from {{ ref('stg_market_data') }}
),

latest_prices as (
    select
        instrument_id,
        close_price,
        volatility,
        row_number() over (partition by instrument_id order by date desc) as rn
    from market_data
),

latest_only as (
    select
        instrument_id,
        close_price,
        volatility
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
        m.volatility,
        p.quantity * m.close_price as position_value
    from positions p
    inner join latest_only m
        on p.instrument_id = m.instrument_id
),

portfolio_aggregates as (
    select
        portfolio_id,
        sum(position_value) as total_value,
        avg(volatility) as avg_volatility,
        count(distinct position_id) as position_count,
        max(position_value) as max_position_value
    from position_values
    group by portfolio_id
)

select
    portfolio_id,
    total_value,
    avg_volatility,
    position_count,
    case
        when total_value > 0
        then (max_position_value / total_value) * 100
        else 0
    end as max_single_position_pct
from portfolio_aggregates
