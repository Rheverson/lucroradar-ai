with src as ({{ latest_version('orders', 'order_id') }})
select
    btrim(s.order_id) as order_id,
    lower(btrim(s.order_type)) as order_type,
    nullif(btrim(s.customer_id), '') as customer_id,
    nullif(btrim(s.salesperson_id), '') as salesperson_id,
    util.try_date(s.order_date) as order_date,
    (btrim(s.order_date) ~ '^\d{2}/\d{2}/\d{4}$') as order_date_br_format,
    s.channel,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when nullif(btrim(s.customer_id), '') is null then 'cliente ausente'
        when c.customer_id is null then 'cliente inexistente'
        when util.try_date(s.order_date) is null then 'data do pedido inválida'
        when lower(btrim(s.order_type)) not in ('sale', 'rental') then 'tipo de pedido inválido'
    end as _invalid_reason
from src s
left join {{ ref('stg_customers') }} c on c.customer_id = nullif(btrim(s.customer_id), '')
