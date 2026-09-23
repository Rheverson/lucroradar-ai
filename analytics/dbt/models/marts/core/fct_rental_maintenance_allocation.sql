-- Grão: mês × SKU × cliente. Custo de manutenção da frota (ordens concluídas, custo
-- conhecido) reconhecido no mês de conclusão e rateado entre os clientes que usaram
-- aquele SKU no mês, proporcionalmente às unidade-dia locadas.
-- Sem uso no mês → linha sem cliente (custo não atribuível, mantido no total).
-- Manutenções em aberto não têm custo conhecido e não entram (limitação documentada).
with ds as (select * from {{ ref('stg_dataset') }}),
mc as (
    select date_trunc('month', closed_at)::date as month_start, sku, product_line, sum(cost_amount) as cost
    from {{ ref('fct_maintenance_orders') }}, ds
    where closed_at is not null and cost_amount is not null and closed_at >= ds.window_start
    group by 1, 2, 3
),
usage as (
    select month_start, sku, customer_id, segment, region, salesperson_id, sum(active_days) as days
    from {{ ref('fct_rental_revenue_monthly') }}
    group by 1, 2, 3, 4, 5, 6
),
tot as (select month_start, sku, sum(days) as days from usage group by 1, 2)
select
    mc.month_start,
    mc.sku,
    mc.product_line,
    u.customer_id,
    u.segment,
    u.region,
    u.salesperson_id,
    case when u.customer_id is null then mc.cost
         else round(mc.cost * u.days / t.days, 2) end as amount
from mc
left join tot t on t.month_start = mc.month_start and t.sku = mc.sku
left join usage u on u.month_start = mc.month_start and u.sku = mc.sku
