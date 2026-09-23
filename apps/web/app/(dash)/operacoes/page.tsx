"use client";

import { CompareBars, LineSeries } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { FilterBar } from "@/components/filter-bar";
import { Card, EmptyState, ErrorState, LoadingBlock, PageHeader, SectionTitle, StatusBadge, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { brl, dateBR, hours, num, pct } from "@/lib/format";
import type { SeriesPoint } from "@/lib/types";

type Util = {
  by_sku: { sku: string; description: string; product_line: string; units: number; units_previous: number | null; owned_days: number; maintenance_days: number; available_days: number; rented_days: number; idle_days: number; idle_depreciation: number; time_utilization: number | null; time_utilization_previous: number | null; maintenance_share: number | null }[];
  trend: { month: string; time_utilization: number; maintenance_share: number; idle_depreciation: number }[];
  totals: { time_utilization: number | null; idle_depreciation: number; rented_days: number; available_days: number; maintenance_days: number; owned_days: number };
  definition: string; filters_not_applied: string[];
};
type Units = { rows: { unit_id: string; sku: string; product_line: string; acquisition_date: string; branch: string; owned_days_90d: number; rented_days_90d: number; idle_days_90d: number; maintenance_days_90d: number; last_rented_day: string | null; status_at_reference: string; utilization_90d: number | null }[]; note: string };
type Maint = { open: { maintenance_id: string; unit_id: string; sku: string; maintenance_type: string; opened_at: string; days_in_maintenance: number; description: string }[]; stats: { maintenance_type: string; orders: number; cost: number | null; median_days: number }[]; note: string };
type Stages = {
  stages: { stage_code: string; stage_label: string; n: number; open_n: number; median_hours: number | null; p90_hours: number | null; median_hours_previous: number | null }[];
  open_orders: { order_id: string; order_type: string; customer_id: string; segment: string; stage_label: string; order_value: number | null; hours_in_current_stage: number; order_date: string }[];
  status: { completed: number; open: number; cancelled: number };
  credit_review_by_value: { period: string; faixa: string; n: number; median_hours: number }[];
  definition: string; filters_not_applied: string[];
};

const STATUS_LABEL: Record<string, string> = { rented: "Locada", idle: "Disponível (ociosa)", maintenance: "Em manutenção" };

export default function OperationsPage() {
  const { query: q } = useFilters();
  const util = useApi<Util>(q ? `v1/operations/utilization?${q}` : null);
  const units = useApi<Units>(q ? `v1/operations/units?${q}&limit=25` : null);
  const maint = useApi<Maint>(q ? `v1/operations/maintenance?${q}` : null);
  const stages = useApi<Stages>(q ? `v1/operations/stages?${q}` : null);
  const trend = (util.data?.trend ?? []).map((t) => ({ ...t, in_period: false })) as unknown as SeriesPoint[];

  return (
    <>
      <PageHeader eyebrow="Operações" title="Operações e locações"
        description="Unidades físicas da frota, utilização com denominador explícito, manutenção e tempo por etapa dos pedidos a partir dos eventos registrados." />
      <FilterBar note="Frota: aplica-se apenas o filtro de linha de produto (unidades não pertencem a um cliente). Etapas de pedidos: negócio, segmento e região." />

      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <Card>
          <SectionTitle title="Utilização da frota por produto" subtitle={util.data?.definition} />
          {util.error ? <ErrorState message={util.error.message} onRetry={util.reload} /> : !util.data ? <LoadingBlock rows={8} /> : util.data.by_sku.length === 0 ? <EmptyState hint="Nenhum produto de locação no filtro atual." /> : (
            <>
              <div className="mb-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                {[
                  ["Utilização", pct(util.data.totals.time_utilization)],
                  ["Unidade-dia locada", num(util.data.totals.rented_days)],
                  ["Em manutenção", pct(util.data.totals.maintenance_days / Math.max(1, util.data.totals.owned_days))],
                  ["Capital parado (estim.)", brl(util.data.totals.idle_depreciation)],
                ].map(([k, v]) => <div key={k} className="rounded-xl bg-surface-2 p-3 ring-1 ring-line"><p className="text-xs text-muted">{k}</p><p className="num mt-0.5 text-lg font-semibold">{v}</p></div>)}
              </div>
              <CompareBars label="Utilização por produto" format={(v) => pct(v, 0)} max={1}
                rows={[...util.data.by_sku].sort((a, b) => (a.time_utilization ?? 0) - (b.time_utilization ?? 0)).map((r) => ({
                  name: r.sku, sub: `${r.description} · ${r.units} un.${r.units_previous && r.units_previous !== r.units ? ` (antes ${r.units_previous})` : ""}`,
                  current: r.time_utilization, previous: r.time_utilization_previous }))} />
              <p className="mt-3 text-xs text-muted">Capital parado = depreciação linear (60 meses) dos dias ociosos: estimativa gerencial, não contábil.</p>
            </>
          )}
        </Card>
        <Card>
          <SectionTitle title="Tendência mensal" subtitle="Utilização da frota filtrada, janela completa." />
          {trend.length ? <LineSeries series={trend} dataKey={"time_utilization" as keyof SeriesPoint} label="Utilização mensal" format={(v) => pct(v, 0)} height={220} /> : <LoadingBlock />}
          <h3 className="mb-1 mt-4 text-sm font-medium text-ink-2">Participação da manutenção nos dias de frota</h3>
          {trend.length ? <LineSeries series={trend} dataKey={"maintenance_share" as keyof SeriesPoint} label="Dias em manutenção ÷ dias na frota" format={(v) => pct(v, 0)} color="var(--series-2)" height={160} /> : null}
        </Card>
      </div>

      <Card className="mt-6">
        <SectionTitle title="Unidades com menor utilização (90 dias)" subtitle={units.data?.note} />
        {units.error ? <ErrorState message={units.error.message} /> : !units.data ? <LoadingBlock rows={6} /> : (
          <DataTable caption="Unidades físicas com menor utilização" rows={units.data.rows} rowKey={(r) => r.unit_id} maxHeight={420}
            columns={[
              { key: "unit_id", header: "Unidade", render: (r) => <span className="font-mono text-xs">{r.unit_id}</span> },
              { key: "sku", header: "Produto", render: (r) => <span>{r.sku} <span className="text-xs text-muted">· {r.product_line}</span></span> },
              { key: "acquisition_date", header: "Aquisição", render: (r) => dateBR(r.acquisition_date), sortValue: (r) => r.acquisition_date, hideOnMobile: true },
              { key: "utilization_90d", header: "Utilização", align: "right", sortValue: (r) => r.utilization_90d, render: (r) => pct(r.utilization_90d, 0) },
              { key: "idle_days_90d", header: "Dias ociosa", align: "right", sortValue: (r) => r.idle_days_90d, render: (r) => num(r.idle_days_90d) },
              { key: "last_rented_day", header: "Última locação", render: (r) => dateBR(r.last_rented_day), hideOnMobile: true },
              { key: "status_at_reference", header: "Situação na referência", render: (r) => <StatusBadge tone={r.status_at_reference === "rented" ? "good" : r.status_at_reference === "maintenance" ? "warn" : "info"}>{STATUS_LABEL[r.status_at_reference] ?? "—"}</StatusBadge> },
            ]} />
        )}
      </Card>

      <Card id="manutencao" className="mt-6 scroll-mt-20">
        <SectionTitle title="Equipamentos em manutenção" subtitle={maint.data?.note} />
        {maint.error ? <ErrorState message={maint.error.message} /> : !maint.data ? <LoadingBlock /> : (
          <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
            <ul className="space-y-2 text-sm">
              {maint.data.stats.map((s) => (
                <li key={s.maintenance_type} className="rounded-xl bg-surface-2 p-3 ring-1 ring-line">
                  <p className="font-medium">{s.maintenance_type === "preventive" ? "Preventiva" : "Corretiva"} <span className="text-muted">· {num(s.orders)} ordens no período</span></p>
                  <p className="text-xs text-muted">Mediana {num(s.median_days)} dias · custo conhecido {brl(s.cost)}</p>
                </li>
              ))}
            </ul>
            {maint.data.open.length === 0 ? <EmptyState title="Nenhuma manutenção aberta" /> : (
              <DataTable caption="Manutenções abertas" rows={maint.data.open} rowKey={(r) => r.maintenance_id} maxHeight={360} initialSort={{ key: "days_in_maintenance", dir: "desc" }}
                columns={[
                  { key: "unit_id", header: "Unidade", render: (r) => <span className="font-mono text-xs">{r.unit_id} · {r.sku}</span> },
                  { key: "maintenance_type", header: "Tipo", render: (r) => <Tag>{r.maintenance_type === "preventive" ? "Preventiva" : "Corretiva"}</Tag> },
                  { key: "opened_at", header: "Aberta em", render: (r) => dateBR(r.opened_at), hideOnMobile: true },
                  { key: "days_in_maintenance", header: "Dias parada", align: "right", sortValue: (r) => r.days_in_maintenance, render: (r) => r.days_in_maintenance >= 30 ? <StatusBadge tone="bad">{r.days_in_maintenance} dias</StatusBadge> : `${r.days_in_maintenance} dias` },
                  { key: "description", header: "Descrição", className: "text-xs text-ink-2", hideOnMobile: true },
                ]} />
            )}
          </div>
        )}
      </Card>

      <Card id="etapas" className="mt-6 scroll-mt-20">
        <SectionTitle title="Tempo por etapa dos pedidos" subtitle={stages.data?.definition} />
        {stages.error ? <ErrorState message={stages.error.message} /> : !stages.data ? <LoadingBlock rows={6} /> : (
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <CompareBars label="Mediana de horas por etapa" format={(v) => hours(v)}
                rows={stages.data.stages.map((s) => ({ name: s.stage_label, sub: `p90 ${hours(s.p90_hours)} · ${num(s.n)} pedidos`, current: s.median_hours, previous: s.median_hours_previous }))} />
              <div className="mt-5 grid grid-cols-3 gap-2 text-center text-sm">
                {[["Concluídos", stages.data.status.completed, "good"], ["Em aberto", stages.data.status.open, "warn"], ["Cancelados", stages.data.status.cancelled, "info"]].map(([l, v]) => (
                  <div key={l as string} className="rounded-xl bg-surface-2 p-3 ring-1 ring-line"><p className="text-xs text-muted">{l}</p><p className="num text-lg font-semibold">{num(v as number)}</p></div>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">Pedidos criados no período. Abertos = sem entrega nem cancelamento até a data de referência.</p>
              <h3 className="mb-2 mt-5 text-sm font-semibold">Análise de crédito por valor do pedido</h3>
              <DataTable caption="Análise de crédito por faixa de valor" rows={stages.data.credit_review_by_value} rowKey={(r) => r.period + r.faixa}
                columns={[
                  { key: "faixa", header: "Faixa" },
                  { key: "period", header: "Período", render: (r) => (r.period === "current" ? "Selecionado" : "Comparação") },
                  { key: "n", header: "Pedidos", align: "right", render: (r) => num(r.n) },
                  { key: "median_hours", header: "Mediana", align: "right", render: (r) => hours(r.median_hours) },
                ]} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">Pedidos abertos há mais tempo na etapa atual</h3>
              <DataTable caption="Pedidos abertos" rows={stages.data.open_orders} rowKey={(r) => r.order_id} maxHeight={520}
                columns={[
                  { key: "order_id", header: "Pedido", render: (r) => <span className="font-mono text-xs">{r.order_id}</span> },
                  { key: "order_type", header: "Tipo", render: (r) => <Tag>{r.order_type === "sale" ? "Venda" : "Locação"}</Tag> },
                  { key: "stage_label", header: "Etapa atual" },
                  { key: "order_value", header: "Valor", align: "right", render: (r) => brl(r.order_value), hideOnMobile: true },
                  { key: "hours_in_current_stage", header: "Na etapa", align: "right", sortValue: (r) => r.hours_in_current_stage, render: (r) => hours(r.hours_in_current_stage) },
                ]} />
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
