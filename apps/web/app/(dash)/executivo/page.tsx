"use client";

import { ArrowRight, Bot, SlidersHorizontal, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AlertList } from "@/components/alerts";
import { BridgeChart, CashChart, LineSeries, RevenueChart } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { FilterBar } from "@/components/filter-bar";
import { KpiCard } from "@/components/kpi";
import { Card, EmptyState, ErrorState, LoadingBlock, PageHeader, SectionTitle, Skeleton, Tag, cx } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { brl, brlShort, dateBR, pct, signedBrl } from "@/lib/format";
import type { Alert, Bridge, BridgeGroup, SeriesPoint, Summary } from "@/lib/types";

type Cash = { series: { month: string; inflow: number; outflow: number; net: number; in_period: boolean }[]; forecast: { week_start: string; direction: string; amount: number }[]; note: string; forecast_note: string };
type Receivables = { aging: { aging_bucket: string; open_amount: number; titles: number }[]; top_overdue_customers: { customer_id: string; customer_name: string; segment: string; overdue: number; titles: number; max_days_overdue: number }[]; as_of: string; note: string; filters_not_applied: string[] };

const DIMS = [
  { key: "product_line", label: "Linha de produto" },
  { key: "salesperson_id", label: "Vendedor" },
  { key: "region", label: "Região" },
  { key: "business_line", label: "Negócio" },
] as const;

function BridgeSection({ q }: { q: string }) {
  const bridge = useApi<Bridge>(q ? `v1/executive/margin-bridge?${q}` : null);
  const [dim, setDim] = useState<(typeof DIMS)[number]["key"]>("product_line");
  return (
    <Card id="ponte-de-margem" className="scroll-mt-20">
      <SectionTitle
        title="O que explica a variação da margem"
        subtitle="Ponte de margem de contribuição entre o período de comparação e o selecionado. Os efeitos somam exatamente a variação; mostram contribuição aritmética, não causa."
      />
      {bridge.loading && !bridge.data ? <Skeleton className="h-72" /> : bridge.error ? (
        <ErrorState message={bridge.error.message} onRetry={bridge.reload} />
      ) : bridge.data && !bridge.data.available ? (
        <EmptyState title="Comparação indisponível" hint={bridge.data.reason} />
      ) : bridge.data ? (
        <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
          <div>
            <BridgeChart bridge={bridge.data} />
            <p className="mt-2 text-xs text-muted">
              Margem %: {pct(bridge.data.margin_pct_previous)} → {pct(bridge.data.margin_pct_current)} · {bridge.data.method}
            </p>
          </div>
          <div>
            <div role="tablist" aria-label="Detalhar efeitos por" className="mb-3 flex flex-wrap gap-1.5">
              {DIMS.map((d) => (
                <button key={d.key} role="tab" aria-selected={dim === d.key} onClick={() => setDim(d.key)}
                  className={cx("rounded-lg px-3 py-1.5 text-xs font-medium", dim === d.key ? "bg-brand text-white dark:text-[#0a111e]" : "bg-surface-2 text-ink-2 ring-1 ring-line hover:text-ink")}>
                  {d.label}
                </button>
              ))}
            </div>
            <DataTable<BridgeGroup>
              caption="Efeitos na margem por dimensão"
              rows={bridge.data.by[dim]}
              rowKey={(r) => r.name}
              initialSort={{ key: "delta", dir: "asc" }}
              maxHeight={300}
              columns={[
                { key: "name", header: DIMS.find((d) => d.key === dim)!.label, render: (r) => <span className="font-medium">{r.name}</span> },
                { key: "volume", header: "Volume/mix", align: "right", sortValue: (r) => r.volume, render: (r) => signedBrl(r.volume), hideOnMobile: true },
                { key: "price", header: "Preço", align: "right", sortValue: (r) => r.price, render: (r) => signedBrl(r.price), hideOnMobile: true },
                { key: "discount", header: "Desconto", align: "right", sortValue: (r) => r.discount, render: (r) => <span className={r.discount < 0 ? "text-bad" : ""}>{signedBrl(r.discount)}</span> },
                { key: "cost", header: "Custo", align: "right", sortValue: (r) => r.cost, render: (r) => <span className={r.cost < 0 ? "text-bad" : ""}>{signedBrl(r.cost)}</span> },
                { key: "delta", header: "Variação", align: "right", sortValue: (r) => r.delta, render: (r) => <strong>{signedBrl(r.delta)}</strong> },
              ]}
            />
          </div>
        </div>
      ) : null}
    </Card>
  );
}

