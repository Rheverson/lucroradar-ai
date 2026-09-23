-- Grão: mês × produto (SKU) da frota.
--   owned_days       unidade-dia na frota
--   available_days   owned_days − dias em manutenção (denominador da utilização)
--   time_utilization rented_days / available_days
--   fleet_utilization rented_days / owned_days (inclui o efeito da manutenção)
--   idle_depreciation estimativa gerencial do custo de capital parado (depreciação linear 60 meses)
select
    month_start,
    sku,
    product_line,
    count(distinct unit_id) as units,
    count(*) as owned_days,
    count(*) filter (where status = 'maintenance') as maintenance_days,
    count(*) filter (where status <> 'maintenance') as available_days,
    count(*) filter (where status = 'rented') as rented_days,
    count(*) filter (where status = 'idle') as idle_days,
    round(count(*) filter (where status = 'rented')::numeric
          / nullif(count(*) filter (where status <> 'maintenance'), 0), 4) as time_utilization,
    round(count(*) filter (where status = 'rented')::numeric / nullif(count(*), 0), 4) as fleet_utilization,
    round(sum(est_daily_depreciation) filter (where status = 'idle'), 2) as idle_depreciation
from {{ ref('fct_equipment_unit_day') }}
group by 1, 2, 3
