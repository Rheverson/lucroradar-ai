-- Grão: um recebimento financeiro válido (entrada de caixa). Linhas duplicadas
-- idênticas no arquivo de origem já foram eliminadas na staging.
select
    rc.receipt_id,
    rc.receivable_id,
    r.customer_id,
    c.segment,
    c.region,
    r.origin_type,
    case r.origin_type when 'sale' then 'sale' when 'rental' then 'rental' else 'opening_balance' end as business_line,
    rc.receipt_date,
    date_trunc('month', rc.receipt_date)::date as month_start,
    rc.amount,
    rc.method,
    (rc.receipt_date > r.due_date) as paid_after_due,
    (rc.receipt_date - r.due_date) as days_after_due
from {{ ref('stg_receipts') }} rc
join {{ ref('stg_receivables') }} r using (receivable_id)
join {{ ref('dim_customer') }} c on c.customer_id = r.customer_id
