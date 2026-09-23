-- Clientes válidos. Duplicidades NÃO são consolidadas aqui (ver quality.dq_customer_duplicate_candidates).
select * from {{ ref('stg_customers_all') }} where _invalid_reason is null
