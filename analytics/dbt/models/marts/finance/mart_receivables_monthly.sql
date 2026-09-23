-- Grão: fim de mês × cliente × linha de negócio.
-- Saldo em aberto e vencido NA DATA de cada fechamento (foto histórica),
-- recalculado a partir de emissão, vencimento e recebimentos até aquela data.
with ds as (select * from {{ ref('stg_dataset') }}),
months as (
    select m::date as month_start,
           least((m + interval '1 month' - interval '1 day')::date, ds.reference_date) as snapshot_date
    from ds, generate_series(date_trunc('month', ds.window_start), date_trunc('month', ds.reference_date),
                             interval '1 month') as m
),
recv as (
    select r.receivable_id, r.customer_id, r.issue_date, r.due_date, r.amount, f.business_line,
           f.segment, f.region
    from {{ ref('stg_receivables') }} r
    join {{ ref('fct_receivables') }} f using (receivable_id)
),
snap as (
    select
        m.month_start, m.snapshot_date, r.customer_id, r.business_line, r.segment, r.region,
        r.receivable_id, r.due_date,
        greatest(r.amount - coalesce(sum(rc.amount), 0), 0) as open_amount
    from months m
    join recv r on r.issue_date <= m.snapshot_date
    left join {{ ref('fct_receipts') }} rc
      on rc.receivable_id = r.receivable_id and rc.receipt_date <= m.snapshot_date
    group by 1, 2, 3, 4, 5, 6, 7, 8, r.amount
)
select
    month_start, snapshot_date, customer_id, business_line, segment, region,
    sum(open_amount) as open_amount,
    sum(open_amount) filter (where due_date < snapshot_date) as overdue_amount,
    sum(open_amount) filter (where due_date < snapshot_date - 30) as overdue_over_30,
    count(*) filter (where open_amount > 0.01 and due_date < snapshot_date) as overdue_titles
from snap
where open_amount > 0.01
group by 1, 2, 3, 4, 5, 6
