-- Grão: ordem de manutenção válida. Abertas na referência têm custo ainda desconhecido (NULL).
with ds as (select * from {{ ref('stg_dataset') }})
select
    m.maintenance_id,
    m.unit_id,
    u.sku,
    u.product_line,
    m.maintenance_type,
    m.opened_at,
    m.closed_at,
    (m.closed_at is null) as is_open,
    coalesce(m.closed_at, ds.reference_date) - m.opened_at as days_in_maintenance,
    m.description,
    m.cost_amount
from {{ ref('stg_maintenance_orders') }} m
join {{ ref('dim_equipment_unit') }} u using (unit_id)
cross join ds
where coalesce(m.closed_at, ds.reference_end_exclusive) > ds.window_start
