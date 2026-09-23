-- Uma linha: janela analítica e data de referência do lote mais recente carregado.
select
    window_start,
    reference_date,
    (reference_date + 1) as reference_end_exclusive,
    batch_id as latest_batch_id,
    is_synthetic
from {{ source('audit', 'load_batches') }}
where status = 'loaded'
order by batch_seq desc
limit 1
