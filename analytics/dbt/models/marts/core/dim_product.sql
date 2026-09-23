-- Grão: produto comercial canônico (SKU). Códigos legados são mapeados via seed.
select
    p.sku,
    p.description,
    p.product_line,
    p.unit_of_measure,
    p.sale_list_price,
    p.rental_monthly_rate,
    p.is_rentable,
    p.is_sellable,
    (select count(*) from {{ ref('stg_products') }} l where l.canonical_sku = p.sku and l.is_legacy_code) as legacy_codes
from {{ ref('stg_products') }} p
where not p.is_legacy_code
