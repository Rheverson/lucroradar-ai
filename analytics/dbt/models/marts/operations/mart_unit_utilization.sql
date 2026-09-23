-- Grão: unidade física (período inteiro da janela e últimos 90 dias).
with ds as (select * from {{ ref('stg_dataset') }})
select
    d.unit_id,
    d.sku,
    u.product_line,
    u.acquisition_date,
    u.acquisition_cost,
    u.branch,
    count(*) as owned_days,
    count(*) filter (where status = 'rented') as rented_days,
    count(*) filter (where status = 'maintenance') as maintenance_days,
    count(*) filter (where status = 'idle') as idle_days,
    count(*) filter (where date_day > ds.reference_date - 90) as owned_days_90d,
    count(*) filter (where date_day > ds.reference_date - 90 and status = 'rented') as rented_days_90d,
    count(*) filter (where date_day > ds.reference_date - 90 and status = 'idle') as idle_days_90d,
    count(*) filter (where date_day > ds.reference_date - 90 and status = 'maintenance') as maintenance_days_90d,
    max(d.date_day) filter (where d.status = 'rented') as last_rented_day,
    max(d.status) filter (where d.date_day = ds.reference_date) as status_at_reference
from {{ ref('fct_equipment_unit_day') }} d
join {{ ref('dim_equipment_unit') }} u using (unit_id)
cross join ds
group by d.unit_id, d.sku, u.product_line, u.acquisition_date, u.acquisition_cost, u.branch
