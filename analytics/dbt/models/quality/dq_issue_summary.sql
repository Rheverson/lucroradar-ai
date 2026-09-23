-- Grão: tipo de problema de qualidade × tabela de origem.
-- handling: quarentena (fora das análises) | padronizado (corrigido de forma determinística)
--           | sinalizado (mantido, com impacto indicado) | para revisão (decisão humana)
with q as (
    select
        source_table,
        reason,
        count(*) as affected_records,
        sum(case source_table
                when 'order_items' then util.try_numeric(raw_payload->>'quantity') * util.try_numeric(raw_payload->>'unit_list_price')
                                        - coalesce(util.try_numeric(raw_payload->>'discount_amount'), 0)
                when 'receivables' then util.try_numeric(raw_payload->>'amount')
                when 'receipts' then util.try_numeric(raw_payload->>'amount')
                when 'direct_costs' then util.try_numeric(raw_payload->>'amount')
            end) as affected_amount
    from {{ ref('dq_quarantine') }}
    group by 1, 2
),
quarantine as (
    select
        'quarantine:' || source_table || ':' || reason as issue_code,
        case
            when reason like '%inexistente%' or reason like '%inválido ou inexistente%' then 'Referência órfã'
            when reason like '%ausente%' then 'Campo obrigatório ausente'
            else 'Valor inválido'
        end as category,
        upper(left(reason, 1)) || substr(reason, 2) as issue_label,
        source_table,
        affected_records,
        affected_amount,
        'quarentena'::text as handling,
        case source_table
            when 'order_items' then 'Receita dessas linhas fica fora de receita e margem até correção na origem.'
            when 'orders' then 'Pedido e todos os seus itens, eventos e custos ficam fora das análises.'
            when 'order_events' then 'Eventos de pedidos inválidos não entram no tempo por etapa.'
            when 'receivables' then 'Títulos fora de contas a receber e vencidos; recebimentos associados também vão para a quarentena.'
            when 'receipts' then 'Recebimentos sem título válido não entram no caixa realizado.'
            when 'direct_costs' then 'Custos de pedidos inválidos não entram na margem.'
            else 'Registro excluído das análises até correção na origem.'
        end as consequence
    from q
),
flags as (
    select 'missing_cost' as issue_code, 'Campo obrigatório ausente' as category,
           'Custo do produto ausente em itens de venda' as issue_label, 'order_items' as source_table,
           count(*) as affected_records, sum(quantity * unit_list_price - discount_amount) as affected_amount,
           'sinalizado' as handling,
           'Receita mantida; margem calculada só sobre linhas com custo conhecido (custo ausente nunca vira zero). Reduz a cobertura da margem.' as consequence
    from {{ ref('stg_order_items') }} where not cost_known
    union all
    select 'missing_segment', 'Campo obrigatório ausente', 'Segmento do cliente ausente', 'customers',
           count(*), null, 'sinalizado',
           'Clientes aparecem como "Não informado" nos filtros de segmento; análises por segmento ficam incompletas.'
    from {{ ref('stg_customers') }} where segment_raw is null
    union all
    select 'region_derived', 'Campo obrigatório ausente', 'Região ausente, derivada da UF', 'customers',
           count(*), null, 'padronizado',
           'Região preenchida pela tabela UF → região (regra determinística).'
    from {{ ref('stg_customers') }} where region_derived_from_state
    union all
    select 'name_inconsistent', 'Inconsistência', 'Razão social com espaços extras ou caixa alta', 'customers',
           count(*), null, 'padronizado',
           'Nome exibido limpo; chave de comparação normalizada usada apenas para sugerir duplicidades.'
    from {{ ref('stg_customers') }} where name_inconsistent
    union all
    select 'tax_id_formatting', 'Formato', 'CNPJ com pontuação variável', 'customers',
           count(*), null, 'padronizado', 'Comparações usam apenas os dígitos.'
    from {{ ref('stg_customers') }} where tax_id_formatted
    union all
    select 'legacy_sku', 'Inconsistência', 'Item com código de produto legado', 'order_items',
           count(*), sum(quantity * unit_list_price - discount_amount), 'padronizado',
           'Mapeado para o código canônico por tabela curada; sem isso a receita do produto ficaria dividida.'
    from {{ ref('stg_order_items') }} where sku_is_legacy_code
    union all
    select 'description_variant', 'Inconsistência', 'Descrição do item diferente do cadastro', 'order_items',
           count(*), sum(quantity * unit_list_price - discount_amount), 'padronizado',
           'Análises usam o SKU e a descrição do cadastro; descrição livre preservada no raw.'
    from {{ ref('stg_order_items') }} where description_differs
    union all
    select 'br_date_format', 'Formato', 'Data do pedido no formato DD/MM/AAAA', 'orders',
           count(*), null, 'padronizado', 'Convertida para data ISO sem perda.'
    from {{ ref('stg_orders') }} where order_date_br_format
    union all
    select 'br_amount_format', 'Formato', 'Valor no formato brasileiro (1.234,56)', 'receivables',
           count(*), sum(amount), 'padronizado', 'Convertido para número sem perda.'
    from {{ ref('stg_receivables') }} where amount_br_format
    union all
    select 'stage_code_case', 'Formato', 'Código de etapa com caixa/espaços variados', 'order_events',
           count(*), null, 'padronizado', 'Normalizado para o catálogo de etapas.'
    from {{ ref('stg_order_events') }} where stage_code_standardized
    union all
    select 'exact_duplicate_' || t.source_table, 'Duplicidade', 'Linha repetida no mesmo arquivo', t.source_table,
           t.exact_duplicates_removed, null, 'padronizado',
           'Cópias idênticas removidas; apenas uma versão entra nas análises (evita dupla contagem).'
    from {{ ref('rec_row_counts') }} t where t.exact_duplicates_removed > 0
    union all
    select 'duplicate_customer_candidate_' || confidence, 'Duplicidade',
           'Possível cliente duplicado (confiança ' || confidence || ')', 'customers',
           count(*), sum(combined_sales_revenue), 'para revisão',
           'Receita e ranking de clientes podem estar divididos entre cadastros. Nada é unificado automaticamente.'
    from {{ ref('dq_customer_duplicate_candidates') }} group by confidence
    union all
    select 'ingestion_reject', 'Valor inválido', 'Linha com número de colunas incorreto', table_name,
           count(*), null, 'quarentena', 'Linha rejeitada na ingestão; não chega ao raw.'
    from {{ source('audit', 'ingestion_rejects') }} group by table_name
)
select * from quarantine
union all
select * from flags where affected_records > 0
