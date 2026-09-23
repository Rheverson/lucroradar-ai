select * from {{ ref('stg_maintenance_orders_all') }} where _invalid_reason is null
