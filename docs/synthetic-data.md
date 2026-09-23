# Dados sintéticos

Empresa fictícia **Nexo Equipamentos** (vende e aluga geradores, plataformas elevatórias,
compactadores, andaimes, torres de iluminação, compressores, ferramentas e peças). Nomes de
clientes e fornecedores são palavras inventadas por sílabas; CNPJs começam com `99` e não são
documentos reais. Qualquer semelhança com empresas reais é coincidência.

```bash
uv run lucroradar-generate --seed 42 --reference-date 2026-06-30 --months 18 --scale 1.0
```

Mesmo seed e mesma data de referência produzem arquivos idênticos (teste
`test_same_seed_same_files`).

## Volume (seed 42, escala 1)

~440 clientes, 22 produtos + 2 códigos legados, ~375 unidades físicas, ~3,9 mil pedidos de venda,
~2,2 mil pedidos/contratos de locação, ~34 mil eventos de etapa, ~9,9 mil títulos a receber,
~9,3 mil recebimentos, ~1,2 mil contas a pagar.

## Cenários de negócio embutidos

| Cenário | Como aparece nos dados |
|---|---|
| Crescimento de demanda | ~2,3% a.m. com sazonalidade leve |
| Descontos elevados | Vendedores V06 e V07 passam a conceder 15–26% a partir de jan/26 e ganham volume |
| Aumento de custo | Custo de Geradores +14% a partir de fev/26 sem reajuste de preço |
| Reajuste de tabela | +4% em jan/26 (exceto Geradores) |
| Recebimentos atrasados | 6 clientes de Eventos passam a pagar 60–150 dias após o vencimento (dez/25+) |
| Frota ociosa | +20 plataformas PLT-T12 em nov/25 com demanda estável |
| Manutenção longa | Articuladas PLT-A16/A20 devolvidas entre mar e mai/26 aguardam peça importada (55–110 dias) |
| Gargalo | Análise de crédito de pedidos ≥ R$ 30 mil: mediana de ~19 h para ~108 h a partir de mar/26 |

## Problemas de qualidade injetados

Clientes duplicados (14 pares, três padrões) e 2 pares de nomes parecidos que **não** são a
mesma empresa; nomes com espaços/caixa inconsistentes; CNPJ com e sem pontuação; segmento e
região ausentes; códigos legados de produto e descrições livres divergentes; custo ausente
(aleatório e um bloco em Peças nos últimos 3 meses); pedidos sem cliente ou com data impossível;
quantidade negativa; SKU inexistente; linhas duplicadas no arquivo; títulos sem vencimento; valor
no formato brasileiro; recebimentos órfãos; códigos de etapa com caixa diferente.

## Manifesto de verdade conhecida

`data/manifest/ground_truth.json` lista os cenários, os IDs afetados e totais esperados
(receita por mês, recebimentos, vencido). **Só os testes leem este arquivo**; a API e a
interface nunca o usam.
