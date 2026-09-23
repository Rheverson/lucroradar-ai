-- Grão: semana de vencimento × direção. Valores PREVISTOS a partir de títulos em
-- aberto e ainda não vencidos (próximos 90 dias). Não aplica probabilidade de atraso:
-- é o que está contratado, não uma previsão estatística.
with ds as (select * from {{ ref('stg_dataset') }})
select date_trunc('week', due_date)::date as week_start, 'inflow'::text as direction,
       sum(open_amount) as amount, count(*) as titles
from {{ ref('fct_receivables') }}, ds
where status = 'open_not_due' and due_date <= ds.reference_date + 90
group by 1, 2
union all
select date_trunc('week', due_date)::date, 'outflow', sum(open_amount), count(*)
from {{ ref('fct_payables') }}, ds
where open_amount > 0.01 and due_date >= ds.reference_date and due_date <= ds.reference_date + 90
group by 1, 2
