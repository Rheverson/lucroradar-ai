select * from {{ ref('stg_orders_all') }} where _invalid_reason is null
