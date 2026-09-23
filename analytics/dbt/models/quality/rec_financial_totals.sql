-- Reconciliação de totais entre camadas e entre métodos de cálculo independentes.
with ds as (select * from {{ ref('stg_dataset') }}),
checks as (
    select 'Receita de venda: linhas faturadas × mart mensal' as check_name,
           (select sum(net_revenue) from {{ ref('fct_sales_order_lines') }} where is_recognized) as left_value,
           (select sum(net_revenue) from {{ ref('mart_contribution_monthly') }} where business_line = 'sale') as right_value,
           0.05 as tolerance
    union all
    select 'Receita de venda: staging (qtd × preço − desconto) × fato',
           (select sum(i.quantity * i.unit_list_price - i.discount_amount)
              from {{ ref('stg_order_items') }} i
              join {{ ref('int_order_milestones') }} m using (order_id)
             where m.invoiced_at is not null),
           (select sum(net_revenue) from {{ ref('fct_sales_order_lines') }} where is_recognized),
           0.05
    union all
    select 'Receita de locação: pró-rata mensal × mart mensal',
           (select sum(recognized_revenue) from {{ ref('fct_rental_revenue_monthly') }}),
           (select sum(net_revenue) from {{ ref('mart_contribution_monthly') }} where business_line = 'rental'),
           0.05
    union all
    -- método independente: soma diária (valor mensal / dias do mês) sobre os dias locados
    select 'Receita de locação: pró-rata mensal × soma diária por unidade-dia',
           (select sum(recognized_revenue) from {{ ref('fct_rental_revenue_monthly') }}),
           (select sum(i.agreed_monthly_rate
                       / extract(day from (date_trunc('month', d.date_day) + interval '1 month' - interval '1 day')))
              from {{ ref('stg_rental_contract_items') }} i
              cross join ds
              cross join lateral generate_series(greatest(i.start_date, ds.window_start),
                    least(coalesce(i.end_date, ds.reference_end_exclusive), ds.reference_end_exclusive) - 1,
                    interval '1 day') as d(date_day)),
           -- arredondamento a centavos por item-mês
           (select count(*) * 0.01 from {{ ref('fct_rental_revenue_monthly') }})
    union all
    select 'Recebimentos: fato de recebimentos × valor pago nos títulos',
           (select sum(amount) from {{ ref('fct_receipts') }}),
           (select sum(paid_amount) from {{ ref('fct_receivables') }}),
           0.05
    union all
    select 'Títulos: valor = pago + em aberto (sem pagamentos acima do valor)',
           (select sum(amount) from {{ ref('fct_receivables') }}),
           (select sum(paid_amount + open_amount) from {{ ref('fct_receivables') }}),
           0.05
    union all
    select 'Caixa: entradas do mart × recebimentos na janela',
           (select sum(amount) from {{ ref('mart_cash_monthly') }} where direction = 'inflow'),
           (select sum(amount) from {{ ref('fct_receipts') }}, ds where receipt_date between ds.window_start and ds.reference_date),
           0.05
    union all
    select 'Vencido na referência: fato de títulos × foto do último mês',
           (select sum(open_amount) from {{ ref('fct_receivables') }} where status = 'overdue'),
           (select sum(overdue_amount) from {{ ref('mart_receivables_monthly') }}, ds
             where month_start = date_trunc('month', ds.reference_date)),
           0.05
    union all
    select 'Frota: unidade-dia locada × dias ativos dos contratos',
           (select count(*) from {{ ref('fct_equipment_unit_day') }} where status = 'rented')::numeric,
           (select sum(active_days) from {{ ref('fct_rental_revenue_monthly') }})::numeric,
           0
)
select
    check_name,
    round(left_value::numeric, 2) as left_value,
    round(right_value::numeric, 2) as right_value,
    round((left_value - right_value)::numeric, 2) as difference,
    tolerance,
    case when abs(coalesce(left_value, 0) - coalesce(right_value, 0)) <= tolerance then 'ok' else 'divergente' end as status
from checks
