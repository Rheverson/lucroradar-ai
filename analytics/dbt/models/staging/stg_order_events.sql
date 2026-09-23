select * from {{ ref('stg_order_events_all') }} where _invalid_reason is null
