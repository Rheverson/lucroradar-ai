select * from {{ ref('stg_rental_contract_items_all') }} where _invalid_reason is null
