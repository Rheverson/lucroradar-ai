-- Grão: unidade física de equipamento (ativo da frota), distinta do produto comercial.
select
    u.unit_id,
    u.sku,
    p.product_line,
    p.description as product_description,
    u.serial_number,
    u.acquisition_date,
    u.acquisition_cost,
    u.branch,
    u.retired_at,
    -- depreciação linear em 60 meses: estimativa gerencial, não contábil
    round(u.acquisition_cost / (60 * 30.4375), 4) as est_daily_depreciation
from {{ ref('stg_equipment_units') }} u
join {{ ref('dim_product') }} p on p.sku = u.sku
