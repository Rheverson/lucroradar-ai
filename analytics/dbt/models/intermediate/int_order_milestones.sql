-- Grão: um pedido válido. Primeiro instante de cada etapa e status na data de referência.
with ev as (
    select order_id, stage_code, min(event_at) as first_at
    from {{ ref('stg_order_events') }}
    group by 1, 2
),
piv as (
    select
        order_id,
        max(first_at) filter (where stage_code = 'CREATED') as created_at,
        max(first_at) filter (where stage_code = 'CREDIT_REVIEW') as credit_review_at,
        max(first_at) filter (where stage_code = 'APPROVED') as approved_at,
        max(first_at) filter (where stage_code = 'PICKING') as picking_at,
        max(first_at) filter (where stage_code = 'INVOICED') as invoiced_at,
        max(first_at) filter (where stage_code = 'DELIVERED') as delivered_at,
        max(first_at) filter (where stage_code = 'CANCELLED') as cancelled_at
    from ev
    group by 1
),
last_stage as (
    select distinct on (e.order_id) e.order_id, e.stage_code as current_stage, e.event_at as current_stage_at
    from {{ ref('stg_order_events') }} e
    join {{ ref('stage_catalog') }} sc using (stage_code)
    order by e.order_id, e.event_at desc, sc.stage_order desc
)
select
    o.order_id,
    o.order_type,
    o.customer_id,
    o.salesperson_id,
    o.order_date,
    p.created_at, p.credit_review_at, p.approved_at, p.picking_at,
    p.invoiced_at, p.delivered_at, p.cancelled_at,
    ls.current_stage,
    ls.current_stage_at,
    case
        when p.cancelled_at is not null then 'cancelled'
        when p.delivered_at is not null then 'completed'
        else 'open'
    end as order_status
from {{ ref('stg_orders') }} o
left join piv p using (order_id)
left join last_stage ls using (order_id)
