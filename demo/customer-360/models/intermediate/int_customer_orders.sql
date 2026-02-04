with customers as (
    select * from {{ ref('stg_crm_customers') }}
),
transactions as (
    select * from {{ ref('stg_transactions') }}
    where status = 'completed'
),
customer_orders as (
    select
        customer_id,
        count(*) as total_orders,
        sum(amount) as total_spend,
        avg(amount) as avg_order_value,
        min(txn_date) as first_order_date,
        max(txn_date) as last_order_date
    from transactions
    group by customer_id
),
final as (
    select
        c.customer_id,
        c.customer_name,
        c.email,
        c.segment,
        coalesce(co.total_orders, 0) as total_orders,
        coalesce(co.total_spend, 0) as total_spend,
        coalesce(co.avg_order_value, 0) as avg_order_value,
        co.first_order_date,
        co.last_order_date,
        {{ current_timestamp() }} as _loaded_at
    from customers c
    left join customer_orders co on c.customer_id = co.customer_id
)
select * from final
