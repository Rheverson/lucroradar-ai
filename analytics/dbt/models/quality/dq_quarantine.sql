-- Grão: registro em quarentena (versão mais recente de uma chave que falhou na validação).
-- O conteúdo original é preservado em raw_payload para auditoria.
{% set tables = [
    ('customers', 'customer_id', 'stg_customers_all', 'customer_id'),
    ('products', 'sku', 'stg_products_all', 'sku'),
    ('equipment_units', 'unit_id', 'stg_equipment_units_all', 'unit_id'),
    ('orders', 'order_id', 'stg_orders_all', 'order_id'),
    ('order_items', 'order_item_id', 'stg_order_items_all', 'order_item_id'),
    ('order_events', 'event_id', 'stg_order_events_all', 'event_id'),
    ('rental_contracts', 'contract_id', 'stg_rental_contracts_all', 'contract_id'),
    ('rental_contract_items', 'contract_item_id', 'stg_rental_contract_items_all', 'contract_item_id'),
    ('maintenance_orders', 'maintenance_id', 'stg_maintenance_orders_all', 'maintenance_id'),
    ('direct_costs', 'cost_id', 'stg_direct_costs_all', 'cost_id'),
    ('receivables', 'receivable_id', 'stg_receivables_all', 'receivable_id'),
    ('receipts', 'receipt_id', 'stg_receipts_all', 'receipt_id'),
    ('payables', 'payable_id', 'stg_payables_all', 'payable_id'),
    ('disbursements', 'disbursement_id', 'stg_disbursements_all', 'disbursement_id'),
] %}
{% for src, raw_key, model, key in tables %}
select
    '{{ src }}'::text as source_table,
    s.{{ key }}::text as record_key,
    s._invalid_reason as reason,
    s._batch_id as batch_id,
    s._row_number as row_number,
    to_jsonb(r) - '_batch_id' - '_source_file' - '_row_number' - '_record_hash' - '_loaded_at' as raw_payload
from {{ ref(model) }} s
join {{ source('raw', src) }} r on r._batch_id = s._batch_id and r._row_number = s._row_number
where s._invalid_reason is not null
{% if not loop.last %}union all{% endif %}
{% endfor %}
