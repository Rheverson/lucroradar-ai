# Métricas e regras de negócio

Todas as fórmulas abaixo estão implementadas em SQL no dbt (`analytics/dbt/models`) ou em
funções Python determinísticas (`services/api/lucroradar_api`). O copiloto e as alertas
consomem os mesmos serviços; nenhum número é calculado por modelo de linguagem.

Valores em BRL, **sem impostos** (simplificação do dado sintético).

## Conceitos que não se misturam

| Conceito | O que é | Onde |
|---|---|---|
| Produto comercial | SKU vendido ou alugado (`dim_product`) | catálogo |
| Unidade física | Equipamento com número de série (`dim_equipment_unit`) | frota |
| Venda | Pedido `order_type = sale`, itens em `order_items` | `fct_sales_order_lines` |
| Locação | Contrato + unidades alocadas por período | `fct_rental_revenue_monthly` |
| Receita reconhecida | Competência: faturamento (venda) ou dias de uso (locação) | `mart_contribution_monthly` |
| Recebimento | Dinheiro que entrou (data do recebimento) | `fct_receipts` |
| Margem de contribuição | Receita − custos diretos variáveis | `mart_contribution_monthly` |
| Lucro líquido | **Não calculado.** Exigiria despesas fixas, depreciação, impostos e juros | — |

## Receita

**Venda.** `receita líquida = quantidade × preço de lista − desconto`, reconhecida na data do
evento `INVOICED` (faturamento). Pedidos sem faturamento até a data de referência não têm
receita (`is_recognized = false`); pedidos cancelados também não.

**Locação.** Para cada item de contrato (uma unidade física alocada):

```
período ativo  = [início, devolução) ∩ [início da janela, data de referência]
receita do mês = valor mensal acordado × dias ativos no mês ÷ dias do mês
```

- Contrato sem devolução registrada é considerado ativo até a data de referência.
- `desconto de locação = (tabela − acordado) × dias ativos ÷ dias do mês`.
- A reconciliação compara esta fórmula com a soma diária `valor ÷ dias do mês` sobre cada
  unidade-dia locada (método independente). Diferença tolerada: centavos de arredondamento.

**Sem dupla contagem.** A receita de locação nasce do item de contrato × mês. Pagamentos e
faturas não entram na receita; unidades não podem estar em dois contratos no mesmo dia
(teste `assert_no_double_counted_rental_days`).

## Margem de contribuição

```
margem de contribuição = receita das linhas com custo conhecido
                         − custo do produto (venda)
                         − frete / logística de entrega e retirada
                         − comissão (venda)
                         − manutenção da frota rateada (locação)

margem %              = margem de contribuição ÷ receita com custo conhecido
cobertura de custo    = receita com custo conhecido ÷ receita total
```

- **Custo ausente não vira zero.** A linha fica com `product_cost` e `contribution_margin` NULL,
  entra na receita e sai do numerador e do denominador da margem %. A cobertura mostra quanto
  da receita tem custo conhecido.
- Frete e comissão são registrados por pedido e rateados entre os itens proporcionalmente à
  receita líquida.
- Logística de locação é reconhecida no mês em que ocorre e dividida igualmente entre as
  unidades do contrato.
- Manutenção de frota é reconhecida no mês de conclusão da ordem (quando o custo passa a ser
  conhecido) e rateada entre os clientes que usaram aquele SKU no mês, por unidade-dia locada.
  Sem uso no mês, o custo fica numa linha sem cliente (não atribuível), mantida no total.
- **Limitações:** manutenções em aberto ainda não têm custo e não entram; depreciação e despesas
  fixas estão fora; alocações são gerenciais.

## Ponte de margem

Chave: linha de negócio × produto × vendedor, só linhas com custo conhecido.

```
q = quantidade (venda: unidades; locação: unidade-dia)
p = bruto ÷ q          d = desconto ÷ bruto
c = (receita − margem) ÷ q          m = p·(1−d) − c

ΔM = Σ (q1 − q0)·m0            volume e mix
   + Σ q1·(p1 − p0)·(1 − d0)   preço de lista
   + Σ q1·p1·(d0 − d1)         desconto
   − Σ q1·(c1 − c0)            custo direto
```

