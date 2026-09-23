// Proxy para a API FastAPI. A URL interna vem de API_URL (servidor); o navegador
// nunca vê credenciais nem o endereço interno.
import type { NextRequest } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const ALLOWED = /^(health|v1\/[a-z0-9\-/._]+)$/i;
const MAX_BODY_BYTES = 8 * 1024; // perguntas e parâmetros do simulador são pequenos

// IP do visitante repassado à API (usado nos limites do copiloto). Só é confiável
// porque a API aceita X-Forwarded-For apenas quando TRUST_FORWARDED_FOR=true.
function clientIp(req: NextRequest) {
  const fwd = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return fwd || req.headers.get("x-real-ip") || "";
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
  if (ip) headers["x-forwarded-for"] = ip;
  try {
    const res = await fetch(url, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(req.method === "POST" && joined.includes("copilot") ? 120_000 : 30_000),
    });
    const text = await res.text();
    return new Response(text, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { detail: "API indisponível. Verifique se o serviço da API está em execução." },
      { status: 503 },
    );
  }
}

export const GET = forward;
export const POST = forward;
