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
        cast(created_at as timestamp) as created_at,
        case
            when resolved_at is not null and resolved_at != ''
            then cast(resolved_at as timestamp)
            else null
        end as resolved_at,
        case
            when resolved_at is not null and resolved_at != ''
            then extract(epoch from (cast(resolved_at as timestamp) - cast(created_at as timestamp))) / 3600.0
            else null
        end as resolution_hours,
        {{ current_timestamp() }} as _loaded_at
    from source
    where ticket_id is not null
        and customer_id is not null
)
select * from cleaned
