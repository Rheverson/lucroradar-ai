with src as ({{ latest_version('products', 'sku') }})
select
    upper(btrim(s.sku)) as sku,
    coalesce(a.canonical_sku, upper(btrim(s.sku))) as canonical_sku,
    (a.legacy_sku is not null) as is_legacy_code,
    util.clean_name(s.description) as description,
    util.clean_name(s.product_line) as product_line,
    s.unit_of_measure,
    util.try_numeric(s.sale_list_price) as sale_list_price,
    util.try_numeric(s.rental_monthly_rate) as rental_monthly_rate,
    (s.is_rentable = 'true') as is_rentable,
    (s.is_sellable = 'true') as is_sellable,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when nullif(btrim(s.sku), '') is null then 'sku ausente'
        when util.clean_name(s.product_line) is null then 'linha de produto ausente'
    end as _invalid_reason
from src s
left join {{ ref('product_code_aliases') }} a on a.legacy_sku = upper(btrim(s.sku))
