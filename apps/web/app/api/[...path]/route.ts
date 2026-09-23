// Proxy para a API FastAPI. A URL interna vem de API_URL (servidor); o navegador
// nunca vê credenciais nem o endereço interno.
import type { NextRequest } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const ALLOWED = /^(health|v1\/[a-z0-9\-/._]+)$/i;

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const joined = path.join("/");
  if (!ALLOWED.test(joined)) {
    return Response.json({ detail: "Rota não permitida" }, { status: 404 });
  }
  const url = `${API_URL}/api/${joined}${req.nextUrl.search}`;
  try {
    const res = await fetch(url, {
      method: req.method,
      headers: { "content-type": "application/json" },
      body: req.method === "POST" ? await req.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(req.method === "POST" && joined.includes("copilot") ? 120_000 : 30_000),
    });
    const body = await res.text();
    return new Response(body, {
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
