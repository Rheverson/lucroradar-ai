select * from {{ ref('stg_payables_all') }} where _invalid_reason is null
