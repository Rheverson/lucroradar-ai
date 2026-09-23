"use client";

import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, PageHeader, SectionTitle, StatusBadge, Tag } from "@/components/ui";
import { useFilters } from "@/lib/filters";

type TestSummary = {
  generated_at: string;
  suites: { name: string; tool: string; passed: number; failed: number; skipped: number; total: number; command: string }[];
};

const LAYERS = [
  { name: "raw", desc: "Arquivos CSV preservados: todas as colunas em texto + lote, arquivo, linha e hash.", items: "14 tabelas de origem" },
  { name: "staging", desc: "Tipagem, padronização e validação. Versão mais recente por chave; inválidos vão para a quarentena.", items: "stg_*_all → stg_*" },
  { name: "marts", desc: "Dimensões, fatos com granularidade declarada e marts de métricas.", items: "dim_*, fct_*, mart_*" },
  { name: "quality", desc: "Quarentena, problemas por tipo, candidatos a duplicidade e reconciliações.", items: "dq_*, rec_*" },
];

const FACTS = [
  ["fct_sales_order_lines", "uma linha de item de pedido de venda", "Receita reconhecida no faturamento; custo ausente = NULL"],
  ["fct_rental_revenue_monthly", "item de contrato (unidade física) × mês", "Receita pró-rata dia do valor mensal acordado"],
  ["fct_rental_logistics_costs", "custo logístico × unidade do contrato", "Reconhecido no mês em que ocorre"],
  ["fct_rental_maintenance_allocation", "mês × SKU × cliente", "Manutenção rateada por unidade-dia locada"],
  ["mart_contribution_monthly", "mês × negócio × cliente × produto × vendedor", "Fonte única de receita e margem"],
  ["fct_receivables", "título (parcela) a receber", "Situação na data de referência"],
  ["fct_receipts", "recebimento (entrada de caixa)", "Cópias idênticas eliminadas na staging"],
  ["mart_receivables_monthly", "fechamento mensal × cliente × negócio", "Vencido na data de cada fechamento"],
  ["mart_cash_monthly", "mês × direção × categoria", "Caixa realizado — não é lucro"],
  ["fct_equipment_unit_day", "unidade física × dia na frota", "Status: manutenção > locada > ociosa"],
  ["mart_fleet_utilization_monthly", "mês × SKU", "Utilização = locada ÷ (frota − manutenção)"],
  ["fct_order_stage_durations", "pedido × etapa", "Duração até a próxima etapa; abertas separadas"],
];

const METRICS = [
  ["Receita líquida", "Σ (quantidade × preço de lista − desconto) das vendas faturadas + receita de locação pró-rata dia. Sem impostos.", "Receita ≠ caixa"],
  ["Margem de contribuição", "Receita com custo conhecido − custo do produto − frete/logística − comissão − manutenção rateada.", "Não é lucro líquido"],
  ["Margem de contribuição (%)", "Margem ÷ receita com custo conhecido.", "Cobertura informada ao lado"],
  ["Cobertura de custo", "Receita com custo conhecido ÷ receita total.", "Custo ausente nunca vira zero"],
  ["Taxa de desconto", "Desconto ÷ receita bruta a preço de lista.", "Venda e locação"],
  ["Recebimentos", "Σ recebimentos no período (data do recebimento).", "Caixa realizado"],
  ["Valores vencidos", "Saldo em aberto com vencimento anterior à data do fechamento.", "Foto de cada fechamento"],
  ["Valores previstos", "Títulos em aberto a vencer nos próximos 90 dias.", "Sem ajuste de atraso"],
  ["Utilização da frota", "Unidade-dia locada ÷ (unidade-dia na frota − unidade-dia em manutenção).", "Manutenção fora do denominador"],
  ["Tempo por etapa", "Entrada na etapa seguinte − entrada na etapa (eventos).", "Etapas abertas separadas"],
];

