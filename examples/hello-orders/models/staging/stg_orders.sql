select
    cast(order_id as integer) as order_id,
    cast(customer_id as varchar) as customer_id,
    cast(order_date as date) as order_date,
    cast(order_total as decimal(18, 2)) as order_total
from {{ ref('orders') }}
