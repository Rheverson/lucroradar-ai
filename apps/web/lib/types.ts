export type Cmp = { current: number | null; previous: number | null; delta: number | null; delta_pct: number | null; kind: "money" | "ratio" };
export type PeriodInfo = { start: string; end: string; label: string; months: number };
export type FiltersInfo = {
  period: PeriodInfo; comparison: PeriodInfo; compare_mode: string;
  business_line?: string; segment?: string; region?: string; product_line?: string;
};
export type Meta = {
  window_start: string; window_end: string; reference_date: string; synthetic: boolean;
  options: { segment: string[]; region: string[]; product_line: string[]; business_line: string[] };
  repository_url: string; copilot_mode: "demo" | "llm"; company: string;
  last_run: { run_id: number; status: string; finished_at: string } | null;
};
export type Summary = {
  filters: FiltersInfo; comparison_available: boolean;
  kpis: Record<"net_revenue" | "contribution_margin" | "margin_pct" | "receipts" | "overdue" | "open_receivables" | "discount_rate" | "cost_coverage" | "cash_conversion", Cmp>;
  breakdown: { sale_revenue: number; rental_revenue: number; lines_missing_cost: number; line_count: number };
  overdue_snapshot_date: string; filters_not_applied: { receivables: string[] };
  definitions: Record<string, string>;
};
export type SeriesPoint = {
  month: string; label: string; net_revenue: number; sale_revenue: number; rental_revenue: number;
  contribution_margin: number; margin_pct: number | null; discount_rate: number | null;
  receipts: number; overdue: number; open_receivables: number; in_period: boolean;
};
export type BridgeGroup = { name: string; volume: number; price: number; discount: number; cost: number; delta: number };
export type Bridge = {
  available: boolean; reason?: string; margin_previous: number; margin_current: number;
  margin_pct_previous: number | null; margin_pct_current: number | null;
  revenue_previous: number; revenue_current: number;
  effects: { key: string; label: string; value: number }[]; residual: number; method: string;
  by: Record<"product_line" | "salesperson_id" | "business_line" | "region", BridgeGroup[]>;
};
export type Link = { path: string; query: Record<string, string>; anchor?: string };
export type Alert = {
  id: string; severity: "high" | "medium" | "low"; title: string; summary: string;
  evidence: { label: string; value: string }[]; rule: string; link: Link;
};
