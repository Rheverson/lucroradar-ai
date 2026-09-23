"use client";

import { Sparkline } from "./charts";
import { Card, cx, Delta } from "./ui";
import type { Cmp } from "@/lib/types";
import { pp, signedPct } from "@/lib/format";

export function KpiCard({
  label, value, cmp, goodWhen = "up", hint, spark, sparkColor, secondary, compareLabel,
}: {
  label: string; value: string; cmp: Cmp; goodWhen?: "up" | "down"; hint?: string;
  spark?: number[]; sparkColor?: string; secondary?: React.ReactNode; compareLabel?: string;
}) {
  const deltaVal = cmp.kind === "ratio" ? cmp.delta : cmp.delta_pct;
  const text = cmp.kind === "ratio" ? pp(cmp.delta) : signedPct(cmp.delta_pct);
  return (
    <Card className="animate-rise flex flex-col gap-2 !p-5">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-ink-2" title={hint}>{label}</h3>
      </div>
      <p className="num text-[28px] font-semibold leading-none tracking-tight text-ink">{value}</p>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Delta value={deltaVal} kind={cmp.kind} goodWhen={goodWhen} text={text} />
      </div>
      {secondary && <div className="text-xs text-muted">{secondary}</div>}
      {spark && spark.length > 1 && <Sparkline values={spark} color={sparkColor} />}
      {hint && <p className={cx("text-[11px] leading-snug text-muted")}>{hint}{compareLabel ? ` Comparação: ${compareLabel}.` : ""}</p>}
    </Card>
  );
}
