"use client";

import { useState } from "react";
import { DataTable } from "@/components/data-table";
import { Drawer } from "@/components/drawer";
import { Card, ErrorState, LoadingBlock, PageHeader, SectionTitle, StatusBadge, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { brl, num, pct } from "@/lib/format";

type Issue = { issue_code: string; category: string; issue_label: string; source_table: string; affected_records: number; affected_amount: number | null; handling: string; consequence: string };
type Rec = { check_name: string; left_value: number; right_value: number; difference: number; tolerance: number; status: string };
type RowCount = { source_table: string; raw_rows: number; distinct_keys: number; valid_rows: number; quarantined_rows: number; exact_duplicates_removed: number; keys_with_multiple_versions: number };
type Run = { run_id: number; trigger: string; status: string; started_at: string; finished_at: string | null; message: string | null; steps: { step: string; status: string; rows: number | null; detail: string | null }[] };
type Overview = { issues: Issue[]; reconciliation: Rec[]; row_counts: RowCount[]; runs: Run[]; batches: { batch_id: string; as_of_date: string; status: string; rows_loaded: number; rows_rejected: number }[]; sale_cost_coverage: { coverage: number; missing: number } };
type Dup = { customer_id_a: string; legal_name_a: string; customer_id_b: string; legal_name_b: string; name_similarity: number; match_score: number; evidence: string; recommendation: string; confidence: string; combined_sales_revenue: number };
type Quarantine = { rows: { source_table: string; record_key: string; reason: string; batch_id: string; row_number: number; raw_payload: Record<string, string> }[] };

const HANDLING_TONE: Record<string, "bad" | "warn" | "good" | "info"> = { quarentena: "bad", sinalizado: "warn", padronizado: "good", "para revisão": "info" };
const TABLES = ["", "orders", "order_items", "order_events", "receivables", "receipts", "direct_costs"];

export default function QualityPage() {
  const ov = useApi<Overview>("v1/quality/overview");
  const dups = useApi<{ rows: Dup[]; rules: string[]; policy: string }>("v1/quality/duplicates?min_score=0");
  const [table, setTable] = useState("");
  const qr = useApi<Quarantine>(`v1/quality/quarantine?limit=100${table ? `&table=${table}` : ""}`);
  const [payload, setPayload] = useState<Quarantine["rows"][number] | null>(null);
  const d = ov.data;

  return (
    <>
      <PageHeader eyebrow="Confiabilidade" title="Qualidade dos dados"
        description="O que chegou com problema, o que foi feito com cada caso e qual a consequência para as análises. Nada é corrigido em silêncio." />
      {ov.error ? <ErrorState message={ov.error.message} onRetry={ov.reload} /> : !d ? <LoadingBlock rows={10} /> : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["Registros em quarentena", num(d.row_counts.reduce((s, r) => s + r.quarantined_rows, 0)), "Fora das análises até correção na origem"],
              ["Cobertura de custo (venda)", pct(d.sale_cost_coverage.coverage), `${num(d.sale_cost_coverage.missing)} linhas sem custo — nunca tratadas como zero`],
              ["Reconciliações", `${d.reconciliation.filter((r) => r.status === "ok").length}/${d.reconciliation.length} ok`, "Totais conferidos entre camadas e métodos"],
              ["Última execução", d.runs[0] ? `#${d.runs[0].run_id} · ${d.runs[0].status === "success" ? "sucesso" : d.runs[0].status}` : "—", d.runs[0] ? new Date(d.runs[0].started_at).toLocaleString("pt-BR") : ""],
            ].map(([k, v, h]) => (
              <Card key={k} className="!p-5"><p className="text-sm text-ink-2">{k}</p><p className="num mt-1 text-2xl font-semibold">{v}</p><p className="mt-1 text-xs text-muted">{h}</p></Card>
            ))}
          </div>

          <Card className="mt-6">
            <SectionTitle title="Problemas por tipo e consequências" subtitle="Quarentena: excluído das análises. Padronizado: corrigido por regra determinística. Sinalizado: mantido com impacto indicado. Para revisão: depende de decisão humana." />
            <DataTable<Issue> caption="Problemas de qualidade" rows={d.issues} rowKey={(r) => r.issue_code} maxHeight={560} initialSort={{ key: "affected_records", dir: "desc" }}
              columns={[
                { key: "issue_label", header: "Problema", render: (r) => <span className="flex flex-col"><span className="font-medium">{r.issue_label}</span><span className="text-xs text-muted">{r.category} · {r.source_table}</span></span> },
                { key: "handling", header: "Tratamento", render: (r) => <StatusBadge tone={HANDLING_TONE[r.handling] ?? "info"}>{r.handling}</StatusBadge> },
                { key: "affected_records", header: "Registros", align: "right", sortValue: (r) => r.affected_records, render: (r) => num(r.affected_records) },
                { key: "affected_amount", header: "Valor afetado", align: "right", sortValue: (r) => r.affected_amount, render: (r) => brl(r.affected_amount), hideOnMobile: true },
                { key: "consequence", header: "Consequência para as análises", className: "max-w-md text-xs text-ink-2" },
              ]} />
          </Card>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <Card>
              <SectionTitle title="Reconciliação de totais" subtitle="Cada verificação compara duas formas independentes de chegar ao mesmo número." />
              <ul className="space-y-2">
                {d.reconciliation.map((r) => (
                  <li key={r.check_name} className="rounded-xl bg-surface-2 p-3 text-sm ring-1 ring-line">
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-medium">{r.check_name}</span>
                      <StatusBadge tone={r.status === "ok" ? "good" : "bad"}>{r.status === "ok" ? "confere" : "divergente"}</StatusBadge>
                    </div>
                    <p className="num mt-1 text-xs text-muted">{num(r.left_value)} × {num(r.right_value)} · diferença {r.difference.toLocaleString("pt-BR")} (tolerância {r.tolerance.toLocaleString("pt-BR")})</p>
                  </li>
                ))}
              </ul>
            </Card>
            <Card>
              <SectionTitle title="Do arquivo à análise, por tabela" subtitle="Chaves distintas = válidas + quarentena. A diferença para as linhas recebidas são versões substituídas por lotes mais novos e cópias idênticas." />
              <DataTable<RowCount> caption="Contagens por tabela" rows={d.row_counts} rowKey={(r) => r.source_table} maxHeight={460}
                columns={[
                  { key: "source_table", header: "Tabela", render: (r) => <span className="font-mono text-xs">{r.source_table}</span> },
                  { key: "raw_rows", header: "Recebidas", align: "right", render: (r) => num(r.raw_rows) },
                  { key: "valid_rows", header: "Válidas", align: "right", render: (r) => num(r.valid_rows) },
                  { key: "quarantined_rows", header: "Quarentena", align: "right", render: (r) => r.quarantined_rows ? <span className="text-bad">{num(r.quarantined_rows)}</span> : "0" },
                  { key: "exact_duplicates_removed", header: "Cópias", align: "right", render: (r) => num(r.exact_duplicates_removed), hideOnMobile: true },
                  { key: "keys_with_multiple_versions", header: "Atualizadas", align: "right", render: (r) => num(r.keys_with_multiple_versions), hideOnMobile: true },
                ]} />
            </Card>
          </div>

          <Card className="mt-6" id="duplicidades">
            <SectionTitle title="Candidatos a cliente duplicado" subtitle={dups.data?.policy} />
            {dups.data && (
              <>
                <ul className="mb-4 grid gap-1 text-xs text-muted sm:grid-cols-2">{dups.data.rules.map((r) => <li key={r}>• {r}</li>)}</ul>
                <DataTable<Dup> caption="Candidatos a duplicidade" rows={dups.data.rows} rowKey={(r) => r.customer_id_a + r.customer_id_b} maxHeight={480}
                  columns={[
                    { key: "a", header: "Cadastro A", render: (r) => <span className="flex flex-col"><span className="font-medium">{r.legal_name_a}</span><span className="text-xs text-muted">{r.customer_id_a}</span></span> },
                    { key: "b", header: "Cadastro B", render: (r) => <span className="flex flex-col"><span className="font-medium">{r.legal_name_b}</span><span className="text-xs text-muted">{r.customer_id_b}</span></span> },
                    { key: "match_score", header: "Confiança", sortValue: (r) => r.match_score, render: (r) => <StatusBadge tone={r.confidence === "alta" ? "bad" : r.confidence === "media" ? "warn" : "info"}>{r.confidence} · {r.match_score.toFixed(2).replace(".", ",")}</StatusBadge> },
                    { key: "evidence", header: "Evidência", className: "text-xs text-ink-2 max-w-xs" },
                    { key: "recommendation", header: "Recomendação de revisão", className: "text-xs max-w-xs", hideOnMobile: true },
                    { key: "combined_sales_revenue", header: "Receita somada", align: "right", sortValue: (r) => r.combined_sales_revenue, render: (r) => brl(r.combined_sales_revenue), hideOnMobile: true },
                  ]} />
              </>
            )}
            {dups.error && <ErrorState message={dups.error.message} />}
          </Card>

          <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
            <Card>
              <SectionTitle title="Registros em quarentena" subtitle="Conteúdo original preservado para correção na origem."
                right={<label className="flex items-center gap-2 text-sm text-muted">Tabela
                  <select value={table} onChange={(e) => setTable(e.target.value)} className="h-9 rounded-lg border border-line bg-surface px-2 text-sm text-ink">
                    {TABLES.map((t) => <option key={t} value={t}>{t || "Todas"}</option>)}
                  </select></label>} />
              {qr.error ? <ErrorState message={qr.error.message} /> : !qr.data ? <LoadingBlock /> : (
                <DataTable caption="Quarentena" rows={qr.data.rows} rowKey={(r) => r.source_table + r.record_key} maxHeight={420} onRowClick={setPayload}
                  columns={[
                    { key: "source_table", header: "Tabela", render: (r) => <span className="font-mono text-xs">{r.source_table}</span> },
                    { key: "record_key", header: "Chave", render: (r) => <span className="font-mono text-xs">{r.record_key}</span> },
                    { key: "reason", header: "Motivo", render: (r) => <Tag>{r.reason}</Tag> },
                    { key: "batch_id", header: "Lote / linha", render: (r) => <span className="text-xs text-muted">{r.batch_id} · {r.row_number}</span>, hideOnMobile: true },
                  ]} />
              )}
            </Card>
            <Card>
              <SectionTitle title="Histórico de execução do pipeline" subtitle="Lotes, passos e resultado de cada execução (audit.pipeline_runs)." />
              <ol className="space-y-3">
                {d.runs.map((r) => (
                  <li key={r.run_id} className="rounded-xl bg-surface-2 p-3 text-sm ring-1 ring-line">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">Execução #{r.run_id} <span className="text-xs font-normal text-muted">· {r.trigger} · {new Date(r.started_at).toLocaleString("pt-BR")}</span></span>
                      <StatusBadge tone={r.status === "success" ? "good" : r.status === "running" ? "warn" : "bad"}>{r.status === "success" ? "sucesso" : r.status}</StatusBadge>
                    </div>
                    <ul className="mt-2 space-y-0.5 text-xs text-ink-2">
                      {r.steps.map((s, i) => <li key={i}><span className="font-mono">{s.step}</span> — {s.status}{s.rows != null ? ` · ${num(s.rows)} linhas` : ""}{s.detail ? ` · ${s.detail}` : ""}</li>)}
                    </ul>
                    {r.message && <p className="mt-1 text-xs text-bad">{r.message}</p>}
                  </li>
                ))}
              </ol>
              <h3 className="mb-2 mt-4 text-sm font-semibold">Lotes carregados</h3>
              <ul className="space-y-1 text-xs text-ink-2">
                {d.batches.map((b) => <li key={b.batch_id}><span className="font-mono">{b.batch_id}</span> · posição em {new Date(`${b.as_of_date}T12:00:00`).toLocaleDateString("pt-BR")} · {num(b.rows_loaded)} linhas · {b.rows_rejected} rejeitadas</li>)}
              </ul>
            </Card>
          </div>
        </>
      )}
      <Drawer open={!!payload} onClose={() => setPayload(null)} title={payload ? `Quarentena · ${payload.source_table} ${payload.record_key}` : ""}>
        {payload && (
          <div className="space-y-3 text-sm">
            <p>Motivo: <strong>{payload.reason}</strong></p>
            <dl className="grid grid-cols-[minmax(0,10rem)_1fr] gap-x-4 gap-y-1.5 rounded-xl border border-line p-4">
              {Object.entries(payload.raw_payload).map(([k, v]) => (
                <div key={k} className="contents"><dt className="font-mono text-xs text-muted">{k}</dt><dd className="break-all font-mono text-xs">{v === "" ? <span className="text-bad">(vazio)</span> : v}</dd></div>
              ))}
            </dl>
          </div>
        )}
      </Drawer>
    </>
  );
}
