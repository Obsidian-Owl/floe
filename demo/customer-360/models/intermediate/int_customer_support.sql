with customers as (
    select * from {{ ref('stg_crm_customers') }}
),
tickets as (
    select * from {{ ref('stg_support_tickets') }}
),
customer_support as (
    select
        customer_id,
        count(*) as ticket_count,
        avg(resolution_hours) as avg_resolution_hours,
        sum(case when resolved_at is null then 1 else 0 end) as open_tickets
    from tickets
    group by customer_id
),
final as (
    select
        c.customer_id,
        c.customer_name,
        c.email,
        c.segment,
        coalesce(cs.ticket_count, 0) as ticket_count,
        cs.avg_resolution_hours,
        coalesce(cs.open_tickets, 0) as open_tickets,
        {{ current_timestamp() }} as _loaded_at
    from customers c
    left join customer_support cs on c.customer_id = cs.customer_id
)
select * from final
