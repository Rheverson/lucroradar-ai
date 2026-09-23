"use client";

import { Activity, Bot, Building2, Database, Gauge, Hammer, Menu, Moon, SlidersHorizontal, Sun, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useFilters } from "@/lib/filters";
import { cx } from "./ui";

export const NAV = [
  { href: "/executivo", label: "Visão executiva", icon: Gauge },
  { href: "/clientes-produtos", label: "Clientes e produtos", icon: Users },
  { href: "/operacoes", label: "Operações e locações", icon: Activity },
  { href: "/qualidade", label: "Qualidade dos dados", icon: Database },
  { href: "/simulador", label: "Simulador", icon: SlidersHorizontal },
  { href: "/copiloto", label: "Copiloto", icon: Bot },
  { href: "/como-foi-construido", label: "Como foi construído", icon: Hammer },
];

function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);
  useEffect(() => {
    // o tema é definido por script antes da hidratação; aqui só sincronizamos o ícone
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme((document.documentElement.dataset.theme as "light" | "dark") ?? "light");
  }, []);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("lr-theme", next); } catch {}
    setTheme(next);
  };
  return (
    <button onClick={toggle} className="inline-flex size-9 items-center justify-center rounded-lg text-ink-2 hover:bg-surface-2" aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema escuro"}>
      {theme === "dark" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
    </button>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { withQuery } = useFilters();
  return (
    <ul className="space-y-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <li key={href}>
            <Link
              href={withQuery(href)}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-brand text-white dark:text-[#0a111e]" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
              )}
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="grid size-8 place-items-center rounded-xl bg-brand text-white dark:text-[#0a111e]" aria-hidden>
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 17l5-5 4 3 7-8" /><circle cx="19" cy="7" r="2" fill="var(--accent)" stroke="none" /></svg>
      </span>
      <span className="leading-tight">
        <span className="block text-[15px] font-semibold tracking-tight text-ink">LucroRadar <span className="text-accent">AI</span></span>
        <span className="block text-[11px] text-muted">Margem · Caixa · Produtividade</span>
      </span>
    </Link>
  );
}

export function SyntheticBanner() {
  const { meta } = useFilters();
  return (
    <div className="flex items-center gap-2 border-b border-line bg-accent-soft px-4 py-1.5 text-xs text-ink-2 sm:px-6">
      <Building2 className="size-3.5 shrink-0 text-accent" aria-hidden />
      <span>
        <strong className="font-semibold text-ink">Dados sintéticos</strong> de uma empresa fictícia
        {meta ? ` · referência ${new Date(`${meta.reference_date}T12:00:00`).toLocaleDateString("pt-BR")}` : ""} · demonstração sem login, somente leitura
      </span>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[260px_1fr]">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">Pular para o conteúdo</a>
      <aside className="hidden border-r border-line bg-surface lg:flex lg:h-dvh lg:flex-col lg:sticky lg:top-0" aria-label="Navegação principal">
        <div className="px-5 py-5"><Brand /></div>
        <nav className="flex-1 overflow-y-auto px-3"><NavLinks /></nav>
        <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-muted">
          <span>Portfólio · dados fictícios</span>
          <ThemeToggle />
        </div>
      </aside>
      <div className="min-w-0">
        <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-surface/95 px-4 py-3 backdrop-blur lg:hidden">
          <Brand />
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <button onClick={() => setOpen(true)} className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-surface-2" aria-label="Abrir menu" aria-expanded={open}>
              <Menu className="size-5" aria-hidden />
            </button>
          </div>
        </div>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
            <button className="absolute inset-0 bg-black/40" aria-label="Fechar menu" onClick={() => setOpen(false)} />
            <nav className="animate-rise absolute right-0 top-0 h-full w-72 max-w-[85%] border-l border-line bg-surface p-4">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-sm font-semibold">Navegação</span>
                <button onClick={() => setOpen(false)} className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-surface-2" aria-label="Fechar menu"><X className="size-5" aria-hidden /></button>
              </div>
              <NavLinks onNavigate={() => setOpen(false)} />
            </nav>
          </div>
        )}
        <SyntheticBanner />
        <main id="conteudo" className="mx-auto w-full max-w-[1320px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
