"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useApi } from "@/lib/api";
import { ErrorState, LoadingBlock } from "./ui";

export function Drawer({ open, onClose, title, children, wide = false }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={title}>
      <button aria-label="Fechar" className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div ref={ref} tabIndex={-1} className={`animate-rise absolute right-0 top-0 flex h-full w-full flex-col border-l border-line bg-surface shadow-2xl outline-none ${wide ? "max-w-4xl" : "max-w-xl"}`}>
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <h2 className="min-w-0 truncate text-base font-semibold">{title}</h2>
          <button onClick={onClose} className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-surface-2" aria-label="Fechar painel">
            <X className="size-5" aria-hidden />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

type SourceRecord = { table: string; fields: Record<string, string>; lineage: Record<string, string> };

/** Mostra o registro exatamente como chegou no arquivo de origem (camada raw). */
export function SourceRecordView({ table, batch, row }: { table: string; batch: string; row: number }) {
  const rec = useApi<SourceRecord>(`v1/source-record/${table}/${batch}/${row}`);
  if (rec.error) return <ErrorState message={rec.error.message} onRetry={rec.reload} />;
  if (!rec.data) return <LoadingBlock rows={6} />;
  return (
    <div className="space-y-4 text-sm">
      <p className="text-ink-2">
        Registro preservado na camada <strong>raw</strong>, sem limpeza, exatamente como recebido no arquivo
        <code className="mx-1 rounded bg-surface-2 px-1">{rec.data.lineage._source_file}</code>
        (lote <code className="rounded bg-surface-2 px-1">{rec.data.lineage._batch_id}</code>, linha {rec.data.lineage._row_number}).
      </p>
      <dl className="grid grid-cols-[minmax(0,10rem)_1fr] gap-x-4 gap-y-1.5 rounded-xl border border-line p-4">
        {Object.entries(rec.data.fields).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="font-mono text-xs text-muted">{k}</dt>
            <dd className="break-all font-mono text-xs text-ink">{v === "" || v == null ? <span className="text-bad">(vazio)</span> : v}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-muted">Hash do conteúdo: <code>{rec.data.lineage._record_hash}</code> · carregado em {new Date(rec.data.lineage._loaded_at).toLocaleString("pt-BR")}</p>
    </div>
  );
}
