"use client";

import { CircleCheck, Loader2, RefreshCw } from "lucide-react";
import { useApi } from "@/lib/api";

type Health = { status: string; data_loaded?: boolean };

/** Na página inicial, uma única verificação por visita: acorda a API em repouso
 *  enquanto a pessoa lê a apresentação e informa o estado. Sem chamadas periódicas. */
export function WarmupStatus() {
  const h = useApi<Health>("health");
  if (h.data?.status === "ok" && h.data.data_loaded !== false) {
    return (
      <p className="mt-4 inline-flex items-center gap-1.5 text-xs text-emerald-200" role="status">
        <CircleCheck className="size-3.5" aria-hidden /> Demonstração pronta
      </p>
    );
  }
  if (h.error || (h.data && h.data.status !== "ok")) {
    return (
      <p className="mt-4 inline-flex flex-wrap items-center gap-2 text-xs text-blue-100" role="status">
        Os serviços ainda estão iniciando.
        <button onClick={h.reload} className="inline-flex items-center gap-1 rounded-md border border-white/30 px-2 py-0.5 font-medium hover:bg-white/10">
          <RefreshCw className="size-3" aria-hidden /> Tentar novamente
        </button>
      </p>
    );
  }
  return (
    <p className="mt-4 inline-flex items-center gap-1.5 text-xs text-blue-100" role="status">
      <Loader2 className="size-3.5 animate-spin" aria-hidden /> Preparando a demonstração (pode levar até um minuto após um período sem acesso)…
    </p>
  );
}
