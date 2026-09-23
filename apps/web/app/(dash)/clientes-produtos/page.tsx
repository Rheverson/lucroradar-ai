"use client";

import { FileSearch, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { DataTable } from "@/components/data-table";
import { Drawer, SourceRecordView } from "@/components/drawer";
import { FilterBar } from "@/components/filter-bar";
import { Card, EmptyState, ErrorState, LoadingBlock, PageHeader, SectionTitle, StatusBadge, Tag, cx } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { brl, dateBR, monthLabel, num, pct } from "@/lib/format";

type CustomerRow = {
  customer_id: string; legal_name: string; segment: string; region: string; city: string; state: string; salesperson_id: string;
  is_duplicate_candidate: boolean; duplicate_candidate_score: number; net_revenue: number; sale_revenue: number | null; rental_revenue: number | null;
  contribution_margin: number; margin_pct: number | null; discount_rate: number | null; cost_coverage: number | null; overdue: number;
};
type ProductRow = {
  sku: string; description: string; product_line: string; business_line: "sale" | "rental"; quantity: number; net_revenue: number;
  discount_amount: number; product_cost: number; logistics_cost: number; commission_cost: number; maintenance_cost: number;
  contribution_margin: number; margin_pct: number | null; discount_rate: number | null; cost_coverage: number | null; lines_missing_cost: number; unit_label: string;
};
type SalesLine = {
  order_item_id: string; order_id: string; customer_id: string; sku: string; revenue_date: string; quantity: number; unit_list_price: number;
  gross_amount: number; discount_amount: number; discount_rate: number; net_revenue: number; cost_known: boolean; product_cost: number | null;
  freight_cost: number; commission_cost: number; contribution_margin: number | null; sku_raw: string; sku_is_legacy_code: boolean;
  source_batch_id: string; source_row_number: number;
};
type RentalLine = { contract_item_id: string; contract_id: string; unit_id: string; sku: string; customer_id: string; month_start: string; active_days: number; days_in_month: number; recognized_revenue: number; list_revenue: number; discount_amount: number };
type CustomerDetail = {
  customer: CustomerRow & { tax_id_digits: string | null; created_at: string; segment_missing: boolean; region_derived_from_state: boolean };
  monthly: { month: string; net_revenue: number; margin_pct: number | null }[];
  duplicate_candidates: { customer_id_a: string; legal_name_a: string; customer_id_b: string; legal_name_b: string; match_score: number; evidence: string; recommendation: string; confidence: string }[];
  open_receivables: { receivable_id: string; document_number: string; due_date: string; open_amount: number; status: string; days_overdue: number | null }[];
};

function withBusinessLine(q: string, bl: string) {
  const p = new URLSearchParams(q);
  p.set("business_line", bl);
  return p.toString();
}

const SORTS = [
  { v: "revenue", l: "Maior receita" },
  { v: "margin_pct", l: "Menor margem %" },
  { v: "discount", l: "Maior desconto" },
  { v: "overdue", l: "Maior vencido" },
];

function Lines({ q, customer, sku, onSource }: { q: string; customer?: string; sku?: string; onSource: (l: SalesLine) => void }) {
  const extra = new URLSearchParams({ ...(customer ? { customer_id: customer } : {}), ...(sku ? { sku } : {}), limit: "100" }).toString();
  const sales = useApi<{ rows: SalesLine[]; total: number; note?: string }>(`v1/drilldown/sales-lines?${q}&${extra}`);
  const rental = useApi<{ rows: RentalLine[]; total: number; note?: string }>(`v1/drilldown/rental-lines?${q}&${extra}`);
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 text-sm font-semibold">Linhas de venda faturadas {sales.data && <span className="font-normal text-muted">({num(sales.data.total)}{sales.data.total > 100 ? ", mostrando 100" : ""})</span>}</h3>
        {sales.error ? <ErrorState message={sales.error.message} /> : !sales.data ? <LoadingBlock /> : sales.data.rows.length === 0 ? <EmptyState title={sales.data.note ?? "Sem vendas no período"} /> : (
          <DataTable<SalesLine>
            caption="Linhas de venda" rows={sales.data.rows} rowKey={(r) => r.order_item_id} maxHeight={360}
            columns={[
              { key: "order_item_id", header: "Item", render: (r) => <span className="font-mono text-xs">{r.order_item_id}</span> },
              { key: "revenue_date", header: "Faturado", render: (r) => dateBR(r.revenue_date), sortValue: (r) => r.revenue_date },
              { key: "sku", header: "SKU", render: (r) => <span className="font-mono text-xs">{r.sku}{r.sku_is_legacy_code && <Tag className="ml-1">legado {r.sku_raw}</Tag>}</span> },
              { key: "net_revenue", header: "Receita", align: "right", sortValue: (r) => r.net_revenue, render: (r) => brl(r.net_revenue) },
              { key: "discount_rate", header: "Desc.", align: "right", sortValue: (r) => r.discount_rate, render: (r) => pct(r.discount_rate) },
              { key: "contribution_margin", header: "Margem", align: "right", sortValue: (r) => r.contribution_margin, render: (r) => r.cost_known ? brl(r.contribution_margin) : <StatusBadge tone="warn">custo ausente</StatusBadge> },
              { key: "src", header: "Origem", render: (r) => (
                <button onClick={(e) => { e.stopPropagation(); onSource(r); }} className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-brand-2 hover:bg-surface-2" aria-label={`Ver registro de origem do item ${r.order_item_id}`}>
                  <FileSearch className="size-3.5" aria-hidden /> raw
                </button>
              ) },
            ]}
          />
        )}
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold">Locação: receita reconhecida por unidade e mês {rental.data && <span className="font-normal text-muted">({num(rental.data.total)}{rental.data.total > 100 ? ", mostrando 100" : ""})</span>}</h3>
        {rental.error ? <ErrorState message={rental.error.message} /> : !rental.data ? <LoadingBlock /> : rental.data.rows.length === 0 ? <EmptyState title={rental.data.note ?? "Sem locações no período"} /> : (
          <DataTable<RentalLine>
            caption="Receita de locação por item de contrato e mês" rows={rental.data.rows} rowKey={(r) => `${r.contract_item_id}-${r.month_start}`} maxHeight={320}
            columns={[
              { key: "contract_id", header: "Contrato", render: (r) => <span className="font-mono text-xs">{r.contract_id}</span> },
              { key: "unit_id", header: "Unidade física", render: (r) => <span className="font-mono text-xs">{r.unit_id} · {r.sku}</span> },
              { key: "month_start", header: "Mês", render: (r) => monthLabel(r.month_start.slice(0, 7)), sortValue: (r) => r.month_start },
              { key: "active_days", header: "Dias ativos", align: "right", render: (r) => `${r.active_days}/${r.days_in_month}` },
              { key: "recognized_revenue", header: "Receita", align: "right", sortValue: (r) => r.recognized_revenue, render: (r) => brl(r.recognized_revenue) },
              { key: "discount_amount", header: "Desconto", align: "right", render: (r) => brl(r.discount_amount), hideOnMobile: true },
            ]}
          />
        )}
      </div>
    </div>
  );
}

