with src as ({{ latest_version('order_events', 'event_id') }})
select
    btrim(s.event_id) as event_id,
    btrim(s.order_id) as order_id,
    upper(btrim(s.stage_code)) as stage_code,
    (s.stage_code is distinct from upper(btrim(s.stage_code))) as stage_code_standardized,
    util.try_timestamp(s.event_at) as event_at,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when o.order_id is null then 'pedido inválido ou inexistente'
        when sc.stage_code is null then 'etapa desconhecida'
        when util.try_timestamp(s.event_at) is null then 'data/hora do evento inválida'
    end as _invalid_reason
from src s
left join {{ ref('stg_orders') }} o on o.order_id = btrim(s.order_id)
left join {{ ref('stage_catalog') }} sc on sc.stage_code = upper(btrim(s.stage_code))
