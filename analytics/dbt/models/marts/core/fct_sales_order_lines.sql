-- Grão: uma linha de item de pedido de VENDA válida.
-- Receita reconhecida na data de faturamento (evento INVOICED). Linhas sem
-- faturamento até a referência ficam com is_recognized = false.
-- Custo do produto ausente permanece NULL (nunca zero) e a margem da linha fica NULL.
-- Frete e comissão do pedido são rateados pelas linhas proporcionalmente à receita líquida.
with lines as (
    select
        i.*,
        i.quantity * i.unit_list_price as gross_amount,
        i.quantity * i.unit_list_price - i.discount_amount as net_revenue,
        case when i.cost_known then i.quantity * i.unit_cost end as product_cost
    from {{ ref('stg_order_items') }} i
),
order_net as (
    select order_id, sum(net_revenue) as order_net from lines group by 1
),
order_costs as (
    select reference_id as order_id,
           sum(amount) filter (where cost_type = 'freight') as freight,
           sum(amount) filter (where cost_type = 'commission') as commission
    from {{ ref('stg_direct_costs') }}
    where reference_type = 'order'
    group by 1
)
select
    l.order_item_id,
    l.order_id,
    m.customer_id,
    m.salesperson_id,
    c.segment,
    c.region,
    l.sku,
    p.product_line,
    m.order_date,
    m.invoiced_at::date as revenue_date,
    date_trunc('month', m.invoiced_at)::date as revenue_month,
    (m.invoiced_at is not null) as is_recognized,
    m.order_status,
    l.quantity,
    l.unit_list_price,
    l.gross_amount,
    l.discount_amount,
    l.net_revenue,
    case when l.gross_amount > 0 then l.discount_amount / l.gross_amount end as discount_rate,
    l.cost_known,
    l.product_cost,
    round(coalesce(oc.freight, 0) * l.net_revenue / nullif(n.order_net, 0), 2) as freight_cost,
    round(coalesce(oc.commission, 0) * l.net_revenue / nullif(n.order_net, 0), 2) as commission_cost,
    case when l.cost_known then
        l.net_revenue - l.product_cost
        - round(coalesce(oc.freight, 0) * l.net_revenue / nullif(n.order_net, 0), 2)
        - round(coalesce(oc.commission, 0) * l.net_revenue / nullif(n.order_net, 0), 2)
    end as contribution_margin,
    l.sku_raw,
    l.sku_is_legacy_code,
    l._batch_id as source_batch_id,
    l._row_number as source_row_number
from lines l
join {{ ref('int_order_milestones') }} m using (order_id)
join {{ ref('dim_customer') }} c on c.customer_id = m.customer_id
join {{ ref('dim_product') }} p on p.sku = l.sku
join order_net n using (order_id)
left join order_costs oc using (order_id)
