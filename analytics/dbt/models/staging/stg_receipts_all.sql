with src as ({{ latest_version('receipts', 'receipt_id') }})
select
    btrim(s.receipt_id) as receipt_id,
    btrim(s.receivable_id) as receivable_id,
    util.try_date(s.receipt_date) as receipt_date,
    util.try_numeric(s.amount) as amount,
    s.method,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when r.receivable_id is null then 'título inexistente ou em quarentena'
        when util.try_date(s.receipt_date) is null then 'data de recebimento inválida'
        when coalesce(util.try_numeric(s.amount), 0) <= 0 then 'valor inválido'
    end as _invalid_reason
from src s
left join {{ ref('stg_receivables') }} r on r.receivable_id = btrim(s.receivable_id)
