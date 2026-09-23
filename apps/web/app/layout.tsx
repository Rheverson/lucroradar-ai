import type { Metadata } from "next";
import "@fontsource-variable/inter";
import { Suspense } from "react";
import { FiltersProvider } from "@/lib/filters";
import "./globals.css";

export const metadata: Metadata = {
  title: "LucroRadar AI",
  description: "Estou vendendo mais. Por que o dinheiro não está sobrando? Plataforma de margem, caixa e produtividade com dados sintéticos.",
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
