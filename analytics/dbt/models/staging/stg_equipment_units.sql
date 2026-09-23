select * from {{ ref('stg_equipment_units_all') }} where _invalid_reason is null
