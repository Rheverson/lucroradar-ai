-- Grão: um pedido válido (venda ou locação) com status na referência.
with ds as (select * from {{ ref('stg_dataset') }}),
totals as (
    select order_id, sum(net_revenue) as order_value from {{ ref('fct_sales_order_lines') }} group by 1
    union all
    select c.order_id, sum(i.agreed_monthly_rate)
    from {{ ref('stg_rental_contracts') }} c join {{ ref('stg_rental_contract_items') }} i using (contract_id)
    group by 1
)
select
    m.order_id,
    m.order_type,
    m.customer_id,
    c.segment,
    c.region,
    m.salesperson_id,
    m.order_date,
    m.created_at,
    m.delivered_at,
    m.cancelled_at,
    m.current_stage,
    m.order_status,
    t.order_value,
    case when m.order_type = 'sale' then 'Venda: valor líquido' else 'Locação: valor mensal contratado' end as order_value_basis,
    round(extract(epoch from (m.delivered_at - m.created_at)) / 3600.0, 1) as lead_time_hours,
    case when m.order_status = 'open'
         then round(extract(epoch from (ds.reference_end_exclusive::timestamp - m.current_stage_at)) / 3600.0, 1)
    end as hours_in_current_stage
from {{ ref('int_order_milestones') }} m
join {{ ref('dim_customer') }} c using (customer_id)
left join totals t using (order_id)
cross join ds
