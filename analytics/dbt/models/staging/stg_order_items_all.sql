with src as ({{ latest_version('order_items', 'order_item_id') }})
select
    btrim(s.order_item_id) as order_item_id,
    btrim(s.order_id) as order_id,
    upper(btrim(s.sku)) as sku_raw,
    p.canonical_sku as sku,
    coalesce(p.is_legacy_code, false) as sku_is_legacy_code,
    s.product_description as description_raw,
    (util.clean_name(s.product_description) is distinct from pc.description) as description_differs,
    util.try_numeric(s.quantity) as quantity,
    util.try_numeric(s.unit_list_price) as unit_list_price,
    coalesce(util.try_numeric(s.discount_amount), 0) as discount_amount,
    util.try_numeric(s.unit_cost) as unit_cost,
    (util.try_numeric(s.unit_cost) is not null) as cost_known,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when o.order_id is null then 'pedido inválido ou inexistente'
        when p.sku is null then 'produto inexistente'
        when util.try_numeric(s.quantity) is null or util.try_numeric(s.quantity) <= 0 then 'quantidade não positiva'
        when util.try_numeric(s.unit_list_price) is null then 'preço de lista ausente'
    end as _invalid_reason
from src s
left join {{ ref('stg_orders') }} o on o.order_id = btrim(s.order_id) and o.order_type = 'sale'
left join {{ ref('stg_products') }} p on p.sku = upper(btrim(s.sku))
left join {{ ref('stg_products') }} pc on pc.sku = p.canonical_sku
