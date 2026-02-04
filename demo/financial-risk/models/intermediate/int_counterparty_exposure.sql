-- int_counterparty_exposure: Per-counterparty exposure metrics

{{ config(
    materialized='table',
    tags=['intermediate']
) }}

with positions as (
    select * from {{ ref('stg_positions') }}
),

counterparties as (
    select * from {{ ref('stg_counterparties') }}
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

-- Assign counterparty based on portfolio_id hash
-- (In real system, would have explicit position->counterparty mapping)
position_counterparty as (
    select
        pv.*,
        'CP' || lpad(cast((abs(hash(pv.portfolio_id)) % 100) + 1 as varchar), 3, '0') as counterparty_id
    from position_values pv
),

exposure_aggregates as (
    select
        pc.counterparty_id,
        sum(pc.position_value) as total_exposure
    from position_counterparty pc
    group by pc.counterparty_id
)

select
    ea.counterparty_id,
    ea.total_exposure,
    c.exposure_limit,
    case
        when c.exposure_limit > 0
        then (ea.total_exposure / c.exposure_limit) * 100
        else 0
    end as utilization_pct
from exposure_aggregates ea
inner join counterparties c
    on ea.counterparty_id = c.counterparty_id
