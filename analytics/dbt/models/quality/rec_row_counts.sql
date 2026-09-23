-- Reconciliação de contagens por tabela de origem.
--   raw_rows            linhas recebidas (todas as versões e cópias)
--   distinct_keys       chaves naturais distintas
--   valid_rows          chaves que passaram na validação (staging)
--   quarantined_rows    chaves em quarentena
--   superseded_or_duplicate_rows = raw_rows − distinct_keys (versões antigas + cópias idênticas)
-- Regra: distinct_keys = valid_rows + quarantined_rows.
{% set tables = [
    ('customers', 'customer_id'), ('products', 'sku'), ('equipment_units', 'unit_id'),
    ('orders', 'order_id'), ('order_items', 'order_item_id'), ('order_events', 'event_id'),
    ('rental_contracts', 'contract_id'), ('rental_contract_items', 'contract_item_id'),
    ('maintenance_orders', 'maintenance_id'), ('direct_costs', 'cost_id'),
    ('receivables', 'receivable_id'), ('receipts', 'receipt_id'), ('payables', 'payable_id'),
    ('disbursements', 'disbursement_id'),
] %}
{% for t, key in tables %}
select
    '{{ t }}'::text as source_table,
    (select count(*) from {{ source('raw', t) }}) as raw_rows,
    (select count(distinct btrim({{ key }})) from {{ source('raw', t) }}) as distinct_keys,
    (select count(*) from {{ ref('stg_' ~ t) }}) as valid_rows,
    (select count(*) from {{ ref('stg_' ~ t ~ '_all') }} where _invalid_reason is not null) as quarantined_rows,
    (select coalesce(sum(_copies_in_batch - 1), 0) from {{ ref('stg_' ~ t ~ '_all') }}) as exact_duplicates_removed,
    (select count(*) from {{ ref('stg_' ~ t ~ '_all') }} where _versions > 1) as keys_with_multiple_versions
{% if not loop.last %}union all{% endif %}
{% endfor %}
