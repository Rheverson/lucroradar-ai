"use client";

import { Download, FileText, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { FilterBar } from "@/components/filter-bar";
import { Button, Card, ErrorState, LoadingBlock, PageHeader, SectionTitle, StatusBadge, cx } from "@/components/ui";
import { apiFetch, ApiError } from "@/lib/api";
import { linkHref, useFilters } from "@/lib/filters";
import { brl, num, pct, pp, signedBrl } from "@/lib/format";
import type { Link as ApiLink } from "@/lib/types";

type Levers = { discount_change_pp: number; utilization_change_pp: number; collection_delay_days: number; max_utilization: number };
type Metrics = { sale_revenue: number; sale_discount_rate: number | null; sale_margin: number; rental_revenue: number; rental_margin: number; rental_utilization: number | null; revenue: number; contribution_margin: number; margin_pct: number | null; cash_tied_in_receivables_change: number };
type SimResult = { baseline: Metrics; simulated: Metrics; delta: Record<keyof Metrics, number | null>; notes: string[]; assumptions: string[]; limitations: string[]; disclaimer: string; daily_revenue: number; filters: { period: { label: string } } };
type Proposal = { actions: { title: string; detail: string; based_on: string; evidence: { label: string; value: string }[]; link: ApiLink }[]; markdown: string };

const DEFAULTS: Levers = { discount_change_pp: 0, utilization_change_pp: 0, collection_delay_days: 0, max_utilization: 0.95 };
const KEY = "lucroradar-simulador";

function Slider({ id, label, value, min, max, step, unit, onChange, help }: { id: string; label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void; help: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-ink">{label}</label>
        <output htmlFor={id} className="num text-sm font-semibold text-brand-2">{value > 0 ? "+" : ""}{value.toLocaleString("pt-BR")} {unit}</output>
      </div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-[var(--brand-2)]" aria-describedby={`${id}-help`} />
      <div className="flex justify-between text-[11px] text-muted"><span>{min} {unit}</span><span>+{max} {unit}</span></div>
      <p id={`${id}-help`} className="mt-1 text-xs text-muted">{help}</p>
    </div>
  );
}

const ROWS: { key: keyof Metrics; label: string; fmt: "brl" | "pct" }[] = [
  { key: "sale_revenue", label: "Receita de venda", fmt: "brl" },
  { key: "sale_discount_rate", label: "Taxa de desconto (venda)", fmt: "pct" },
  { key: "rental_revenue", label: "Receita de locação", fmt: "brl" },
  { key: "rental_utilization", label: "Utilização da frota", fmt: "pct" },
  { key: "revenue", label: "Receita total", fmt: "brl" },
  { key: "contribution_margin", label: "Margem de contribuição", fmt: "brl" },
  { key: "margin_pct", label: "Margem de contribuição (%)", fmt: "pct" },
];

export default function SimulatorPage() {
  const { query: q } = useFilters();
  const [levers, setLevers] = useState<Levers>(DEFAULTS);
  const [loaded, setLoaded] = useState(false);
  const [res, setRes] = useState<SimResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [proposalState, setProposalState] = useState<{ key: string; value: Proposal } | null>(null);
  const [propBusy, setPropBusy] = useState(false);

  // cenário fica só nesta aba do navegador (sessionStorage): nada é gravado no servidor
  useEffect(() => {
    // sessionStorage só existe no navegador: lido após a hidratação
    let saved: Levers | null = null;
    try { const s = sessionStorage.getItem(KEY); if (s) saved = { ...DEFAULTS, ...JSON.parse(s) }; } catch {}
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved) setLevers(saved);
    setLoaded(true);
  }, []);
  useEffect(() => {
    if (!loaded) return;
    try { sessionStorage.setItem(KEY, JSON.stringify(levers)); } catch {}
  }, [levers, loaded]);

  useEffect(() => {
    if (!q || !loaded) return;
    const t = setTimeout(() => {
      setBusy(true);
      apiFetch<SimResult>(`v1/simulator/run?${q}`, { method: "POST", body: JSON.stringify(levers) })
        .then((r) => { setRes(r); setErr(null); })
        .catch((e: unknown) => setErr(e instanceof ApiError ? e.message : String(e)))
        .finally(() => setBusy(false));
    }, 250);
    return () => clearTimeout(t);
  }, [q, levers, loaded]);

  // a proposta vale só para os filtros e alavancas com que foi gerada
  const inputsKey = `${q}|${JSON.stringify(levers)}`;
  const proposal = proposalState?.key === inputsKey ? proposalState.value : null;

  const set = (k: keyof Levers) => (v: number) => setLevers((l) => ({ ...l, [k]: v }));
  const fmt = (f: "brl" | "pct", v: number | null) => (f === "brl" ? brl(v) : pct(v));
  const dfmt = (f: "brl" | "pct", v: number | null) => (v == null ? "—" : f === "brl" ? signedBrl(v) : pp(v));

  const genProposal = () => {
    setPropBusy(true);
    apiFetch<Proposal>(`v1/proposal?${q}`, { method: "POST", body: JSON.stringify(levers) })
      .then((value) => setProposalState({ key: inputsKey, value })).catch((e: unknown) => setErr(e instanceof ApiError ? e.message : String(e))).finally(() => setPropBusy(false));
  };
  const download = () => {
    if (!proposal) return;
    const blob = new Blob([proposal.markdown], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "proposta-lucroradar.md";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <>
      <PageHeader eyebrow="Simulação determinística" title="Simulador de cenários"
        description="Altere variáveis operacionais e compare com o cenário base do período filtrado. Os cálculos são funções determinísticas testadas no servidor — sem modelo de IA e sem previsão estatística." />
      <FilterBar />
      <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
        <Card className="h-fit xl:sticky xl:top-6">
          <SectionTitle title="Alavancas" right={<Button variant="secondary" onClick={() => setLevers(DEFAULTS)} className="!px-3 !py-1.5"><RotateCcw className="size-3.5" aria-hidden />Restaurar</Button>} />
          <div className="space-y-6">
            <Slider id="disc" label="Desconto médio na venda" value={levers.discount_change_pp} min={-10} max={10} step={0.5} unit="p.p." onChange={set("discount_change_pp")}
              help="Premissa: volume vendido e preço de lista constantes." />
            <Slider id="util" label="Utilização da frota" value={levers.utilization_change_pp} min={-30} max={30} step={1} unit="p.p." onChange={set("utilization_change_pp")}
              help="Receita e custos por unidade-dia constantes; limitada à capacidade física." />
            <div>
              <label htmlFor="cap" className="text-sm font-medium">Utilização máxima fisicamente possível</label>
              <select id="cap" value={levers.max_utilization} onChange={(e) => set("max_utilization")(Number(e.target.value))} className="mt-1 h-9 w-full rounded-lg border border-line bg-surface px-2 text-sm">
                {[0.85, 0.9, 0.95, 1].map((v) => <option key={v} value={v}>{pct(v, 0)}</option>)}
              </select>
            </div>
            <Slider id="delay" label="Prazo médio de recebimento" value={levers.collection_delay_days} min={-30} max={60} step={1} unit="dias" onChange={set("collection_delay_days")}
              help="Afeta caixa (capital em contas a receber), não a margem." />
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <SectionTitle title="Base × simulado" subtitle={res ? `Período: ${res.filters.period.label}` : undefined}
              right={<StatusBadge tone="warn">Impacto simulado — não é ganho realizado</StatusBadge>} />
            {err ? <ErrorState message={err} /> : !res ? <LoadingBlock rows={7} /> : (
              <div className={cx("transition-opacity", busy && "opacity-60")}>
                <div className="overflow-x-auto rounded-xl border border-line">
                  <table className="w-full min-w-[520px] text-sm">
                    <caption className="sr-only">Comparação entre cenário base e simulado</caption>
                    <thead className="bg-surface-2 text-xs text-muted">
                      <tr><th scope="col" className="px-3 py-2 text-left font-medium">Indicador</th><th scope="col" className="px-3 py-2 text-right font-medium">Base</th><th scope="col" className="px-3 py-2 text-right font-medium">Simulado</th><th scope="col" className="px-3 py-2 text-right font-medium">Diferença</th></tr>
                    </thead>
                    <tbody>
                      {ROWS.map((r) => {
                        const d = res.delta[r.key];
                        return (
                          <tr key={r.key} className="border-t border-line">
                            <th scope="row" className="px-3 py-2 text-left font-medium">{r.label}</th>
                            <td className="num px-3 py-2 text-right text-ink-2">{fmt(r.fmt, res.baseline[r.key])}</td>
                            <td className="num px-3 py-2 text-right font-semibold">{fmt(r.fmt, res.simulated[r.key])}</td>
                            <td className={cx("num px-3 py-2 text-right", d && d > 0 ? "text-good" : d && d < 0 ? "text-bad" : "text-muted")}>{dfmt(r.fmt, d)}</td>
                          </tr>
                        );
                      })}
                      <tr className="border-t border-line bg-surface-2/60">
                        <th scope="row" className="px-3 py-2 text-left font-medium">Capital adicional em contas a receber</th>
                        <td className="num px-3 py-2 text-right text-ink-2">—</td>
                        <td className="num px-3 py-2 text-right font-semibold">{signedBrl(res.simulated.cash_tied_in_receivables_change)}</td>
                        <td className={cx("num px-3 py-2 text-right", res.simulated.cash_tied_in_receivables_change > 0 ? "text-bad" : res.simulated.cash_tied_in_receivables_change < 0 ? "text-good" : "text-muted")}>
                          {res.simulated.cash_tied_in_receivables_change > 0 ? "caixa preso" : res.simulated.cash_tied_in_receivables_change < 0 ? "caixa liberado" : "—"}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-muted">Receita média diária do período: {brl(res.daily_revenue)}. Variação de margem calculada apenas sobre linhas com custo conhecido, como na base.</p>
                {res.notes.length > 0 && (
                  <ul className="mt-3 space-y-1 text-xs">{res.notes.map((n) => <li key={n}><StatusBadge tone="info">Nota</StatusBadge> <span className="text-ink-2">{n}</span></li>)}</ul>
                )}
              </div>
            )}
          </Card>

          {res && (
            <div className="grid gap-6 lg:grid-cols-2">
              <Card><SectionTitle as="h3" title="Premissas" /><ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{res.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></Card>
              <Card><SectionTitle as="h3" title="Limitações" /><ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{res.limitations.map((a) => <li key={a}>{a}</li>)}</ul></Card>
            </div>
          )}

          <Card id="proposta" className="scroll-mt-20">
            <SectionTitle title="Proposta de ação fundamentada" subtitle="Combina os alertas com evidências do período e o cenário simulado acima. Texto montado por regras; os números vêm dos serviços de métricas."
              right={<div className="flex gap-2">
                <Button onClick={genProposal} disabled={propBusy || !res}><FileText className="size-4" aria-hidden />{propBusy ? "Gerando…" : "Gerar proposta"}</Button>
                {proposal && <Button variant="secondary" onClick={download}><Download className="size-4" aria-hidden />Baixar .md</Button>}
              </div>} />
            {!proposal ? <p className="text-sm text-muted">Ajuste as alavancas e gere a proposta para o período e filtros atuais.</p> : (
              <ol className="space-y-3">
                {proposal.actions.map((a, i) => (
                  <li key={a.title + i} className="rounded-xl border border-line p-4">
                    <p className="text-sm font-semibold">{i + 1}. {a.title}</p>
                    <p className="mt-1 text-sm text-ink-2">{a.detail}</p>
                    <p className="mt-2 text-xs text-muted">Com base em: {a.based_on} · {a.evidence.map((e) => `${e.label}: ${e.value}`).join(" · ")}</p>
                    <Link href={linkHref(a.link)} className="mt-1 inline-block text-xs font-medium text-brand-2 hover:underline">Ver evidência →</Link>
                  </li>
                ))}
                {proposal.actions.length === 0 && <li className="text-sm text-muted">Nenhum alerta ativo; nenhuma ação sugerida para estes filtros.</li>}
              </ol>
            )}
            {proposal && <p className="mt-3 text-xs text-muted">Contém {num(proposal.actions.length)} ações. Associações observadas não comprovam causa.</p>}
          </Card>
        </div>
      </div>
    </>
  );
}
