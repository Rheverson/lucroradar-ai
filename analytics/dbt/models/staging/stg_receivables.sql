select * from {{ ref('stg_receivables_all') }} where _invalid_reason is null