function CustomerPanel({ id, q, onSource }: { id: string; q: string; onSource: (l: SalesLine) => void }) {
  const d = useApi<CustomerDetail>(`v1/customers/${id}?${q}`);
  if (d.error) return <ErrorState message={d.error.message} onRetry={d.reload} />;
  if (!d.data) return <LoadingBlock rows={8} />;
  const c = d.data.customer;
  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {[
          ["Segmento", c.segment + (c.segment_missing ? " (ausente na origem)" : "")],
          ["Região", c.region + (c.region_derived_from_state ? " (derivada da UF)" : "")],
          ["Cidade", `${c.city}/${c.state}`],
          ["CNPJ (dígitos)", c.tax_id_digits ?? "ausente"],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl bg-surface-2 p-3 ring-1 ring-line"><dt className="text-xs text-muted">{k}</dt><dd className="mt-0.5 font-medium">{v}</dd></div>
        ))}
      </dl>
      {d.data.duplicate_candidates.length > 0 && (
        <div className="rounded-xl border border-warn/40 bg-warn-bg/40 p-4 text-sm">
          <p className="font-semibold text-warn">Possível cadastro duplicado — nada foi unificado automaticamente</p>
          <ul className="mt-2 space-y-2">
            {d.data.duplicate_candidates.map((p) => {
              const other = p.customer_id_a === id ? `${p.legal_name_b} (${p.customer_id_b})` : `${p.legal_name_a} (${p.customer_id_a})`;
              return <li key={p.customer_id_a + p.customer_id_b}><strong>{other}</strong> · confiança {p.confidence} ({p.match_score.toFixed(2).replace(".", ",")}) — {p.evidence}. <em>{p.recommendation}.</em></li>;
            })}
          </ul>
        </div>
      )}
      <div>
        <h3 className="mb-2 text-sm font-semibold">Receita e margem por mês (janela completa)</h3>
        <div className="flex gap-1 overflow-x-auto pb-1" role="list">
          {d.data.monthly.map((m) => {
            const max = Math.max(...d.data!.monthly.map((x) => x.net_revenue), 1);
            return (
              <div key={m.month} role="listitem" className="flex w-9 shrink-0 flex-col items-center gap-1" title={`${monthLabel(m.month)}: ${brl(m.net_revenue)} · margem ${pct(m.margin_pct)}`}>
                <div className="flex h-20 w-full items-end rounded bg-surface-2"><div className="w-full rounded bg-[var(--series-1)]" style={{ height: `${(m.net_revenue / max) * 100}%` }} /></div>
                <span className="text-[10px] text-muted">{monthLabel(m.month).slice(0, 3)}</span>
              </div>
            );
          })}
        </div>
      </div>
      {d.data.open_receivables.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Títulos em aberto</h3>
          <DataTable caption="Títulos em aberto" rows={d.data.open_receivables} rowKey={(r) => r.receivable_id} maxHeight={220}
            columns={[
              { key: "document_number", header: "Documento", render: (r) => <span className="font-mono text-xs">{r.document_number}</span> },
              { key: "due_date", header: "Vencimento", render: (r) => dateBR(r.due_date) },
              { key: "open_amount", header: "Em aberto", align: "right", render: (r) => brl(r.open_amount) },
              { key: "status", header: "Situação", render: (r) => r.status === "overdue" ? <StatusBadge tone="bad">vencido há {r.days_overdue} d</StatusBadge> : <StatusBadge tone="info">a vencer</StatusBadge> },
            ]} />
        </div>
      )}
      <Lines q={q} customer={id} onSource={onSource} />
    </div>
  );
}

