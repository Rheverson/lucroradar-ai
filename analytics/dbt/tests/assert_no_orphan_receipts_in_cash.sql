-- Nenhum recebimento no caixa pode vir de título em quarentena.
select rc.receipt_id
from {{ ref('fct_receipts') }} rc
left join {{ ref('fct_receivables') }} r using (receivable_id)
where r.receivable_id is null
