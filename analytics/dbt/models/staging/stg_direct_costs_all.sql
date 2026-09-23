with src as ({{ latest_version('direct_costs', 'cost_id') }})
select
    btrim(s.cost_id) as cost_id,
    lower(btrim(s.reference_type)) as reference_type,
    btrim(s.reference_id) as reference_id,
    lower(btrim(s.cost_type)) as cost_type,
    util.try_date(s.cost_date) as cost_date,
    util.try_numeric(s.amount) as amount,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when util.try_numeric(s.amount) is null then 'valor inválido'
        when util.try_date(s.cost_date) is null then 'data inválida'
        when lower(btrim(s.reference_type)) = 'order' and o.order_id is null then 'pedido inválido ou inexistente'
        when lower(btrim(s.reference_type)) = 'contract' and c.contract_id is null then 'contrato inválido ou inexistente'
        when lower(btrim(s.reference_type)) not in ('order', 'contract') then 'tipo de referência inválido'
    end as _invalid_reason
from src s
left join {{ ref('stg_orders') }} o on o.order_id = btrim(s.reference_id)
left join {{ ref('stg_rental_contracts') }} c on c.contract_id = btrim(s.reference_id)
