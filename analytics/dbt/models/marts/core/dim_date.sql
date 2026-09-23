-- Grão: um dia da janela analítica.
select
    d::date as date_day,
    date_trunc('month', d)::date as month_start,
    date_trunc('quarter', d)::date as quarter_start,
    extract(isodow from d)::int as iso_weekday,
    to_char(d, 'YYYY-MM') as year_month
from {{ ref('stg_dataset') }} ds,
     generate_series(ds.window_start, ds.reference_date, interval '1 day') as d
