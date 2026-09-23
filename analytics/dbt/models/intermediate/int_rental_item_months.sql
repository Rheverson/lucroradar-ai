-- Grão: item de contrato (unidade física alocada) × mês civil com dias ativos na janela.
-- Receita reconhecida pró-rata dia: valor mensal acordado × dias ativos / dias do mês.
-- Período ativo = [início, devolução) limitado à janela [window_start, referência].
-- Contrato sem devolução registrada é considerado ativo até a data de referência.
with ds as (select * from {{ ref('stg_dataset') }}),
items as (
    select
        i.*,
        c.customer_id,
        greatest(i.start_date, ds.window_start) as active_from,
        least(coalesce(i.end_date, ds.reference_end_exclusive), ds.reference_end_exclusive) as active_to_excl
    from {{ ref('stg_rental_contract_items') }} i
    join {{ ref('stg_rental_contracts') }} c using (contract_id)
    cross join ds
),
months as (
    select generate_series(date_trunc('month', ds.window_start), date_trunc('month', ds.reference_date),
                           interval '1 month')::date as month_start
    from ds
)
select
    i.contract_item_id,
    i.contract_id,
    i.unit_id,
    i.sku,
    i.customer_id,
    m.month_start,
    (extract(day from (m.month_start + interval '1 month' - interval '1 day')))::int as days_in_month,
    (least(i.active_to_excl, (m.month_start + interval '1 month')::date)
        - greatest(i.active_from, m.month_start)) as active_days,
    i.agreed_monthly_rate,
    i.list_monthly_rate
from items i
join months m
  on m.month_start < i.active_to_excl
 and (m.month_start + interval '1 month')::date > i.active_from
where i.active_to_excl > i.active_from