function ArchitectureDiagram() {
  const box = "fill-[var(--surface)] stroke-[var(--border)]";
  const t = "fill-[var(--text)] text-[13px] font-semibold";
  const s = "fill-[var(--muted)] text-[11px]";
  const nodes = [
    { x: 10, y: 30, w: 170, title: "Gerador sintético", sub: "seed + data de referência", sub2: "lotes CSV + manifesto" },
    { x: 220, y: 30, w: 170, title: "Ingestão (Python)", sub: "hash por arquivo, lotes", sub2: "rejeições + logs" },
    { x: 430, y: 30, w: 170, title: "PostgreSQL", sub: "raw → staging → marts", sub2: "dbt Core + testes" },
    { x: 640, y: 30, w: 170, title: "API FastAPI", sub: "métricas, simulador", sub2: "alertas, copiloto" },
    { x: 640, y: 170, w: 170, title: "Next.js (web)", sub: "proxy /api no servidor", sub2: "sem segredos no navegador" },
    { x: 430, y: 170, w: 170, title: "Provedor de LLM", sub: "opcional, só no servidor", sub2: "ferramentas controladas" },
    { x: 220, y: 170, w: 170, title: "n8n", sub: "resumo e alertas", sub2: "execução manual" },
  ];
  // [x1, y1, x2, y2, tracejada]
  const arrows: [number, number, number, number, boolean][] = [
    [180, 65, 220, 65, false], [390, 65, 430, 65, false], [600, 65, 640, 65, false], // gerador → ingestão → banco → API
    [725, 100, 725, 170, false], // API → web
    [690, 100, 560, 170, true], // API → LLM (opcional)
    [360, 170, 650, 100, true], // n8n → API (resumo)
  ];
  return (
    <svg viewBox="0 0 820 260" className="h-auto w-full min-w-[640px]" role="img" aria-label="Arquitetura: gerador, ingestão, PostgreSQL com dbt, API, web, LLM opcional e n8n">
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--muted)" /></marker></defs>
      {arrows.map(([x1, y1, x2, y2, dashed], i) => <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--muted)" strokeWidth="1.5" markerEnd="url(#arr)" strokeDasharray={dashed ? "5 4" : undefined} />)}
      {nodes.map((n) => (
        <g key={n.title}>
          <rect x={n.x} y={n.y} width={n.w} height={70} rx={12} className={box} strokeWidth="1.5" />
          <text x={n.x + 14} y={n.y + 24} className={t}>{n.title}</text>
          <text x={n.x + 14} y={n.y + 43} className={s}>{n.sub}</text>
          <text x={n.x + 14} y={n.y + 58} className={s}>{n.sub2}</text>
        </g>
      ))}
      <text x={10} y={255} className={s}>Linhas tracejadas: integrações opcionais — a API chama o LLM só se houver chave; o n8n consulta o endpoint de resumo da API.</text>
    </svg>
  );
}

export default function BuiltPage() {
  const { meta } = useFilters();
  const [tests, setTests] = useState<TestSummary | null | "missing">(null);
  useEffect(() => {
    fetch("/test-summary.json", { cache: "no-store" }).then((r) => (r.ok ? r.json() : "missing")).then(setTests).catch(() => setTests("missing"));
  }, []);

  return (
    <>
      <PageHeader eyebrow="Engenharia" title="Como foi construído"
        description="Arquitetura, modelo de dados, dicionário de métricas e o resultado real dos testes. Tudo reproduzível localmente com Docker Compose."
        right={meta?.repository_url && (
          <a href={meta.repository_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2 text-sm font-medium hover:bg-surface-2">
            Repositório <ExternalLink className="size-4" aria-hidden />
          </a>
        )} />

      <Card>
        <SectionTitle title="Arquitetura" subtitle="Fluxo de dados do arquivo recebido até a resposta na tela. A API só lê o banco (sessão read-only)." />
        <div className="overflow-x-auto"><ArchitectureDiagram /></div>
      </Card>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1.4fr]">
        <Card>
          <SectionTitle title="Camadas do modelo" />
          <ol className="space-y-3">
            {LAYERS.map((l, i) => (
              <li key={l.name} className="flex gap-3">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">{i + 1}</span>
                <span><span className="font-mono text-sm font-semibold">{l.name}</span> <Tag>{l.items}</Tag><span className="mt-0.5 block text-sm text-ink-2">{l.desc}</span></span>
              </li>
            ))}
          </ol>
          <h3 className="mb-2 mt-6 text-sm font-semibold">Conceitos que não se misturam</h3>
          <ul className="grid grid-cols-2 gap-2 text-xs text-ink-2">
            {["Produto comercial (SKU) ≠ unidade física", "Venda ≠ locação", "Receita reconhecida ≠ recebimento", "Margem de contribuição ≠ lucro", "Vencido ≠ previsto", "Associação ≠ causa"].map((x) => <li key={x} className="rounded-lg bg-surface-2 p-2 ring-1 ring-line">{x}</li>)}
          </ul>
        </Card>
        <Card>
          <SectionTitle title="Tabelas fato e granularidade" />
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[560px] text-sm">
              <caption className="sr-only">Tabelas fato</caption>
              <thead className="bg-surface-2 text-xs text-muted"><tr><th scope="col" className="px-3 py-2 text-left">Tabela</th><th scope="col" className="px-3 py-2 text-left">Uma linha representa</th><th scope="col" className="px-3 py-2 text-left">Regra</th></tr></thead>
              <tbody>{FACTS.map(([n, g, r]) => <tr key={n} className="border-t border-line"><td className="px-3 py-2 font-mono text-xs">{n}</td><td className="px-3 py-2">{g}</td><td className="px-3 py-2 text-xs text-ink-2">{r}</td></tr>)}</tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <SectionTitle title="Dicionário de métricas" subtitle="Fórmulas completas, cobertura e limitações em docs/metrics.md." />
        <dl className="grid gap-3 md:grid-cols-2">
          {METRICS.map(([n, f, note]) => (
            <div key={n} className="rounded-xl bg-surface-2 p-4 ring-1 ring-line">
              <dt className="flex items-center justify-between gap-2 text-sm font-semibold">{n}<Tag>{note}</Tag></dt>
              <dd className="mt-1 text-sm text-ink-2">{f}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card className="mt-6">
        <SectionTitle title="Resumo dos testes" subtitle="Gerado pelo script scripts/collect_test_summary.py a partir dos relatórios reais das ferramentas. Nada é digitado à mão." />
        {tests === null ? <p className="text-sm text-muted">Carregando…</p> : tests === "missing" ? (
          <p className="text-sm text-muted">Resumo ainda não gerado nesta instalação. Rode <code>make test</code> para produzir <code>test-summary.json</code>.</p>
        ) : (
          <>
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {tests.suites.map((s) => (
                <li key={s.name} className="rounded-xl border border-line p-4">
                  <div className="flex items-center justify-between gap-2"><span className="text-sm font-semibold">{s.name}</span>
                    <StatusBadge tone={s.failed ? "bad" : "good"}>{s.failed ? `${s.failed} falhas` : "passou"}</StatusBadge></div>
                  <p className="num mt-2 text-2xl font-semibold">{s.passed}/{s.total}</p>
                  <p className="text-xs text-muted">{s.tool}{s.skipped ? ` · ${s.skipped} ignorados` : ""}</p>
                  <code className="mt-2 block truncate text-[11px] text-muted" title={s.command}>{s.command}</code>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted">Gerado em {new Date(tests.generated_at).toLocaleString("pt-BR")}.</p>
          </>
        )}
      </Card>
    </>
  );
}
