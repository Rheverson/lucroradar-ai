-- Grão: uma conta a pagar válida, com valor pago até a referência.
with paid as (
    select payable_id, sum(amount) as paid_amount, max(paid_date) as last_paid_date
    from {{ ref('stg_disbursements') }} group by 1
)
select
    p.payable_id,
    p.supplier_name,
    p.category,
    case p.category
        when 'inventory_purchase' then 'Compras de estoque para revenda'
        when 'fleet_capex' then 'Aquisição de frota (investimento)'
        when 'maintenance' then 'Manutenção de frota'
        when 'freight' then 'Frete e logística'
        when 'operating_expenses' then 'Despesas operacionais fixas'
    end as category_label,
    p.issue_date,
    p.due_date,
    p.amount,
    coalesce(pd.paid_amount, 0) as paid_amount,
    greatest(p.amount - coalesce(pd.paid_amount, 0), 0) as open_amount,
    pd.last_paid_date
from {{ ref('stg_payables') }} p
left join paid pd using (payable_id)
