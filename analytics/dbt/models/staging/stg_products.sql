select * from {{ ref('stg_products_all') }} where _invalid_reason is null
