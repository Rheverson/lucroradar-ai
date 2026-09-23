"use client";

import { Bot, Send, ShieldCheck, Wrench } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { FilterBar } from "@/components/filter-bar";
import { Button, Card, ErrorState, PageHeader, SectionTitle, Skeleton, StatusBadge, Tag } from "@/components/ui";
import { apiFetch, ApiError, useApi } from "@/lib/api";
import { linkHref, useFilters } from "@/lib/filters";
import type { FiltersInfo, Link as ApiLink } from "@/lib/types";

type Status = { mode: "demo" | "llm"; mode_label: string; model: string | null; max_question_chars: number; tools: string[] };
type Answer = {
  mode: "demo" | "llm"; mode_label: string; model: string | null; question: string; summary: string;
  filters: FiltersInfo; evidence: { id: string; label: string; formatted: string; tool: string; link: ApiLink | null }[];
  limitations: string[]; causality_note: string; actions: (ApiLink & { label: string })[];
  tool_calls: { name: string; input: Record<string, unknown> }[]; warnings: string[]; unsupported_numbers: string[];
};
type Turn = { question: string; answer?: Answer; error?: string };

const BL: Record<string, string> = { sale: "Venda", rental: "Locação" };
const PAGES: Record<string, string> = { "/executivo": "Visão executiva", "/clientes-produtos": "Clientes e produtos", "/operacoes": "Operações", "/qualidade": "Qualidade dos dados" };

