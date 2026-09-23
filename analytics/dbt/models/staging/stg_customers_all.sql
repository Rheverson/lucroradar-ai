with src as ({{ latest_version('customers', 'customer_id') }})
select
    nullif(btrim(s.customer_id), '') as customer_id,
    s.legal_name as legal_name_raw,
    util.clean_name(s.legal_name) as legal_name,
    util.company_key(s.legal_name) as name_key,
    nullif(regexp_replace(coalesce(s.tax_id, ''), '\D', '', 'g'), '') as tax_id_digits,
    nullif(btrim(s.segment), '') as segment_raw,
    coalesce(nullif(btrim(s.segment), ''), 'Não informado') as segment,
    coalesce(nullif(btrim(s.region), ''), sr.region, 'Não informado') as region,
    (nullif(btrim(s.region), '') is null and sr.region is not null) as region_derived_from_state,
    util.clean_name(s.city) as city,
    upper(btrim(s.state)) as state,
    nullif(btrim(s.salesperson_id), '') as salesperson_id,
    util.try_numeric(s.credit_limit) as credit_limit,
    util.try_date(s.created_at) as created_at,
    (s.legal_name is distinct from util.clean_name(s.legal_name)
        or s.legal_name = upper(s.legal_name)) as name_inconsistent,
    (s.tax_id ~ '[^0-9]') as tax_id_formatted,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when nullif(btrim(s.customer_id), '') is null then 'customer_id ausente'
        when util.clean_name(s.legal_name) is null then 'razão social ausente'
        when util.try_date(s.created_at) is null then 'data de cadastro inválida'
    end as _invalid_reason
from src s
left join {{ ref('state_region') }} sr on sr.state = upper(btrim(s.state))
