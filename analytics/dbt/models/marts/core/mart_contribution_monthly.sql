-- Grão: mês × linha de negócio (venda/locação) × cliente × produto × vendedor.
-- Fonte única para receita e margem de contribuição da visão executiva.
--   net_revenue          receita reconhecida (líquida de descontos, sem impostos)
--   revenue_cost_known   receita das linhas com custo direto conhecido
--   product_cost         custo do produto vendido (somente venda; NULL-safe: só linhas com custo)
--   logistics_cost       frete (venda) ou entrega/retirada (locação)
--   commission_cost      comissão sobre venda
--   maintenance_cost     manutenção de frota rateada por uso (locação)
--   contribution_margin  revenue_cost_known − custos diretos das mesmas linhas
--   quantity             venda: unidades vendidas; locação: unidade-dia locada
--   *_cost_known         mesmas medidas restritas às linhas com custo conhecido (base da ponte de margem)
-- Não inclui despesas fixas, depreciação, impostos ou juros: NÃO é lucro líquido.
with sales as (
    select
        revenue_month as month_start, 'sale'::text as business_line,
        customer_id, segment, region, salesperson_id, sku, product_line,
        sum(quantity) as quantity,
        sum(gross_amount) as gross_amount,
        sum(discount_amount) as discount_amount,
        sum(net_revenue) as net_revenue,
        coalesce(sum(net_revenue) filter (where cost_known), 0) as revenue_cost_known,
        coalesce(sum(product_cost), 0) as product_cost,
        coalesce(sum(freight_cost) filter (where cost_known), 0) as logistics_cost,
        coalesce(sum(commission_cost) filter (where cost_known), 0) as commission_cost,
        0::numeric as maintenance_cost,
        coalesce(sum(contribution_margin), 0) as contribution_margin,
        count(*) as line_count,
        count(*) filter (where not cost_known) as lines_missing_cost,
        coalesce(sum(quantity) filter (where cost_known), 0) as quantity_cost_known,
        coalesce(sum(gross_amount) filter (where cost_known), 0) as gross_cost_known,
        coalesce(sum(discount_amount) filter (where cost_known), 0) as discount_cost_known
    from {{ ref('fct_sales_order_lines') }}
    where is_recognized
    group by 1, 2, 3, 4, 5, 6, 7, 8
),
rental_parts as (
    select month_start, customer_id, segment, region, salesperson_id, sku, product_line,
           active_days as quantity, list_revenue as gross_amount, discount_amount,
           recognized_revenue as net_revenue, 0::numeric as logistics_cost,
           0::numeric as maintenance_cost, 1 as line_count
    from {{ ref('fct_rental_revenue_monthly') }}
    union all
    select month_start, customer_id, segment, region, salesperson_id, sku, product_line,
           0, 0, 0, 0, amount, 0, 0
    from {{ ref('fct_rental_logistics_costs') }}
    where month_start >= (select date_trunc('month', window_start) from {{ ref('stg_dataset') }})
    union all
    select month_start, customer_id, segment, region, salesperson_id, sku, product_line,
           0, 0, 0, 0, 0, amount, 0
    from {{ ref('fct_rental_maintenance_allocation') }}
),
rental as (
    select
        month_start, 'rental'::text as business_line,
        customer_id, segment, region, salesperson_id, sku, product_line,
        sum(quantity) as quantity,
        sum(gross_amount) as gross_amount,
        sum(discount_amount) as discount_amount,
        sum(net_revenue) as net_revenue,
        sum(net_revenue) as revenue_cost_known,
        0::numeric as product_cost,
        sum(logistics_cost) as logistics_cost,
        0::numeric as commission_cost,
        sum(maintenance_cost) as maintenance_cost,
        sum(net_revenue) - sum(logistics_cost) - sum(maintenance_cost) as contribution_margin,
        sum(line_count) as line_count,
        0::bigint as lines_missing_cost,
        sum(quantity) as quantity_cost_known,
        sum(gross_amount) as gross_cost_known,
        sum(discount_amount) as discount_cost_known
    from rental_parts
    group by 1, 2, 3, 4, 5, 6, 7, 8
)
select * from sales
union all
select * from rental
