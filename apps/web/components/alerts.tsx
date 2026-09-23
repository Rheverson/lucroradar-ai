"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { linkHref } from "@/lib/filters";
import type { Alert } from "@/lib/types";
import { StatusBadge } from "./ui";

const SEV = { high: { tone: "bad", label: "Alta" }, medium: { tone: "warn", label: "Média" }, low: { tone: "info", label: "Baixa" } } as const;

export function AlertList({ alerts, compact = false }: { alerts: Alert[]; compact?: boolean }) {
  if (!alerts.length) {
    return <p className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">Nenhum alerta ativo com os filtros atuais.</p>;
  }
  return (
    <ol className="space-y-3">
      {alerts.map((a) => (
        <li key={a.id} className="rounded-xl border border-line bg-surface-2/60 p-4">
          <details open={!compact} className="group">
            <summary className="flex cursor-pointer list-none items-start gap-3 [&::-webkit-details-marker]:hidden">
              <StatusBadge tone={SEV[a.severity].tone}>{SEV[a.severity].label}</StatusBadge>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-ink">{a.title}</span>
                <span className="mt-1 block text-sm text-ink-2">{a.summary}</span>
              </span>
              <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted transition-transform group-open:rotate-90" aria-hidden />
            </summary>
            <dl className="mt-3 grid gap-1.5 border-t border-line pt-3 text-xs">
              {a.evidence.map((e) => (
                <div key={e.label} className="flex flex-wrap justify-between gap-x-3">
                  <dt className="text-muted">{e.label}</dt>
                  <dd className="num font-medium text-ink">{e.value}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-muted">Regra: {a.rule}</span>
              <Link href={linkHref(a.link)} className="font-medium text-brand-2 underline-offset-2 hover:underline">
                Ver evidência →
              </Link>
            </div>
          </details>
        </li>
      ))}
    </ol>
  );
}
