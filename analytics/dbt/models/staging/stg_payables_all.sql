with src as ({{ latest_version('payables', 'payable_id') }})
select
    btrim(s.payable_id) as payable_id,
    s.supplier_name,
    lower(btrim(s.category)) as category,
    util.try_date(s.issue_date) as issue_date,
    util.try_date(s.due_date) as due_date,
    util.try_numeric(s.amount) as amount,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when util.try_numeric(s.amount) is null then 'valor inválido'
        when util.try_date(s.due_date) is null then 'vencimento inválido'
        when lower(btrim(s.category)) not in ('inventory_purchase','fleet_capex','maintenance','freight','operating_expenses')
            then 'categoria desconhecida'
    end as _invalid_reason
from src s
