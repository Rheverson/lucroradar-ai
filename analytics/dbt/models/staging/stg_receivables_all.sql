with src as ({{ latest_version('receivables', 'receivable_id') }})
select
    btrim(s.receivable_id) as receivable_id,
    nullif(btrim(s.customer_id), '') as customer_id,
    lower(btrim(s.origin_type)) as origin_type,
    btrim(s.origin_id) as origin_id,
    s.document_number,
    util.try_date(s.issue_date) as issue_date,
    util.try_date(s.due_date) as due_date,
    util.try_numeric(s.amount) as amount,
    util.is_br_number(s.amount) as amount_br_format,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when c.customer_id is null then 'cliente inexistente'
        when util.try_date(s.due_date) is null then 'vencimento ausente ou inválido'
        when util.try_date(s.issue_date) is null then 'emissão inválida'
        when util.try_numeric(s.amount) is null or util.try_numeric(s.amount) <= 0 then 'valor inválido'
    end as _invalid_reason
from src s
left join {{ ref('stg_customers') }} c on c.customer_id = nullif(btrim(s.customer_id), '')
