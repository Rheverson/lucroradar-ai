import type { Metadata } from "next";
import "@fontsource-variable/inter";
import { Suspense } from "react";
import { FiltersProvider } from "@/lib/filters";
import "./globals.css";

// URL pública usada nos links de compartilhamento. Na Vercel, cai no domínio de produção do projeto.
const SITE_URL =
  process.env.SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "http://localhost:3000");
const DESCRIPTION =
  "Estou vendendo mais. Por que o dinheiro não está sobrando? Demonstração de margem, caixa e produtividade com dados sintéticos de uma empresa fictícia, copiloto com evidências e simulações.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "LucroRadar AI — margem, caixa e produtividade", template: "%s · LucroRadar AI" },
  description: DESCRIPTION,
  applicationName: "LucroRadar AI",
  openGraph: {
    type: "website",
    locale: "pt_BR",
    siteName: "LucroRadar AI",
    title: "LucroRadar AI — Por que o dinheiro não está sobrando?",
    description: DESCRIPTION,
    url: "/",
  },
  twitter: { card: "summary_large_image", title: "LucroRadar AI", description: DESCRIPTION },
};

// Aplica o tema antes da hidratação (evita piscar). Preferência salva > sistema.
const themeScript = `(function(){try{var t=localStorage.getItem('lr-theme');if(!t){t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme='light'}})()`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="font-sans">
        <Suspense fallback={null}>
          <FiltersProvider>{children}</FiltersProvider>
        </Suspense>
      </body>
    </html>
  );
}
