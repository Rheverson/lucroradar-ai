-- Grão: custo logístico (entrega/retirada) × item do contrato.
-- Reconhecido no mês em que ocorre; dividido igualmente entre as unidades do contrato.
with items as (
    select contract_id, contract_item_id, sku, count(*) over (partition by contract_id) as n_items
    from {{ ref('stg_rental_contract_items') }}
)
select
    dc.cost_id,
    i.contract_item_id,
    dc.reference_id as contract_id,
    rc.customer_id,
    c.segment,
    c.region,
    c.salesperson_id,
    i.sku,
    p.product_line,
    dc.cost_type,
    dc.cost_date,
    date_trunc('month', dc.cost_date)::date as month_start,
    round(dc.amount / i.n_items, 2) as amount
from {{ ref('stg_direct_costs') }} dc
join items i on i.contract_id = dc.reference_id
join {{ ref('stg_rental_contracts') }} rc on rc.contract_id = dc.reference_id
join {{ ref('dim_customer') }} c on c.customer_id = rc.customer_id
join {{ ref('dim_product') }} p on p.sku = i.sku
where dc.reference_type = 'contract'
