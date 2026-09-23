with src as ({{ latest_version('disbursements', 'disbursement_id') }})
select
    btrim(s.disbursement_id) as disbursement_id,
    btrim(s.payable_id) as payable_id,
    util.try_date(s.paid_date) as paid_date,
    util.try_numeric(s.amount) as amount,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when p.payable_id is null then 'conta a pagar inexistente'
        when util.try_date(s.paid_date) is null then 'data de pagamento inválida'
        when util.try_numeric(s.amount) is null then 'valor inválido'
    end as _invalid_reason
from src s
left join {{ ref('stg_payables') }} p on p.payable_id = btrim(s.payable_id)
