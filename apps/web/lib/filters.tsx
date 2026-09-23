"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, useMemo } from "react";
import { useApi } from "./api";
import type { Meta } from "./types";

export const FILTER_KEYS = ["start", "end", "business_line", "segment", "region", "product_line", "compare"] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];
export type FilterValues = Partial<Record<FilterKey, string>>;

export function addMonths(ym: string, n: number) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + n, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export const PRESETS: { id: string; label: string; description: string; values: (m: Meta) => FilterValues }[] = [
  { id: "ceo", label: "CEO", description: "Últimos 6 meses × 6 anteriores, todos os negócios",
    values: (m) => ({ start: addMonths(m.window_end, -5), end: m.window_end, compare: "previous" }) },
  { id: "financeiro", label: "Financeiro", description: "Último trimestre × mesmo trimestre do ano anterior",
    values: (m) => ({ start: addMonths(m.window_end, -2), end: m.window_end, compare: "yoy" }) },
  { id: "operacoes", label: "Operações", description: "Locação, últimos 3 meses",
    values: (m) => ({ start: addMonths(m.window_end, -2), end: m.window_end, business_line: "rental", compare: "previous" }) },
];

type Ctx = {
  meta: Meta | null; metaError: string | null; values: FilterValues; query: string;
  setFilters: (patch: FilterValues, replaceAll?: boolean) => void; withQuery: (path: string, extra?: Record<string, string>) => string;
};
const FiltersContext = createContext<Ctx | null>(null);

export function FiltersProvider({ children }: { children: React.ReactNode }) {
  const meta = useApi<Meta>("v1/meta");
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const values = useMemo(() => {
    const v: FilterValues = {};
    for (const k of FILTER_KEYS) {
      const x = sp.get(k);
      if (x) v[k] = x;
    }
    if (meta.data && !v.start && !v.end) {
      v.end = meta.data.window_end;
      v.start = addMonths(meta.data.window_end, -5);
    }
    return v;
  }, [sp, meta.data]);

  const query = useMemo(() => {
    const p = new URLSearchParams();
    for (const k of FILTER_KEYS) if (values[k]) p.set(k, values[k]!);
    return p.toString();
  }, [values]);

  const setFilters = useCallback(
    (patch: FilterValues, replaceAll = false) => {
      const next = new URLSearchParams(replaceAll ? "" : sp.toString());
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      if (!next.get("start") && values.start) next.set("start", values.start);
      if (!next.get("end") && values.end) next.set("end", values.end);
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [sp, router, pathname, values.start, values.end],
  );

  const withQuery = useCallback(
    (path: string, extra?: Record<string, string>) => {
      const p = new URLSearchParams(query);
      for (const [k, v] of Object.entries(extra ?? {})) if (v) p.set(k, v);
      const s = p.toString();
      return s ? `${path}?${s}` : path;
    },
    [query],
  );

  return (
    <FiltersContext.Provider
      value={{ meta: meta.data, metaError: meta.error?.message ?? null, values, query, setFilters, withQuery }}
    >
      {children}
    </FiltersContext.Provider>
  );
}

export function useFilters() {
  const c = useContext(FiltersContext);
  if (!c) throw new Error("useFilters fora do FiltersProvider");
  return c;
}

export function linkHref(link: { path: string; query?: Record<string, string>; anchor?: string }) {
  const q = new URLSearchParams(link.query ?? {}).toString();
  return `${link.path}${q ? `?${q}` : ""}${link.anchor ? `#${link.anchor}` : ""}`;
}
