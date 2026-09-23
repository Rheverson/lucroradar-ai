-- Grão: um cadastro de cliente válido (customer_id). Possíveis duplicidades
-- ficam sinalizadas, não consolidadas.
with cand as (
    select customer_id_a as customer_id, max(match_score) as score from {{ ref('dq_customer_duplicate_candidates') }} group by 1
    union all
    select customer_id_b, max(match_score) from {{ ref('dq_customer_duplicate_candidates') }} group by 1
)
select
    c.customer_id,
    c.legal_name,
    c.name_key,
    c.tax_id_digits,
    c.segment,
    c.region,
    c.region_derived_from_state,
    c.city,
    c.state,
    c.salesperson_id,
    c.credit_limit,
    c.created_at,
    (c.segment_raw is null) as segment_missing,
    coalesce(max(cand.score), 0) as duplicate_candidate_score,
    (max(cand.score) is not null) as is_duplicate_candidate
from {{ ref('stg_customers') }} c
left join cand using (customer_id)
group by c.customer_id, c.legal_name, c.name_key, c.tax_id_digits, c.segment, c.region,
         c.region_derived_from_state, c.city, c.state, c.salesperson_id, c.credit_limit,
         c.created_at, c.segment_raw
