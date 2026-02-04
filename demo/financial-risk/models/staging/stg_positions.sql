-- stg_positions: Clean positions, validate quantity > 0

{{ config(
    materialized='view',
    tags=['staging']
) }}

with source as (
    select * from {{ ref('raw_positions') }}
),

cleaned as (
    select
        position_id,
        portfolio_id,
        instrument_id,
        cast(quantity as integer) as quantity,
        cast(entry_price as decimal(18, 2)) as entry_price,
        cast(entry_date as date) as entry_date,
        cast(_loaded_at as timestamp) as loaded_at
    from source
    where quantity > 0
)

select * from cleaned
