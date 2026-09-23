-- Grão: mês × direção (entrada/saída) × categoria. Caixa realizado (regime de caixa).
-- Entradas: recebimentos de clientes. Saídas: desembolsos de contas a pagar.
-- Não é lucro: inclui investimento em frota e exclui receita ainda não recebida.
with ds as (select * from {{ ref('stg_dataset') }})
select
    date_trunc('month', rc.receipt_date)::date as month_start,
    'inflow'::text as direction,
    'customer_receipts_' || f.business_line as category,
    case f.business_line when 'sale' then 'Recebimentos de vendas'
                         when 'rental' then 'Recebimentos de locação'
                         else 'Recebimentos de saldo inicial' end as category_label,
    sum(rc.amount) as amount
from {{ ref('stg_receipts') }} rc
join {{ ref('fct_receivables') }} f using (receivable_id)
cross join ds
where rc.receipt_date between ds.window_start and ds.reference_date
group by 1, 2, 3, 4
union all
select
    date_trunc('month', d.paid_date)::date,
    'outflow',
    p.category,
    p.category_label,
    sum(d.amount)
from {{ ref('stg_disbursements') }} d
join {{ ref('fct_payables') }} p using (payable_id)
cross join ds
where d.paid_date between ds.window_start and ds.reference_date
group by 1, 2, 3, 4
