-- stg_counterparties: Clean counterparty records, validate rating

{{ config(
    materialized='view',
    tags=['staging']
) }}

with source as (
    select * from {{ ref('raw_counterparties') }}
),

cleaned as (
    select
        counterparty_id,
        name,
        rating,
        country,
        cast(exposure_limit as bigint) as exposure_limit,
        cast(_loaded_at as timestamp) as loaded_at
    from source
    where rating in ('AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC')
)

select * from cleaned
