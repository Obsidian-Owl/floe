select
    order_date,
    count(*) as order_count,
    sum(order_total) as total_order_value
from {{ ref('stg_orders') }}
group by order_date
