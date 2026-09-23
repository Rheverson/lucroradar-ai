with src as ({{ latest_version('rental_contract_items', 'contract_item_id') }})
select
    btrim(s.contract_item_id) as contract_item_id,
    btrim(s.contract_id) as contract_id,
    btrim(s.unit_id) as unit_id,
    u.sku,
    util.try_date(s.start_date) as start_date,
    util.try_date(s.end_date) as end_date,
    util.try_numeric(s.list_monthly_rate) as list_monthly_rate,
    util.try_numeric(s.agreed_monthly_rate) as agreed_monthly_rate,
    s._batch_id, s._row_number, s._versions, s._copies_in_batch,
    case
        when c.contract_id is null then 'contrato inválido ou inexistente'
        when u.unit_id is null then 'unidade física inexistente'
        when util.try_date(s.start_date) is null then 'data de início inválida'
        when coalesce(util.try_numeric(s.agreed_monthly_rate), 0) <= 0 then 'valor mensal inválido'
    end as _invalid_reason
from src s
left join {{ ref('stg_rental_contracts') }} c on c.contract_id = btrim(s.contract_id)
left join {{ ref('stg_equipment_units') }} u on u.unit_id = btrim(s.unit_id)
