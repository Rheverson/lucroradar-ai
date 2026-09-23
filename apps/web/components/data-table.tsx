"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import { cx } from "./ui";

export type Column<T> = {
  key: string; header: string; align?: "left" | "right"; render?: (row: T) => React.ReactNode;
  sortValue?: (row: T) => number | string | null; className?: string; hideOnMobile?: boolean;
};

export function DataTable<T>({
  rows, columns, rowKey, caption, initialSort, onRowClick, maxHeight, minWidth = 0,
}: {
  rows: T[]; columns: Column<T>[]; rowKey: (r: T) => string; caption: string;
  initialSort?: { key: string; dir: "asc" | "desc" }; onRowClick?: (r: T) => void; maxHeight?: number; minWidth?: number;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const out = [...rows].sort((a, b) => {
      const va = col.sortValue!(a), vb = col.sortValue!(b);
      if (va == null) return 1;
      if (vb == null) return -1;
      return va < vb ? -1 : va > vb ? 1 : 0;
    });
    return sort.dir === "desc" ? out.reverse() : out;
  }, [rows, columns, sort]);

  return (
    <div className="overflow-auto rounded-xl border border-line" style={maxHeight ? { maxHeight } : undefined}>
      <table className="w-full border-collapse text-sm" style={{ minWidth }}>
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 z-10 bg-surface-2 text-xs text-muted">
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th key={c.key} scope="col" aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                  className={cx("whitespace-nowrap border-b border-line px-3 py-2 font-medium", c.align === "right" ? "text-right" : "text-left", c.hideOnMobile && "hidden md:table-cell")}>
                  {c.sortValue ? (
                    <button className={cx("inline-flex items-center gap-1 hover:text-ink", c.align === "right" && "flex-row-reverse")}
                      onClick={() => setSort({ key: c.key, dir: active && sort!.dir === "desc" ? "asc" : "desc" })}>
                      {c.header}
                      {active ? (sort!.dir === "asc" ? <ArrowUp className="size-3" aria-hidden /> : <ArrowDown className="size-3" aria-hidden />) : <ArrowUpDown className="size-3 opacity-40" aria-hidden />}
                    </button>
                  ) : c.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={rowKey(r)}
              className={cx("border-b border-line last:border-0", onRowClick && "cursor-pointer hover:bg-surface-2")}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              onKeyDown={onRowClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onRowClick(r); } } : undefined}
              tabIndex={onRowClick ? 0 : undefined}>
              {columns.map((c) => (
                <td key={c.key} className={cx("px-3 py-2 align-top", c.align === "right" && "num text-right", c.hideOnMobile && "hidden md:table-cell", c.className)}>
                  {c.render ? c.render(r) : String((r as Record<string, unknown>)[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
