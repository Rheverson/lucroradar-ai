with src as ({{ latest_version('equipment_units', 'unit_id') }})
select
    btrim(s.unit_id) as unit_id,
    coalesce(p.canonical_sku, upper(btrim(s.sku))) as sku,
    s.serial_number,
    util.try_date(s.acquisition_date) as acquisition_date,
    util.try_numeric(s.acquisition_cost) as acquisition_cost,
    s.branch,
    util.try_date(s.retired_at) as retired_at,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when p.sku is null then 'produto inexistente'
        when util.try_date(s.acquisition_date) is null then 'data de aquisição inválida'
    end as _invalid_reason
from src s
left join {{ ref('stg_products') }} p on p.sku = upper(btrim(s.sku))
