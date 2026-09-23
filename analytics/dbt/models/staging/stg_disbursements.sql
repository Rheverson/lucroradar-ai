select * from {{ ref('stg_disbursements_all') }} where _invalid_reason is null
