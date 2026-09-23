select * from {{ ref('stg_direct_costs_all') }} where _invalid_reason is null
