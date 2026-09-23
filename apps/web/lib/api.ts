"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

// Hospedagem gratuita hiberna após inatividade: a primeira chamada pode receber
// 502/503/504 ou falhar na rede enquanto a API e o banco acordam. Leituras (GET)
// são repetidas com espera crescente, e a interface mostra "Iniciando…".
const RETRY_STATUS = new Set([502, 503, 504]);
const RETRY_DELAYS_MS = [1500, 3000, 5000, 8000, 10000, 12000, 15000, 15000];

let waking = 0;
const listeners = new Set<() => void>();
function setWaking(delta: number) {
  waking = Math.max(0, waking + delta);
  listeners.forEach((l) => l());
}
/** true enquanto alguma leitura está aguardando a API acordar. */
export function useApiWaking() {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    () => waking > 0,
    () => false,
  );
}

async function once(path: string, init?: RequestInit): Promise<{ res: Response | null; text: string }> {
  try {
    const res = await fetch(`/api/${path}`, { ...init, headers: { "content-type": "application/json" } });
    return { res, text: await res.text() };
  } catch {
    return { res: null, text: "" };
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const retriable = !init?.method || init.method === "GET";
  let { res, text } = await once(path, init);
  if (retriable && (!res || RETRY_STATUS.has(res.status))) {
    setWaking(1);
    try {
      for (const delay of RETRY_DELAYS_MS) {
        await new Promise((r) => setTimeout(r, delay));
        ({ res, text } = await once(path, init));
        if (res && !RETRY_STATUS.has(res.status)) break;
      }
    } finally {
      setWaking(-1);
    }
  }
  if (!res) throw new ApiError("Sem conexão com o servidor. Verifique a internet e tente novamente.", 0);
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail = (body as { detail?: unknown })?.detail;
    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? "Parâmetros inválidos." : `Erro ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return body as T;
}

export type AsyncState<T> = { data: T | null; error: ApiError | null; loading: boolean; reload: () => void };

/** Busca GET com estados de carregamento/erro; descarta respostas antigas.
 *  Mantém o último dado enquanto recarrega (a tela esmaece em vez de piscar). */
export function useApi<T>(path: string | null): AsyncState<T> {
  const [tick, setTick] = useState(0);
  const key = path ? `${path}#${tick}` : null;
  const [res, setRes] = useState<{ key: string | null; data: T | null; error: ApiError | null }>({ key: null, data: null, error: null });

  useEffect(() => {
    if (!key || !path) return;
    let alive = true;
    apiFetch<T>(path)
      .then((d) => { if (alive) setRes({ key, data: d, error: null }); })
      .catch((e: unknown) => {
        if (alive) setRes((prev) => ({ key, data: prev.data, error: e instanceof ApiError ? e : new ApiError(String(e), 0) }));
      });
    return () => { alive = false; };
  }, [key, path]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const loading = key !== null && res.key !== key;
  return { data: res.data, error: loading ? null : res.error, loading, reload };
}
