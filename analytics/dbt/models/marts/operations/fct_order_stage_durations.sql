-- Grão: pedido × etapa em que o pedido entrou.
-- duration_hours = instante da próxima etapa − entrada nesta etapa.
-- Etapas ainda sem saída na referência ficam com is_open = true e duração parcial
-- (tempo decorrido até o fim da data de referência). Etapas terminais não têm duração.
with ds as (select * from {{ ref('stg_dataset') }}),
ev as (
    select e.order_id, e.stage_code, min(e.event_at) as entered_at
    from {{ ref('stg_order_events') }} e
    group by 1, 2
),
seq as (
    select
        ev.*,
        sc.stage_order,
        sc.stage_label,
        sc.is_terminal,
        lead(ev.entered_at) over (partition by ev.order_id order by ev.entered_at, sc.stage_order) as next_at,
        lead(ev.stage_code) over (partition by ev.order_id order by ev.entered_at, sc.stage_order) as next_stage
    from ev
    join {{ ref('stage_catalog') }} sc using (stage_code)
)
select
    s.order_id,
    o.order_type,
    o.segment,
    o.region,
    o.order_value,
    s.stage_code,
    s.stage_label,
    s.stage_order,
    s.entered_at,
    date_trunc('month', s.entered_at)::date as entered_month,
    s.next_stage,
    s.next_at as exited_at,
    (s.next_at is null and not s.is_terminal) as is_open,
    case
        when s.is_terminal then null
        when s.next_at is not null then round(extract(epoch from (s.next_at - s.entered_at)) / 3600.0, 2)
        else round(extract(epoch from (ds.reference_end_exclusive::timestamp - s.entered_at)) / 3600.0, 2)
    end as duration_hours
from seq s
join {{ ref('fct_orders') }} o using (order_id)
cross join ds