function AnswerCard({ a }: { a: Answer }) {
  const f = a.filters;
  const dims = [f.business_line && `Negócio: ${BL[f.business_line]}`, f.segment && `Segmento: ${f.segment}`, f.region && `Região: ${f.region}`, f.product_line && `Linha: ${f.product_line}`].filter(Boolean);
  return (
    <article className="animate-rise space-y-4 rounded-2xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <StatusBadge tone={a.mode === "demo" ? "info" : "good"}>{a.mode_label}{a.model ? ` · ${a.model}` : ""}</StatusBadge>
        <Tag>{f.period?.label}{f.comparison ? ` × ${f.comparison.label}` : ""}</Tag>
        {dims.map((d) => <Tag key={d as string}>{d}</Tag>)}
      </div>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Resumo</h3>
        <p className="mt-1 text-[15px] leading-relaxed text-ink">{a.summary}</p>
      </section>
      {a.evidence.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Evidências (calculadas no servidor)</h3>
          <ul className="mt-2 divide-y divide-line rounded-xl border border-line">
            {a.evidence.map((e) => (
              <li key={e.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-3 py-2 text-sm">
                <span className="min-w-0"><span className="mr-2 font-mono text-xs text-muted">{e.id}</span>{e.label}</span>
                <span className="num text-right font-medium">{e.formatted}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Limitações</h3>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-ink-2">{a.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Associação ≠ causa</h3>
          <p className="mt-1 text-sm text-ink-2">{a.causality_note}</p>
        </div>
      </section>
      {(a.warnings.length > 0 || a.unsupported_numbers.length > 0) && (
        <div className="rounded-xl bg-warn-bg/60 p-3 text-sm">
          {a.warnings.map((w) => <p key={w} className="text-warn">{w}</p>)}
          {a.unsupported_numbers.length > 0 && <p className="text-warn">Números no resumo sem evidência correspondente: {a.unsupported_numbers.join(", ")}. Confira nas evidências.</p>}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {a.actions.map((l, i) => (
          <Link key={i} href={linkHref(l)} className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-brand-2 hover:bg-surface-2">
            Abrir {PAGES[l.path] ?? l.path}{l.anchor ? " (detalhe)" : ""} →
          </Link>
        ))}
        <details className="ml-auto text-xs text-muted">
          <summary className="cursor-pointer">Ferramentas usadas ({a.tool_calls.length})</summary>
          <ul className="mt-1 space-y-0.5 break-all font-mono">{a.tool_calls.map((t, i) => <li key={i}>{t.name}({JSON.stringify(t.input)})</li>)}</ul>
        </details>
      </div>
    </article>
  );
}

export default function CopilotPage() {
  const { query: q } = useFilters();
  const status = useApi<Status>("v1/copilot/status");
  const demo = useApi<{ questions: { id: string; question: string }[] }>("v1/copilot/demo-questions");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const max = status.data?.max_question_chars ?? 600;

  const ask = async (question: string, question_id?: string) => {
    if (!question.trim() || busy) return;
    setBusy(true);
    setTurns((t) => [{ question }, ...t]);
    setText("");
    try {
      const answer = await apiFetch<Answer>(`v1/copilot/ask?${q}`, { method: "POST", body: JSON.stringify({ question, question_id }) });
      setTurns((t) => [{ question, answer }, ...t.slice(1)]);
    } catch (e) {
      setTurns((t) => [{ question, error: e instanceof ApiError ? e.message : String(e) }, ...t.slice(1)]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="IA com evidências" title="Copiloto analítico"
        description="Pergunte o que explica a variação. O copiloto consulta ferramentas controladas sobre as mesmas métricas das telas — sem SQL livre — e cada resposta traz período, filtros, evidências e limitações."
        right={status.data && <StatusBadge tone={status.data.mode === "demo" ? "info" : "good"}>{status.data.mode_label}</StatusBadge>} />
      <FilterBar />
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Card>
            <form onSubmit={(e) => { e.preventDefault(); ask(text); }} className="space-y-3">
              <label htmlFor="pergunta" className="text-sm font-medium">Sua pergunta</label>
              <textarea id="pergunta" value={text} onChange={(e) => setText(e.target.value.slice(0, max))} rows={3}
                onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(text); }}
                placeholder="Ex.: Por que a margem de contribuição caiu se a receita cresceu?"
                className="w-full resize-y rounded-xl border border-line bg-surface p-3 text-sm" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs text-muted">{text.length}/{max} · os filtros acima são aplicados à resposta</span>
                <Button type="submit" disabled={busy || text.trim().length < 3}><Send className="size-4" aria-hidden />{busy ? "Consultando…" : "Perguntar"}</Button>
              </div>
            </form>
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Perguntas demonstrativas</p>
              <div className="flex flex-wrap gap-2">
                {(demo.data?.questions ?? []).map((d) => (
                  <button key={d.id} onClick={() => ask(d.question, d.id)} disabled={busy}
                    className="rounded-full border border-line bg-surface-2 px-3 py-1.5 text-left text-xs font-medium text-ink-2 hover:border-brand-2 hover:text-ink disabled:opacity-50">
                    {d.question}
                  </button>
                ))}
              </div>
            </div>
          </Card>
          <div aria-live="polite" className="space-y-4">
            {turns.length === 0 && (
              <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-line p-10 text-center text-sm text-muted">
                <Bot className="size-6 text-accent" aria-hidden />
                Escolha uma pergunta demonstrativa ou escreva a sua.
              </div>
            )}
            {turns.map((t, i) => (
              <div key={turns.length - i} className="space-y-2">
                <p className="ml-auto w-fit max-w-[90%] rounded-2xl rounded-br-sm bg-brand px-4 py-2 text-sm text-white dark:text-[#0a111e]">{t.question}</p>
                {t.answer ? <AnswerCard a={t.answer} /> : t.error ? <ErrorState message={t.error} /> : (
                  <div className="space-y-2 rounded-2xl border border-line bg-surface p-5" role="status"><span className="sr-only">Consultando métricas…</span><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" /></div>
                )}
              </div>
            ))}
          </div>
        </div>
        <aside className="space-y-4">
          <Card>
            <SectionTitle as="h3" title="Como o copiloto funciona" />
            <ul className="space-y-3 text-sm text-ink-2">
              <li className="flex gap-2"><Wrench className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden /><span className="min-w-0">Só pode chamar ferramentas fixas:<span className="mt-1 flex flex-wrap gap-1">{status.data?.tools.map((t) => <code key={t} className="break-all rounded bg-surface-2 px-1 text-xs">{t}</code>)}</span></span></li>
              <li className="flex gap-2"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />Números vêm do banco e de funções determinísticas; o texto só cita evidências por ID. Números sem evidência são sinalizados.</li>
              <li className="flex gap-2"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />Os filtros da tela prevalecem sobre o que o modelo pedir.</li>
            </ul>
          </Card>
          {status.data?.mode === "demo" && (
            <Card>
              <SectionTitle as="h3" title="Demonstração sem modelo generativo" />
              <p className="text-sm text-ink-2">Não há chave de API configurada no servidor. As respostas são montadas por regras a partir dos mesmos serviços de métricas — nenhuma chamada a modelo de linguagem é simulada. Perguntas livres são direcionadas ao roteiro mais próximo por palavras-chave.</p>
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}
