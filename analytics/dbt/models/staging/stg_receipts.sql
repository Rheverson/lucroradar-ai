select * from {{ ref('stg_receipts_all') }} where _invalid_reason is null
