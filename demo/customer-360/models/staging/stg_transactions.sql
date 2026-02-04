with source as (
    select * from {{ ref('raw_transactions') }}
),
cleaned as (
    select
        txn_id,
        customer_id,
        cast(amount as decimal(10, 2)) as amount,
        product_id,
        cast(txn_date as date) as txn_date,
        case
            when status in ('completed', 'pending', 'refunded', 'cancelled') then status
            else 'unknown'
        end as status,
        {{ current_timestamp() }} as _loaded_at
    from source
    where txn_id is not null
        and customer_id is not null
        and amount > 0
)
select * from cleaned
