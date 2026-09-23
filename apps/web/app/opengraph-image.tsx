import { ImageResponse } from "next/og";

export const alt = "LucroRadar AI — Estou vendendo mais. Por que o dinheiro não está sobrando?";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Imagem de compartilhamento gerada no build (sem fontes ou imagens externas).
export default function OpengraphImage() {
  const bars = [52, 60, 66, 74, 82, 90];
  const margin = [40, 36, 31, 27, 22, 18];
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#0b2f5b", color: "white", padding: 64, fontFamily: "sans-serif" }}>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: 700 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ width: 56, height: 56, borderRadius: 14, background: "#1baf7a", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 30, fontWeight: 700 }}>L</div>
            <div style={{ display: "flex", fontSize: 36, fontWeight: 700 }}>
              LucroRadar <span style={{ color: "#5ee0ad", marginLeft: 10 }}>AI</span>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 54, fontWeight: 700, lineHeight: 1.15 }}>“Estou vendendo mais. Por que o dinheiro não está sobrando?”</div>
            <div style={{ fontSize: 26, color: "#c7d8f0", marginTop: 24 }}>Receita, margem de contribuição e caixa — com evidências e simulações.</div>
          </div>
          <div style={{ fontSize: 22, color: "#9fb8da" }}>Demonstração com dados sintéticos de uma empresa fictícia</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "flex-end", marginLeft: 48, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 14, height: 360 }}>
            {bars.map((h, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}>
                <div style={{ width: 20, height: margin[i] * 3, background: "#f2a93b", borderRadius: 6, marginBottom: 8 }} />
                <div style={{ width: 44, height: h * 2.6, background: "#3b82f6", borderRadius: 8 }} />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 24, marginTop: 20, fontSize: 20, color: "#c7d8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 16, height: 16, background: "#3b82f6", borderRadius: 4 }} />receita</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 16, height: 16, background: "#f2a93b", borderRadius: 4 }} />margem %</div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
