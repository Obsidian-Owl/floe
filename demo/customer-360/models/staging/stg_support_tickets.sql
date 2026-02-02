with source as (
    select * from {{ ref('raw_support_tickets') }}
),
cleaned as (
    select
        ticket_id,
        customer_id,
        case
            when category in ('billing', 'technical', 'account', 'shipping', 'general') then category
            else 'unknown'
        end as category,
        case
            when priority in ('low', 'medium', 'high', 'critical') then priority
            else 'medium'
        end as priority,
        created_at,
        resolved_at,
        case
            when resolved_at is not null
            then extract(epoch from (resolved_at - created_at)) / 3600.0
            else null
        end as resolution_hours,
        {{ current_timestamp() }} as _loaded_at
    from source
    where ticket_id is not null
        and customer_id is not null
)
select * from cleaned