Chaves presentes em só um período entram inteiras em volume/mix. A soma é exata (resíduo 0,
testado em `tests/python/test_bridge.py`). **É decomposição aritmética, não causalidade.**

## Caixa, vencidos e previstos

| Métrica | Fórmula | Observação |
|---|---|---|
| Recebimentos | Σ recebimentos com data no período | Caixa realizado |
| Saídas | Σ desembolsos de contas a pagar no período | Inclui investimento em frota; sem filtro por cliente |
| Recebido ÷ receita | recebimentos ÷ receita líquida do período | Indicador de conversão; períodos diferentes de competência e caixa |
| Saldo em aberto no fechamento *M* | Σ max(valor − recebido até *M*, 0) dos títulos emitidos até *M* | `mart_receivables_monthly` |
| **Vencido** no fechamento *M* | saldo em aberto com vencimento < *M* | Foto histórica, não o saldo de hoje |
| **Previsto** | títulos em aberto que vencem nos próximos 90 dias após a referência | Sem ajuste por atraso ou inadimplência |
| Aging | faixas por dias de atraso na data de referência | A vencer, 1–30, 31–60, 61–90, >90 |

Títulos sem vencimento válido vão para a quarentena; recebimentos ligados a eles também.
Isso reduz os totais de recebíveis — a tela de qualidade mostra os valores afetados.

## Frota e locação

```
dias na frota         = unidade-dia desde a aquisição (dentro da janela)
dias em manutenção    = unidade-dia com ordem de manutenção aberta
dias disponíveis      = dias na frota − dias em manutenção      ← denominador
dias locados          = unidade-dia com contrato ativo
utilização            = dias locados ÷ dias disponíveis
utilização de frota   = dias locados ÷ dias na frota            (inclui efeito da manutenção)
dias ociosos          = dias disponíveis − dias locados
capital parado (est.) = Σ custo de aquisição ÷ (60 × 30,44) × dias ociosos
```

Prioridade do status diário: manutenção > locada > ociosa. O simulador limita a utilização a um
teto físico configurável (padrão 95%) porque manutenção, deslocamento e giro impedem 100%.

## Produtividade (etapas de pedidos)

Etapas: Pedido criado → Análise de crédito → Aprovado → Separação e preparo → Faturado (venda)
→ Entregue. Cancelado é terminal.

```
duração da etapa = primeiro instante da próxima etapa − primeiro instante da etapa
```

- Medianas e p90 usam só etapas **concluídas**.
- Etapas sem saída até a referência ficam abertas (`is_open`) com duração parcial, exibidas
  separadamente (pedidos parados).
- Pedido concluído = tem `DELIVERED`; cancelado = tem `CANCELLED`; demais = aberto.
- A análise de crédito também é mostrada por faixa de valor do pedido (≥ R$ 30 mil), porque a
  mediana geral pode esconder um gargalo concentrado em pedidos grandes.

## Simulador (determinístico)

| Alavanca | Premissa | Efeito calculado |
|---|---|---|
| Desconto (p.p.) | Volume e preço de lista constantes | Receita de venda e margem (sobre a parcela com custo conhecido) |
| Utilização (p.p.) | Receita e custos por unidade-dia constantes; teto físico | Receita, custo e margem de locação |
| Prazo de recebimento (dias) | Capital preso ≈ receita diária × dias | Caixa; não altera margem |

Com filtro de segmento/região, a alavanca de utilização é desativada (frota não pertence a um
cliente). Resultados são **impacto simulado**, não ganho realizado ou garantido.

## Cobertura e limitações gerais

- Dados sintéticos; comportamentos foram injetados de propósito (ver `data/manifest`).
- Sem impostos, sem despesas fixas na margem, sem depreciação contábil.
- Clientes possivelmente duplicados **não** são unificados: rankings por cliente podem dividir
  receita entre dois cadastros até a revisão humana.
- Alertas e copiloto mostram associações; não provam causa.
