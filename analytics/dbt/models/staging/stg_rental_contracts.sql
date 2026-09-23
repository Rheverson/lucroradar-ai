select * from {{ ref('stg_rental_contracts_all') }} where _invalid_reason is null
