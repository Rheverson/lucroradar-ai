with src as ({{ latest_version('maintenance_orders', 'maintenance_id') }})
select
    btrim(s.maintenance_id) as maintenance_id,
    btrim(s.unit_id) as unit_id,
    lower(btrim(s.maintenance_type)) as maintenance_type,
    util.try_date(s.opened_at) as opened_at,
    util.try_date(s.closed_at) as closed_at,
    s.description,
    util.try_numeric(s.cost_amount) as cost_amount,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when u.unit_id is null then 'unidade física inexistente'
        when util.try_date(s.opened_at) is null then 'data de abertura inválida'
    end as _invalid_reason
from src s
left join {{ ref('stg_equipment_units') }} u on u.unit_id = btrim(s.unit_id)
