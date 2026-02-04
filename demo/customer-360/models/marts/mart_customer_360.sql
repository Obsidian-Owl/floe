with customers as (
    select * from {{ ref('stg_crm_customers') }}
),
orders as (
    select * from {{ ref('int_customer_orders') }}
),
support as (
    select * from {{ ref('int_customer_support') }}
),
final as (
    select
        c.customer_id,
        c.customer_name,
        c.email,
        c.segment,
        c.signup_date,
        o.total_orders,
        o.total_spend,
        o.avg_order_value,
        o.first_order_date,
        o.last_order_date,
        s.ticket_count,
        s.avg_resolution_hours,
        s.open_tickets,
        (current_date - c.signup_date) as customer_lifetime_days,
        {{ current_timestamp() }} as _loaded_at
    from customers c
    left join orders o on c.customer_id = o.customer_id
    left join support s on c.customer_id = s.customer_id
)
select * from final