export default function ExecutivePage() {
  const { query: q, withQuery } = useFilters();
  const summary = useApi<Summary>(q ? `v1/executive/summary?${q}` : null);
  const ts = useApi<{ series: SeriesPoint[] }>(q ? `v1/executive/timeseries?${q}` : null);
  const alerts = useApi<{ alerts: Alert[]; note: string }>(q ? `v1/alerts?${q}` : null);
  const cash = useApi<Cash>(q ? `v1/finance/cash?${q}` : null);
  const recv = useApi<Receivables>(q ? `v1/finance/receivables?${q}` : null);
  const s = summary.data;
  const series = ts.data?.series ?? [];
  const inP = series.filter((x) => x.in_period);

  return (
    <>
      <PageHeader
        eyebrow="Visão executiva"
        title="Estou vendendo mais. Por que o dinheiro não está sobrando?"
        description={s ? <>Período <strong>{s.filters.period.label}</strong> comparado a <strong>{s.filters.comparison.label}</strong>. Receita, margem de contribuição e caixa são medidas diferentes — e é na diferença entre elas que a resposta aparece.</> : "Receita, margem de contribuição e caixa lado a lado."}
      />
      <FilterBar />

      {summary.error ? (
        <ErrorState message={summary.error.message} onRetry={summary.reload} />
      ) : !s ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-44" />)}</div>
      ) : (
        <div className={cx("grid gap-4 sm:grid-cols-2 xl:grid-cols-4", summary.loading && "opacity-60 transition-opacity")} aria-busy={summary.loading}>
          <KpiCard label="Receita líquida" value={brl(s.kpis.net_revenue.current)} cmp={s.kpis.net_revenue}
            spark={series.map((x) => x.net_revenue)} secondary={<>Venda {brlShort(s.breakdown.sale_revenue)} · Locação {brlShort(s.breakdown.rental_revenue)}</>}
            hint={s.definitions.net_revenue} />
          <KpiCard label="Margem de contribuição" value={pct(s.kpis.margin_pct.current)} cmp={s.kpis.margin_pct}
            spark={series.map((x) => x.margin_pct ?? 0)} sparkColor="var(--series-3)"
            secondary={<>{brl(s.kpis.contribution_margin.current)} · cobertura de custo {pct(s.kpis.cost_coverage.current)}</>}
            hint={s.definitions.contribution_margin} />
          <KpiCard label="Recebimentos (caixa)" value={brl(s.kpis.receipts.current)} cmp={s.kpis.receipts}
            spark={series.map((x) => x.receipts)}
            secondary={<>Recebido ÷ receita: {pct(s.kpis.cash_conversion.current)} (antes {pct(s.kpis.cash_conversion.previous)})</>}
            hint={s.definitions.receipts} />
          <KpiCard label="Valores vencidos" value={brl(s.kpis.overdue.current)} cmp={s.kpis.overdue} goodWhen="down"
            spark={series.map((x) => x.overdue)} sparkColor="var(--series-2)"
            secondary={<>No fechamento de {dateBR(s.overdue_snapshot_date)} · em aberto {brlShort(s.kpis.open_receivables.current)}</>}
            hint={s.definitions.overdue} />
        </div>
      )}
      {s && s.filters_not_applied.receivables.length > 0 && (
        <p className="mt-2 text-xs text-muted">Recebimentos e vencidos não se aplicam ao filtro de {s.filters_not_applied.receivables.join(", ")} (títulos são por cliente).</p>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card>
          <SectionTitle title="Receita cresce; margem não acompanha" subtitle="Receita mensal por linha de negócio (período selecionado em destaque) e margem de contribuição % no mesmo intervalo, em eixos separados." />
          {ts.error ? <ErrorState message={ts.error.message} onRetry={ts.reload} /> : !ts.data ? <Skeleton className="h-96" /> : series.length === 0 ? <EmptyState /> : (
            <>
              <RevenueChart series={series} />
              <h3 className="mb-1 mt-5 text-sm font-medium text-ink-2">Margem de contribuição (%)</h3>
              <LineSeries series={series} dataKey="margin_pct" label="Margem de contribuição (%)" format={(v) => pct(v, 0)} color="var(--series-3)" height={150} />
              <h3 className="mb-1 mt-4 text-sm font-medium text-ink-2">Taxa de desconto (%)</h3>
              <LineSeries series={series} dataKey="discount_rate" label="Taxa de desconto (%)" format={(v) => pct(v, 1)} color="var(--series-2)" height={130} />
              {inP.length > 0 && <p className="mt-2 text-xs text-muted">Dados mensais completos: <Link className="underline" href={withQuery("/como-foi-construido")}>ver dicionário de métricas</Link>.</p>}
            </>
          )}
        </Card>
        <Card>
          <SectionTitle title="Alertas com evidências" subtitle={alerts.data?.note ?? "Regras determinísticas sobre as métricas."} />
          {alerts.error ? <ErrorState message={alerts.error.message} onRetry={alerts.reload} /> : !alerts.data ? <LoadingBlock rows={5} /> : <AlertList alerts={alerts.data.alerts} compact />}
        </Card>
      </div>

      <div className="mt-6"><BridgeSection q={q} /></div>

      <Card id="recebiveis" className="mt-6 scroll-mt-20">
        <SectionTitle title="Caixa: onde a receita fica presa" subtitle="Entradas e saídas realizadas por mês (empresa inteira) e saldo vencido no fechamento de cada mês." />
        <div className="grid gap-6 xl:grid-cols-2">
          <div>
            {cash.error ? <ErrorState message={cash.error.message} onRetry={cash.reload} /> : !cash.data ? <Skeleton className="h-60" /> : <CashChart series={cash.data.series} />}
            <p className="mt-2 text-xs text-muted">{cash.data?.note}</p>
          </div>
          <div>
            <h3 className="mb-1 text-sm font-medium text-ink-2">Saldo vencido no fechamento do mês</h3>
            {series.length ? <LineSeries series={series} dataKey="overdue" label="Saldo vencido" format={(v) => brlShort(v)} color="var(--series-2)" height={220} /> : <Skeleton className="h-56" />}
          </div>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <div>
            <h3 className="mb-2 text-sm font-medium text-ink-2">Aging na data de referência</h3>
            {recv.error ? <ErrorState message={recv.error.message} /> : !recv.data ? <LoadingBlock /> : (
              <ul className="space-y-1.5 text-sm">
                {recv.data.aging.map((a) => (
                  <li key={a.aging_bucket} className="flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2 ring-1 ring-line">
                    <span className="text-ink-2">{a.aging_bucket} <span className="text-xs text-muted">({a.titles} títulos)</span></span>
                    <span className="num font-medium">{brl(a.open_amount)}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted">{recv.data?.note}</p>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium text-ink-2">Clientes com maior saldo vencido</h3>
            {recv.data && (
              <DataTable
                caption="Clientes com maior saldo vencido"
                rows={recv.data.top_overdue_customers}
                rowKey={(r) => r.customer_id}
                columns={[
                  { key: "customer_name", header: "Cliente", render: (r) => <Link className="font-medium hover:underline" href={withQuery("/clientes-produtos", { customer: r.customer_id })}>{r.customer_name}</Link> },
                  { key: "segment", header: "Segmento", render: (r) => <Tag>{r.segment}</Tag>, hideOnMobile: true },
                  { key: "overdue", header: "Vencido", align: "right", sortValue: (r) => r.overdue, render: (r) => brl(r.overdue) },
                  { key: "max_days_overdue", header: "Maior atraso", align: "right", sortValue: (r) => r.max_days_overdue, render: (r) => `${r.max_days_overdue} dias` },
                ]}
              />
            )}
          </div>
        </div>
      </Card>

      <nav aria-label="Próximos passos da investigação" className="mt-6 grid gap-3 sm:grid-cols-3">
        {[
          { href: "/clientes-produtos", icon: Users, title: "Investigar clientes e produtos", text: "Margem, descontos e custos até o registro de origem." },
          { href: "/copiloto", icon: Bot, title: "Perguntar ao copiloto", text: "Respostas com evidências, filtros e limitações." },
          { href: "/simulador", icon: SlidersHorizontal, title: "Simular e propor ações", text: "Desconto, utilização e prazo de recebimento." },
        ].map(({ href, icon: Icon, title, text }) => (
          <Link key={href} href={withQuery(href)} className="group flex items-start gap-3 rounded-2xl border border-line bg-surface p-4 hover:border-brand-2">
            <Icon className="mt-0.5 size-5 text-accent" aria-hidden />
            <span className="flex-1">
              <span className="block text-sm font-semibold text-ink">{title}</span>
              <span className="block text-xs text-muted">{text}</span>
            </span>
            <ArrowRight className="size-4 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        ))}
      </nav>
    </>
  );
}
