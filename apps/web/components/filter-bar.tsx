"use client";

import { RotateCcw } from "lucide-react";
import { addMonths, PRESETS, useFilters, type FilterValues } from "@/lib/filters";
import { monthLabel } from "@/lib/format";
import { cx } from "./ui";

function months(start: string, end: string) {
  const out: string[] = [];
  for (let m = start; m <= end; m = addMonths(m, 1)) out.push(m);
  return out;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs font-medium text-muted">
      {label}
      {children}
    </label>
  );
}

const selectCls =
  "h-9 w-full min-w-0 rounded-lg border border-line bg-surface px-2.5 text-sm text-ink shadow-sm focus:border-[var(--focus)]";

/** Filtros compartilhados entre telas (ficam na URL). `show` limita os campos relevantes. */
export function FilterBar({
  show = ["business_line", "segment", "region", "product_line"],
  note,
}: {
  show?: ("business_line" | "segment" | "region" | "product_line")[];
  note?: string;
}) {
  const { meta, values, setFilters } = useFilters();
  if (!meta) {
    return <div className="mb-6 h-[74px] rounded-2xl border border-line bg-surface skeleton" aria-hidden />;
  }
  const all = months(meta.window_start, meta.window_end);
  const set = (k: keyof FilterValues) => (e: React.ChangeEvent<HTMLSelectElement>) => setFilters({ [k]: e.target.value });
  const activePreset = PRESETS.find((p) => {
    const v = p.values(meta);
    return (["start", "end", "business_line", "compare"] as const).every((k) => (v[k] ?? "") === (values[k] ?? (k === "compare" ? "previous" : "")))
      && !values.segment && !values.region && !values.product_line;
  });
  return (
    <div className="mb-6 rounded-2xl border border-line bg-surface p-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">Visões</span>
        <div role="group" aria-label="Presets de filtros" className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              title={p.description}
              aria-pressed={activePreset?.id === p.id}
              onClick={() => setFilters(p.values(meta), true)}
              className={cx(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                activePreset?.id === p.id ? "border-brand bg-brand text-white dark:text-[#0a111e]" : "border-line text-ink-2 hover:bg-surface-2",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
        <button onClick={() => setFilters(PRESETS[0].values(meta), true)} className="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-ink">
          <RotateCcw className="size-3.5" aria-hidden /> Limpar filtros
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
        <Field label="De">
          <select className={selectCls} value={values.start ?? ""} onChange={set("start")}>
            {all.map((m) => <option key={m} value={m} disabled={!!values.end && m > values.end}>{monthLabel(m)}</option>)}
          </select>
        </Field>
        <Field label="Até">
          <select className={selectCls} value={values.end ?? ""} onChange={set("end")}>
            {all.map((m) => <option key={m} value={m} disabled={!!values.start && m < values.start}>{monthLabel(m)}</option>)}
          </select>
        </Field>
        <Field label="Comparar com">
          <select className={selectCls} value={values.compare ?? "previous"} onChange={set("compare")}>
            <option value="previous">Período anterior</option>
            <option value="yoy">Mesmo período, ano anterior</option>
          </select>
        </Field>
        {show.includes("business_line") && (
          <Field label="Negócio">
            <select className={selectCls} value={values.business_line ?? ""} onChange={set("business_line")}>
              <option value="">Todos</option>
              <option value="sale">Venda</option>
              <option value="rental">Locação</option>
            </select>
          </Field>
        )}
        {show.includes("segment") && (
          <Field label="Segmento">
            <select className={selectCls} value={values.segment ?? ""} onChange={set("segment")}>
              <option value="">Todos</option>
              {meta.options.segment.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
        )}
        {show.includes("region") && (
          <Field label="Região">
            <select className={selectCls} value={values.region ?? ""} onChange={set("region")}>
              <option value="">Todas</option>
              {meta.options.region.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
        )}
        {show.includes("product_line") && (
          <Field label="Linha de produto">
            <select className={selectCls} value={values.product_line ?? ""} onChange={set("product_line")}>
              <option value="">Todas</option>
              {meta.options.product_line.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
        )}
      </div>
      {note && <p className="mt-3 text-xs text-muted">{note}</p>}
    </div>
  );
}
