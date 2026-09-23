"use client";

import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ReferenceArea, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { brl, brlShort, hours, monthLabel, pct, signedBrl } from "@/lib/format";
import type { Bridge, SeriesPoint } from "@/lib/types";

const AXIS = { fontSize: 11, fill: "var(--muted)" };
const GRID = { stroke: "var(--grid)", strokeDasharray: "0", vertical: false };

type TipRow = { name: string; value: string; color?: string };

function TipBox({ title, rows }: { title: string; rows: TipRow[] }) {
  return (
    <div className="min-w-44 rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-ink">{title}</p>
      {rows.map((r) => (
        <p key={r.name} className="flex items-center justify-between gap-4 text-ink-2">
          <span className="flex items-center gap-1.5">
            {r.color && <span className="inline-block size-2 rounded-sm" style={{ background: r.color }} />}
            {r.name}
          </span>
          <span className="num font-medium text-ink">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-4 text-xs text-ink-2" aria-label="Legenda">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-3 rounded-sm" style={{ background: i.color, opacity: i.dashed ? 0.45 : 1 }} aria-hidden />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

function periodBounds(series: SeriesPoint[]) {
  const inP = series.filter((s) => s.in_period);
  return inP.length ? { x1: inP[0].month, x2: inP[inP.length - 1].month } : null;
}

/** Receita mensal por linha de negócio (barras empilhadas), destacando o período selecionado. */
export function RevenueChart({ series }: { series: SeriesPoint[] }) {
  const b = periodBounds(series);
  return (
    <div>
      <Legend items={[{ label: "Venda", color: "var(--series-1)" }, { label: "Locação", color: "var(--series-3)" }]} />
      <div className="h-64" role="img" aria-label="Receita líquida mensal por linha de negócio">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="22%">
            <CartesianGrid {...GRID} />
            {b && <ReferenceArea x1={b.x1} x2={b.x2} fill="var(--accent)" fillOpacity={0.07} ifOverflow="extendDomain" />}
            <XAxis dataKey="month" tickFormatter={monthLabel} tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval="preserveStartEnd" minTickGap={16} />
            <YAxis tickFormatter={(v) => brlShort(v)} tick={AXIS} tickLine={false} axisLine={false} width={64} />
            <Tooltip
              cursor={{ fill: "var(--grid)", opacity: 0.5 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TipBox
                    title={monthLabel(String(payload[0].payload.month))}
                    rows={[
                      { name: "Venda", value: brl(payload[0].payload.sale_revenue), color: "var(--series-1)" },
                      { name: "Locação", value: brl(payload[0].payload.rental_revenue), color: "var(--series-3)" },
                      { name: "Total", value: brl(payload[0].payload.net_revenue) },
                    ]}
                  />
                ) : null
              }
            />
            <Bar dataKey="sale_revenue" stackId="r" fill="var(--series-1)" stroke="var(--surface)" strokeWidth={1} isAnimationActive={false}>
              {series.map((s) => <Cell key={s.month} fillOpacity={s.in_period ? 1 : 0.45} />)}
            </Bar>
            <Bar dataKey="rental_revenue" stackId="r" fill="var(--series-3)" stroke="var(--surface)" strokeWidth={1} radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {series.map((s) => <Cell key={s.month} fillOpacity={s.in_period ? 1 : 0.45} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Série única em linha (margem %, desconto %, vencidos), eixo próprio. */
export function LineSeries({
  series, dataKey, label, format, color = "var(--series-1)", height = 176,
}: {
  series: SeriesPoint[]; dataKey: keyof SeriesPoint; label: string; format: (v: number) => string; color?: string; height?: number;
}) {
  const b = periodBounds(series);
  return (
    <div style={{ height }} role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid {...GRID} />
          {b && <ReferenceArea x1={b.x1} x2={b.x2} fill="var(--accent)" fillOpacity={0.07} />}
          <XAxis dataKey="month" tickFormatter={monthLabel} tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval="preserveStartEnd" minTickGap={20} />
          <YAxis tickFormatter={(v) => format(v)} tick={AXIS} tickLine={false} axisLine={false} width={64} domain={["auto", "auto"]} />
          <Tooltip
            cursor={{ stroke: "var(--muted)", strokeWidth: 1 }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TipBox title={monthLabel(String(payload[0].payload.month))} rows={[{ name: label, value: format(Number(payload[0].value)), color }]} />
              ) : null
            }
          />
          <Line type="monotone" dataKey={dataKey as string} stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Sparkline({ values, color = "var(--series-1)" }: { values: number[]; color?: string }) {
  const data = values.map((v, i) => ({ i, v }));
  return (
    <div className="h-9 w-full" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 2, left: 2, bottom: 4 }}>
          <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.75} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const SHORT: Record<string, string> = { volume: "Volume/mix", price: "Preço", discount: "Desconto", cost: "Custo" };

/** Ponte de margem em cascata: margem anterior → efeitos → margem atual. */
export function BridgeChart({ bridge }: { bridge: Bridge }) {
  let running = bridge.margin_previous;
  const rows: { name: string; base: number; value: number; kind: "total" | "up" | "down"; raw: number }[] = [
    { name: "Anterior", base: 0, value: bridge.margin_previous, kind: "total", raw: bridge.margin_previous },
  ];
  for (const e of bridge.effects) {
    const start = running;
    running += e.value;
    rows.push({ name: SHORT[e.key] ?? e.label, base: Math.min(start, running), value: Math.abs(e.value), kind: e.value >= 0 ? "up" : "down", raw: e.value });
  }
  rows.push({ name: "Atual", base: 0, value: bridge.margin_current, kind: "total", raw: bridge.margin_current });
  const color = { total: "var(--muted)", up: "var(--series-1)", down: "var(--series-2)" };
  // eixo começa perto do menor nível da cascata para os efeitos ficarem legíveis (totais truncados)
  const levels = rows.flatMap((r) => (r.kind === "total" ? [r.value] : [r.base]));
  const lo = Math.floor((Math.min(...levels) * 0.9) / 100000) * 100000;
  for (const r of rows) if (r.kind === "total") { r.base = lo; r.value = r.value - lo; }
  return (
    <div>
      <Legend items={[{ label: "Aumentou a margem", color: "var(--series-1)" }, { label: "Reduziu a margem", color: "var(--series-2)" }, { label: "Total do período", color: "var(--muted)" }]} />
      <div className="h-72" role="img" aria-label="Ponte de margem de contribuição entre os períodos">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 22, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="name" tick={{ ...AXIS, fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval={0} />
            <YAxis tickFormatter={(v) => brlShort(v)} tick={AXIS} tickLine={false} axisLine={false} width={64} domain={[lo, "auto"]} allowDataOverflow />
            <Tooltip
              cursor={{ fill: "var(--grid)", opacity: 0.5 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TipBox title={String(payload[0].payload.name)} rows={[{ name: payload[0].payload.kind === "total" ? "Margem" : "Efeito", value: payload[0].payload.kind === "total" ? brl(payload[0].payload.raw) : signedBrl(payload[0].payload.raw) }]} />
                ) : null
              }
            />
            <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="value" stackId="w" radius={[4, 4, 4, 4]} isAnimationActive={false}>
              {rows.map((r) => <Cell key={r.name} fill={color[r.kind]} />)}
              <LabelList dataKey="raw" position="top" formatter={(v: unknown) => brlShort(Number(v))} style={{ fontSize: 11, fill: "var(--text-2)" }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function CashChart({ series }: { series: { month: string; inflow: number; outflow: number; net: number; in_period: boolean }[] }) {
  return (
    <div>
      <Legend items={[{ label: "Entradas (recebimentos)", color: "var(--series-1)" }, { label: "Saídas (pagamentos)", color: "var(--series-2)" }]} />
      <div className="h-60" role="img" aria-label="Entradas e saídas de caixa por mês">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={2}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="month" tickFormatter={monthLabel} tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--border)" }} minTickGap={16} />
            <YAxis tickFormatter={(v) => brlShort(v)} tick={AXIS} tickLine={false} axisLine={false} width={64} />
            <Tooltip
              cursor={{ fill: "var(--grid)", opacity: 0.5 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TipBox title={monthLabel(String(payload[0].payload.month))} rows={[
                    { name: "Entradas", value: brl(payload[0].payload.inflow), color: "var(--series-1)" },
                    { name: "Saídas", value: brl(payload[0].payload.outflow), color: "var(--series-2)" },
                    { name: "Saldo do mês", value: signedBrl(payload[0].payload.net) },
                  ]} />
                ) : null
              }
            />
            <Bar dataKey="inflow" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {series.map((s) => <Cell key={s.month} fillOpacity={s.in_period ? 1 : 0.45} />)}
            </Bar>
            <Bar dataKey="outflow" fill="var(--series-2)" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {series.map((s) => <Cell key={s.month} fillOpacity={s.in_period ? 1 : 0.45} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Barras horizontais: valor atual com marcador do período de comparação. */
export function CompareBars({
  rows, format, label, max,
}: {
  rows: { name: string; sub?: string; current: number | null; previous: number | null }[];
  format: (v: number | null) => string; label: string; max?: number;
}) {
  const top = max ?? Math.max(1, ...rows.flatMap((r) => [r.current ?? 0, r.previous ?? 0]));
  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-4 text-xs text-ink-2" aria-label="Legenda">
        <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-3 rounded-sm bg-[var(--series-1)]" aria-hidden />Período selecionado</li>
        <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-0.5 bg-ink" aria-hidden />Comparação</li>
      </ul>
      <ul className="space-y-2.5" aria-label={label}>
        {rows.map((r) => (
          <li key={r.name} className="grid grid-cols-[minmax(0,9rem)_1fr_4.5rem] items-center gap-3 text-sm sm:grid-cols-[minmax(0,14rem)_1fr_5rem]">
            <span className="min-w-0 truncate text-ink-2" title={r.sub ? `${r.name} — ${r.sub}` : r.name}>
              <span className="font-medium text-ink">{r.name}</span>
              {r.sub && <span className="hidden text-muted sm:inline"> · {r.sub}</span>}
            </span>
            <span className="relative h-3 rounded-full bg-surface-2 ring-1 ring-line">
              <span className="absolute inset-y-0 left-0 rounded-full bg-[var(--series-1)]" style={{ width: `${Math.min(100, ((r.current ?? 0) / top) * 100)}%` }} />
              {r.previous != null && (
                <span className="absolute -top-0.5 h-4 w-0.5 bg-ink" style={{ left: `calc(${Math.min(100, (r.previous / top) * 100)}% - 1px)` }} title={`Comparação: ${format(r.previous)}`} />
              )}
            </span>
            <span className="num text-right text-sm font-medium text-ink">{format(r.current)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export const formatters = { brl, brlShort, pct, hours };