export default function CustomersProductsPage() {
  const { query: q } = useFilters();
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [tab, setTab] = useState<"customers" | "products">(sp.get("tab") === "products" ? "products" : "customers");
  const [sort, setSort] = useState(sp.get("sort") ?? "revenue");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [product, setProduct] = useState<ProductRow | null>(null);
  const [source, setSource] = useState<SalesLine | null>(null);
  const customer = sp.get("customer");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const setCustomer = useCallback((id: string | null) => {
    const p = new URLSearchParams(sp.toString());
    if (id) p.set("customer", id); else p.delete("customer");
    router.replace(`${pathname}?${p.toString()}`, { scroll: false });
  }, [sp, router, pathname]);

  const customers = useApi<{ rows: CustomerRow[]; total: number; filters_not_applied: { overdue: string[] } }>(
    q && tab === "customers" ? `v1/customers?${q}&sort=${sort}&limit=100${debounced ? `&q=${encodeURIComponent(debounced)}` : ""}` : null);
  const products = useApi<{ rows: ProductRow[] }>(q && tab === "products" ? `v1/products?${q}` : null);

  return (
    <>
      <PageHeader eyebrow="Investigação" title="Clientes e produtos"
        description="Receita, descontos, custos e margem de contribuição por cliente e por produto. Clique em uma linha para descer até os registros de origem." />
      <FilterBar />
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div role="tablist" aria-label="Visão" className="flex rounded-xl bg-surface-2 p-1 ring-1 ring-line">
            {([["customers", "Clientes"], ["products", "Produtos"]] as const).map(([k, l]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                className={cx("rounded-lg px-4 py-1.5 text-sm font-medium", tab === k ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink")}>{l}</button>
            ))}
          </div>
          {tab === "customers" && (
            <>
              <label className="relative min-w-0 flex-1 sm:max-w-xs">
                <span className="sr-only">Buscar cliente</span>
                <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted" aria-hidden />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por nome ou código"
                  className="h-9 w-full rounded-lg border border-line bg-surface pl-8 pr-3 text-sm" />
              </label>
              <label className="flex items-center gap-2 text-sm text-muted">Ordenar
                <select value={sort} onChange={(e) => setSort(e.target.value)} className="h-9 rounded-lg border border-line bg-surface px-2 text-sm text-ink">
                  {SORTS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
                </select>
              </label>
            </>
          )}
        </div>

        {tab === "customers" ? (
          customers.error ? <ErrorState message={customers.error.message} onRetry={customers.reload} /> : !customers.data ? <LoadingBlock rows={8} /> :
            customers.data.rows.length === 0 ? <EmptyState hint="Ajuste os filtros ou a busca." /> : (
              <>
                <SectionTitle as="h3" title={`${num(customers.data.total)} clientes com receita no período`} subtitle="Margem % calculada só sobre receita com custo conhecido. Vencido na data de fechamento do período." />
                <DataTable<CustomerRow>
                  caption="Clientes" rows={customers.data.rows} rowKey={(r) => r.customer_id} onRowClick={(r) => setCustomer(r.customer_id)} maxHeight={620}
                  columns={[
                    { key: "legal_name", header: "Cliente", sortValue: (r) => r.legal_name, render: (r) => (
                      <span className="flex flex-col">
                        <span className="font-medium text-ink">{r.legal_name}</span>
                        <span className="text-xs text-muted">{r.customer_id} · {r.salesperson_id}{r.is_duplicate_candidate && r.duplicate_candidate_score >= 0.6 ? " · " : ""}{r.is_duplicate_candidate && r.duplicate_candidate_score >= 0.6 && <span className="text-warn">possível duplicidade</span>}</span>
                      </span>
                    ) },
                    { key: "segment", header: "Segmento", render: (r) => <Tag>{r.segment}</Tag>, hideOnMobile: true },
                    { key: "region", header: "Região", hideOnMobile: true },
                    { key: "net_revenue", header: "Receita", align: "right", sortValue: (r) => r.net_revenue, render: (r) => brl(r.net_revenue) },
                    { key: "margin_pct", header: "Margem %", align: "right", sortValue: (r) => r.margin_pct, render: (r) => pct(r.margin_pct) },
                    { key: "discount_rate", header: "Desconto", align: "right", sortValue: (r) => r.discount_rate, render: (r) => pct(r.discount_rate) },
                    { key: "cost_coverage", header: "Cobertura custo", align: "right", sortValue: (r) => r.cost_coverage, render: (r) => pct(r.cost_coverage, 0), hideOnMobile: true },
                    { key: "overdue", header: "Vencido", align: "right", sortValue: (r) => r.overdue, render: (r) => r.overdue > 0 ? <span className="text-bad">{brl(r.overdue)}</span> : "—" },
                  ]}
                />
              </>
            )
        ) : products.error ? <ErrorState message={products.error.message} onRetry={products.reload} /> : !products.data ? <LoadingBlock rows={8} /> :
          products.data.rows.length === 0 ? <EmptyState /> : (
            <>
              <SectionTitle as="h3" title="Produtos comerciais por linha de negócio" subtitle="Venda: custo do produto + frete + comissão. Locação: logística + manutenção rateada por uso. Quantidade de locação em unidade-dia." />
              <DataTable<ProductRow>
                caption="Produtos" rows={products.data.rows} rowKey={(r) => r.sku + r.business_line} onRowClick={setProduct} maxHeight={620}
                initialSort={{ key: "net_revenue", dir: "desc" }}
                columns={[
                  { key: "sku", header: "Produto", sortValue: (r) => r.sku, render: (r) => <span className="flex flex-col"><span className="font-medium">{r.description}</span><span className="text-xs text-muted">{r.sku} · {r.product_line}</span></span> },
                  { key: "business_line", header: "Negócio", render: (r) => <Tag>{r.business_line === "sale" ? "Venda" : "Locação"}</Tag> },
                  { key: "quantity", header: "Qtd.", align: "right", sortValue: (r) => r.quantity, render: (r) => <span title={r.unit_label}>{num(r.quantity)}</span>, hideOnMobile: true },
                  { key: "net_revenue", header: "Receita", align: "right", sortValue: (r) => r.net_revenue, render: (r) => brl(r.net_revenue) },
                  { key: "discount_rate", header: "Desconto", align: "right", sortValue: (r) => r.discount_rate, render: (r) => pct(r.discount_rate) },
                  { key: "costs", header: "Custos diretos", align: "right", sortValue: (r) => r.product_cost + r.logistics_cost + r.commission_cost + r.maintenance_cost, render: (r) => brl(r.product_cost + r.logistics_cost + r.commission_cost + r.maintenance_cost), hideOnMobile: true },
                  { key: "margin_pct", header: "Margem %", align: "right", sortValue: (r) => r.margin_pct, render: (r) => pct(r.margin_pct) },
                  { key: "cost_coverage", header: "Cobertura", align: "right", sortValue: (r) => r.cost_coverage, render: (r) => (r.cost_coverage ?? 1) < 0.95 ? <StatusBadge tone="warn">{pct(r.cost_coverage, 0)}</StatusBadge> : pct(r.cost_coverage, 0) },
                ]}
              />
            </>
          )}
      </Card>

      <Drawer open={!!customer} onClose={() => setCustomer(null)} title={customer ? `Cliente ${customer}` : ""} wide>
        {customer && <CustomerPanel id={customer} q={q} onSource={setSource} />}
      </Drawer>
      <Drawer open={!!product} onClose={() => setProduct(null)} title={product ? `${product.sku} — ${product.description}` : ""} wide>
        {product && <Lines q={withBusinessLine(q, product.business_line)} sku={product.sku} onSource={setSource} />}
      </Drawer>
      <Drawer open={!!source} onClose={() => setSource(null)} title={source ? `Registro de origem · ${source.order_item_id}` : ""}>
        {source && <SourceRecordView table="order_items" batch={source.source_batch_id} row={source.source_row_number} />}
      </Drawer>
    </>
  );
}
