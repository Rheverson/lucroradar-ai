with src as ({{ latest_version('rental_contracts', 'contract_id') }})
select
    btrim(s.contract_id) as contract_id,
    btrim(s.order_id) as order_id,
    nullif(btrim(s.customer_id), '') as customer_id,
    util.try_date(s.start_date) as start_date,
    util.try_date(s.planned_end_date) as planned_end_date,
    util.try_date(s.actual_end_date) as actual_end_date,
    s.billing_cycle,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when c.customer_id is null then 'cliente inexistente'
        when o.order_id is null then 'pedido de locação inexistente'
        when util.try_date(s.start_date) is null then 'data de início inválida'
        when util.try_date(s.actual_end_date) < util.try_date(s.start_date) then 'devolução antes do início'
    end as _invalid_reason
from src s
left join {{ ref('stg_customers') }} c on c.customer_id = nullif(btrim(s.customer_id), '')
left join {{ ref('stg_orders') }} o on o.order_id = btrim(s.order_id) and o.order_type = 'rental'
