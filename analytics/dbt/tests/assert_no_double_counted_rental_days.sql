-- Uma unidade física não pode estar em dois contratos no mesmo dia (evita dupla contagem).
select i1.unit_id, i1.contract_id, i2.contract_id
from {{ ref('stg_rental_contract_items') }} i1
join {{ ref('stg_rental_contract_items') }} i2
  on i1.unit_id = i2.unit_id and i1.contract_item_id < i2.contract_item_id
 and daterange(i1.start_date, coalesce(i1.end_date, 'infinity'::date))
     && daterange(i2.start_date, coalesce(i2.end_date, 'infinity'::date))
