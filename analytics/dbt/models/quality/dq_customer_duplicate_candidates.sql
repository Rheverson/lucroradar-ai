-- Grão: par de cadastros de clientes (a < b) que PODEM ser a mesma empresa.
-- Nada é consolidado automaticamente. Regras explicáveis:
--   R1 mesmo CNPJ após remover pontuação                 → score 0,95
--   R2 nome normalizado parecido (trigramas ≥ 0,55), mesma cidade, sem CNPJs conflitantes
--      → 0,40 + 0,45 × similaridade (máx. 0,85: sem documento não há confirmação)
--   R3 nome normalizado muito parecido (≥ 0,75) em cidades diferentes → 0,30 × similaridade
--   CNPJs diferentes e preenchidos nunca geram score alto.
-- Normalização do nome: sem acento, maiúsculas, abreviações expandidas, sem sufixo societário.
with c as (
    select customer_id, legal_name, name_key, tax_id_digits, city, state, segment, created_at
    from {{ ref('stg_customers') }}
),
pairs as (
    select a.customer_id as customer_id_a, b.customer_id as customer_id_b,
           similarity(a.name_key, b.name_key) as name_similarity,
           (a.tax_id_digits is not null and a.tax_id_digits = b.tax_id_digits) as same_tax_id,
           (a.city = b.city and a.state = b.state) as same_city,
           (a.tax_id_digits is not null and b.tax_id_digits is not null and a.tax_id_digits <> b.tax_id_digits) as different_tax_id
    from c a
    join c b on a.customer_id < b.customer_id
     and (a.tax_id_digits = b.tax_id_digits or a.name_key % b.name_key)
),
scored as (
    select *,
        case
            when same_tax_id then 0.950
            when name_similarity >= 0.55 and same_city and not different_tax_id then round((0.40 + 0.45 * name_similarity)::numeric, 3)
            when name_similarity >= 0.75 then round((0.30 * name_similarity)::numeric, 3)
            else 0
        end as match_score
    from pairs
)
select
    s.customer_id_a,
    ca.legal_name as legal_name_a,
    s.customer_id_b,
    cb.legal_name as legal_name_b,
    round(s.name_similarity::numeric, 3) as name_similarity,
    s.same_tax_id,
    s.same_city,
    s.different_tax_id,
    s.match_score,
    concat_ws('; ',
        case when s.same_tax_id then 'mesmo CNPJ (após remover pontuação)' end,
        case when s.different_tax_id then 'CNPJs diferentes' end,
        case when s.name_similarity >= 0.55 then 'nome normalizado ' || round((s.name_similarity * 100)::numeric) || '% similar' end,
        case when s.same_city then 'mesma cidade' else 'cidades diferentes' end,
        case when ca.tax_id_digits is null or cb.tax_id_digits is null then 'um dos cadastros sem CNPJ' end
    ) as evidence,
    case
        when s.match_score >= 0.9 then 'Provável duplicidade: confirmar e unificar no cadastro de origem'
        when s.match_score >= 0.6 then 'Possível duplicidade: conferir documento e endereço antes de unificar'
        else 'Nome parecido: provavelmente empresas distintas, manter separados'
    end as recommendation,
    case when s.match_score >= 0.9 then 'alta' when s.match_score >= 0.6 then 'media' else 'baixa' end as confidence,
    coalesce(ra.net_revenue, 0) + coalesce(rb.net_revenue, 0) as combined_sales_revenue
from scored s
join c ca on ca.customer_id = s.customer_id_a
join c cb on cb.customer_id = s.customer_id_b
left join (select o.customer_id, sum(i.quantity * i.unit_list_price - i.discount_amount) as net_revenue
           from {{ ref('stg_order_items') }} i join {{ ref('stg_orders') }} o using (order_id) group by 1) ra
       on ra.customer_id = s.customer_id_a
left join (select o.customer_id, sum(i.quantity * i.unit_list_price - i.discount_amount) as net_revenue
           from {{ ref('stg_order_items') }} i join {{ ref('stg_orders') }} o using (order_id) group by 1) rb
       on rb.customer_id = s.customer_id_b
where s.match_score > 0
