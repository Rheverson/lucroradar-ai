-- Grão: um título a receber (parcela) válido, com situação na data de referência.
--   open_amount   = valor − recebido até a referência (nunca negativo)
--   overdue       = em aberto E vencimento < data de referência
--   previsto      = em aberto E vencimento >= data de referência
with paid as (
    select receivable_id, sum(amount) as paid_amount, max(receipt_date) as last_receipt_date,
           count(*) as receipt_count
    from {{ ref('stg_receipts') }}
    group by 1
),
ds as (select * from {{ ref('stg_dataset') }})
select
    r.receivable_id,
    r.customer_id,
    c.legal_name as customer_name,
    c.segment,
    c.region,
    r.origin_type,
    case r.origin_type when 'sale' then 'sale' when 'rental' then 'rental' else 'opening_balance' end as business_line,
    r.origin_id,
    r.document_number,
    r.issue_date,
    r.due_date,
    r.amount,
    coalesce(p.paid_amount, 0) as paid_amount,
    greatest(r.amount - coalesce(p.paid_amount, 0), 0) as open_amount,
    p.last_receipt_date,
    case
        when r.amount - coalesce(p.paid_amount, 0) <= 0.01 then 'paid'
        when r.due_date < ds.reference_date then 'overdue'
        else 'open_not_due'
    end as status,
    case when r.amount - coalesce(p.paid_amount, 0) > 0.01 and r.due_date < ds.reference_date
         then ds.reference_date - r.due_date end as days_overdue,
    case
        when r.amount - coalesce(p.paid_amount, 0) <= 0.01 then 'Quitado'
        when r.due_date >= ds.reference_date then 'A vencer'
        when ds.reference_date - r.due_date <= 30 then '1–30 dias'
        when ds.reference_date - r.due_date <= 60 then '31–60 dias'
        when ds.reference_date - r.due_date <= 90 then '61–90 dias'
        else 'Mais de 90 dias'
    end as aging_bucket,
    r.amount_br_format,
    r._batch_id as source_batch_id,
    r._row_number as source_row_number
from {{ ref('stg_receivables') }} r
join {{ ref('dim_customer') }} c on c.customer_id = r.customer_id
left join paid p using (receivable_id)
cross join ds
