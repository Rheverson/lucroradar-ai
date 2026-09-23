# Pipeline: geração, ingestão e transformação

## Execução

```bash
uv run lucroradar-ingest run --generate           # gera, carrega e roda dbt build
uv run lucroradar-ingest run                      # reexecuta: arquivos já carregados são ignorados
uv run lucroradar-ingest run --generate --seed 7 --reference-date 2025-12-31 --replace
uv run lucroradar-ingest status
```

## Lotes

| Lote | Conteúdo |
|---|---|
| `batch_001_initial` | situação no último dia antes do mês de referência |
| `batch_002_incremental` | mês de referência + novas versões de contratos encerrados, manutenções concluídas e cadastros corrigidos |

Cada pasta traz `_batch.json` (data de posição, janela, seed, hash e linhas de cada arquivo).

## Garantias

1. **Raw preservado.** Nada é limpo na carga; tudo em texto.
2. **Reexecução sem duplicação.** `audit.load_files` guarda o SHA-256 de cada arquivo por lote.
   Mesmo arquivo → ignorado. Arquivo diferente no mesmo lote → erro, a menos que `--replace`
   (apaga e recarrega aquele arquivo na mesma transação). Testado em `test_rerun_does_not_duplicate`
   e no CI (duas execuções seguidas).
3. **Carga atômica por arquivo.** Cada arquivo em uma transação; falha deixa o lote `failed`.
4. **Contrato de colunas.** Cabeçalho diferente do contrato aborta o lote; linha com número de
   colunas errado vai para `audit.ingestion_rejects`.
5. **Logs.** `audit.pipeline_runs` e `audit.pipeline_run_steps` (visíveis na tela de qualidade).

## Staging: validação e quarentena

Cada tabela tem `stg_<t>_all` (versão mais recente por chave, tipada, com `_invalid_reason`) e
`stg_<t>` (apenas válidos). Funções `util.try_date`, `util.try_numeric` e `util.try_timestamp`
convertem sem falhar: valor inválido vira NULL e o registro recebe o motivo.

Regras de quarentena (exemplos): pedido sem cliente ou com data impossível; item com quantidade
não positiva ou SKU inexistente; título sem vencimento; recebimento de título inexistente;
eventos/custos de pedidos inválidos (integridade referencial).

Padronizações determinísticas: datas `DD/MM/AAAA`, valores `1.234,56`, códigos de etapa em
caixa diferente, espaços em nomes, CNPJ com pontuação, região derivada da UF, códigos legados de
produto via seed curada `product_code_aliases`.

## Testes de dados (dbt)

- Genéricos: `unique`, `not_null`, `accepted_values`, `relationships` (integridade referencial) e
  `expression_is_true` / `approx_equal` próprios.
- Singulares: nenhuma unidade em dois contratos no mesmo dia; nenhum recebimento no caixa sem
  título válido.
- Reconciliação: `rec_row_counts` (chaves = válidas + quarentena) e `rec_financial_totals`
  (9 verificações entre camadas e métodos independentes) com teste `status = 'ok'`.

## Duplicidade de clientes

Não há unificação automática. `dq_customer_duplicate_candidates` aplica regras explicáveis
(mesmo CNPJ; nome normalizado similar + mesma cidade; nome muito similar em cidades diferentes) e
recomenda a revisão. CNPJs diferentes nunca geram confiança alta.
