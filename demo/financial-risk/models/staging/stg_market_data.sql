-- stg_market_data: Clean market data, compute daily returns

{{ config(
    materialized='view',
    tags=['staging']
) }}

with source as (
    select * from {{ ref('raw_market_data') }}
),

cleaned as (
    select
        instrument_id,
        cast(date as date) as date,
        cast(close_price as decimal(18, 2)) as close_price,
        cast(volume as bigint) as volume,
        cast(volatility as decimal(10, 4)) as volatility,
        cast(_loaded_at as timestamp) as loaded_at
    from source
),

with_returns as (
    select
        *,
        lag(close_price) over (partition by instrument_id order by date) as prev_close_price,
        case
            when lag(close_price) over (partition by instrument_id order by date) is not null
                and lag(close_price) over (partition by instrument_id order by date) > 0
            then (close_price - lag(close_price) over (partition by instrument_id order by date))
                 / lag(close_price) over (partition by instrument_id order by date)
            else null
        end as daily_return
    from cleaned
)

select
    instrument_id,
    date,
    close_price,
    volume,
    volatility,
    daily_return,
    loaded_at
from with_returns
