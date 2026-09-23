-- Grão: unidade física × dia em que a unidade pertence à frota dentro da janela.
-- Status com prioridade: manutenção > locada > disponível (ociosa).
-- Manutenção sem data de fechamento é considerada aberta até a referência.
with ds as (select * from {{ ref('stg_dataset') }}),
unit_days as (
    select u.unit_id, u.sku, u.product_line, u.est_daily_depreciation, d::date as date_day
    from {{ ref('dim_equipment_unit') }} u
    cross join ds
    cross join lateral generate_series(greatest(u.acquisition_date, ds.window_start),
                                       least(coalesce(u.retired_at - 1, ds.reference_date), ds.reference_date),
                                       interval '1 day') as d
),
rented as (
    select distinct i.unit_id, d::date as date_day, i.contract_id
    from {{ ref('stg_rental_contract_items') }} i
    cross join ds
    cross join lateral generate_series(greatest(i.start_date, ds.window_start),
                                       least(coalesce(i.end_date, ds.reference_end_exclusive), ds.reference_end_exclusive) - 1,
                                       interval '1 day') as d
),
maint as (
    select distinct m.unit_id, d::date as date_day, m.maintenance_id, m.maintenance_type
    from {{ ref('stg_maintenance_orders') }} m
    cross join ds
    cross join lateral generate_series(greatest(m.opened_at, ds.window_start),
                                       least(coalesce(m.closed_at, ds.reference_end_exclusive), ds.reference_end_exclusive) - 1,
                                       interval '1 day') as d
)
select
    ud.unit_id,
    ud.sku,
    ud.product_line,
    ud.date_day,
    date_trunc('month', ud.date_day)::date as month_start,
    case
        when mt.unit_id is not null then 'maintenance'
        when r.unit_id is not null then 'rented'
        else 'idle'
    end as status,
    r.contract_id,
    mt.maintenance_id,
    ud.est_daily_depreciation
from unit_days ud
left join (select distinct on (unit_id, date_day) * from rented order by unit_id, date_day, contract_id) r
       using (unit_id, date_day)
left join (select distinct on (unit_id, date_day) * from maint order by unit_id, date_day, maintenance_id) mt
       using (unit_id, date_day)
