select * from {{ ref('stg_order_items_all') }} where _invalid_reason is null
