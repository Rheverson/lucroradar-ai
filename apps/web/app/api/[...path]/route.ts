// Proxy para a API FastAPI. A URL interna vem de API_URL (servidor); o navegador
// nunca vê credenciais nem o endereço interno.
import type { NextRequest } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const ALLOWED = /^(health|v1\/[a-z0-9\-/._]+)$/i;
const MAX_BODY_BYTES = 8 * 1024; // perguntas e parâmetros do simulador são pequenos

// Segredo compartilhado com a API (só no servidor). Com ele definido, a API recusa
// chamadas diretas e aceita o IP do visitante informado por este proxy.
const PROXY_TOKEN = process.env.PROXY_SHARED_SECRET ?? "";

// IP do visitante (limites do copiloto). Na Vercel, x-real-ip e x-forwarded-for são
// definidos pela borda e sobrescrevem o que o cliente enviar; no Compose, pelo Docker.
function clientIp(req: NextRequest) {
  const real = req.headers.get("x-real-ip")?.trim();
  const fwd = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return (real || fwd || "").slice(0, 64);
}

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const joined = path.join("/");
  if (!ALLOWED.test(joined)) {
    return Response.json({ detail: "Rota não permitida" }, { status: 404 });
  }
  const url = `${API_URL}/api/${joined}${req.nextUrl.search}`;
  let body: string | undefined;
  if (req.method === "POST") {
    body = await req.text();
    if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) {
      return Response.json({ detail: "Requisição muito grande." }, { status: 413 });
    }
  }
  const headers: Record<string, string> = { "content-type": "application/json" };
  const ip = clientIp(req);
  if (PROXY_TOKEN) {
    headers["x-lr-proxy-token"] = PROXY_TOKEN;
    if (ip) headers["x-lr-client-ip"] = ip;
  } else if (ip) {
    headers["x-forwarded-for"] = ip;
  }
  try {
    const res = await fetch(url, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(req.method === "POST" && joined.includes("copilot") ? 120_000 : 30_000),
    });
    const text = await res.text();
    const contentType = res.headers.get("content-type") ?? "";
    // Erro 5xx fora do formato da API (ex.: falha da plataforma ao iniciar a função)
    // vira 503 genérico: não repassa detalhes e permite nova tentativa no front-end.
    if (res.status >= 500 && !contentType.includes("application/json")) return unavailable();
    return new Response(text, {
      status: res.status,
      headers: { "content-type": contentType || "application/json" },
    });
  } catch {
    return unavailable();
  }
}

// Serviços gratuitos hibernam: a primeira chamada após o repouso pode falhar ou
// demorar. O front-end mostra "iniciando" e tenta de novo.
function unavailable() {
  return Response.json(
    { detail: "A API está iniciando ou indisponível. Tente novamente em alguns segundos.", code: "api_unavailable" },
    { status: 503, headers: { "retry-after": "5" } },
  );
}

export const GET = forward;
export const POST = forward;
