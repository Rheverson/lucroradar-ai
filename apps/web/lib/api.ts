"use client";

import { useCallback, useEffect, useState } from "react";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/${path}`, { ...init, headers: { "content-type": "application/json" } });
  const text = await res.text();
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
