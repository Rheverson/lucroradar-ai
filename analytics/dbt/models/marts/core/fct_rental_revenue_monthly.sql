-- Grão: item de contrato de locação (unidade física alocada) × mês.
-- recognized_revenue = valor mensal acordado × dias ativos / dias do mês.
-- list_revenue = mesmo cálculo com a tabela de preço (base para desconto concedido).
select
    im.contract_item_id,
    im.contract_id,
    im.unit_id,
    im.sku,
    p.product_line,
    im.customer_id,
    c.segment,
    c.region,
    c.salesperson_id,
    im.month_start,
    im.days_in_month,
    im.active_days,
    round(im.agreed_monthly_rate * im.active_days / im.days_in_month, 2) as recognized_revenue,
    round(im.list_monthly_rate * im.active_days / im.days_in_month, 2) as list_revenue,
    round((im.list_monthly_rate - im.agreed_monthly_rate) * im.active_days / im.days_in_month, 2) as discount_amount
from {{ ref('int_rental_item_months') }} im
join {{ ref('dim_customer') }} c using (customer_id)
join {{ ref('dim_product') }} p on p.sku = im.sku
where im.active_days > 0
