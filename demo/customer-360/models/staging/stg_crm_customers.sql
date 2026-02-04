with source as (
    select * from {{ ref('raw_customers') }}
),
cleaned as (
    select
        customer_id,
        trim(name) as customer_name,
        lower(trim(email)) as email,
        cast(signup_date as date) as signup_date,
        case
            when segment in ('enterprise', 'mid_market', 'smb', 'startup') then segment
            else 'unknown'
        end as segment,
        {{ current_timestamp() }} as _loaded_at
    from source
    where customer_id is not null
)
select * from cleaned
