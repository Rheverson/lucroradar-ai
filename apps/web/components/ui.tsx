"use client";

import { AlertTriangle, CircleCheck, CircleX, Info, RefreshCw, SearchX } from "lucide-react";
import type { ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cx("min-w-0 rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)] sm:p-6", className)}>
      {children}
    </section>
  );
}

export function SectionTitle({ title, subtitle, right, as = "h2" }: { title: string; subtitle?: ReactNode; right?: ReactNode; as?: "h2" | "h3" }) {
  const H = as;
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <H className={cx("font-semibold tracking-tight text-ink", as === "h2" ? "text-lg" : "text-base")}>{title}</H>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, right }: { eyebrow?: string; title: string; description?: ReactNode; right?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">{eyebrow}</p>}
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 text-[15px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {right}
    </header>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("skeleton", className)} />;
}

export function LoadingBlock({ label = "Carregando dados…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={cx("h-6", i === 0 ? "w-1/3" : "w-full")} />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const unavailable = /indispon|503/i.test(message);
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-line bg-bad-bg/50 p-4 text-sm">
      <div className="flex items-center gap-2 font-medium text-bad">
        <CircleX className="size-4" aria-hidden />
        {unavailable ? "Serviço indisponível" : "Não foi possível carregar"}
      </div>
      <p className="text-ink-2">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-2">
          <RefreshCw className="size-3.5" aria-hidden /> Tentar novamente
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title = "Sem dados para os filtros atuais", hint }: { title?: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line p-8 text-center text-sm">
      <SearchX className="size-5 text-muted" aria-hidden />
      <p className="font-medium text-ink">{title}</p>
      {hint && <p className="max-w-md text-muted">{hint}</p>}
    </div>
  );
}

const STATUS = {
  good: { icon: CircleCheck, cls: "bg-good-bg text-good" },
  warn: { icon: AlertTriangle, cls: "bg-warn-bg text-warn" },
  bad: { icon: CircleX, cls: "bg-bad-bg text-bad" },
  info: { icon: Info, cls: "bg-surface-2 text-ink-2 border border-line" },
};

export function StatusBadge({ tone, children }: { tone: keyof typeof STATUS; children: ReactNode }) {
  const { icon: Icon, cls } = STATUS[tone];
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", cls)}>
      <Icon className="size-3.5" aria-hidden />
      {children}
    </span>
  );
}

export function Tag({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx("inline-flex items-center rounded-md bg-surface-2 px-1.5 py-0.5 text-xs font-medium text-ink-2 ring-1 ring-line", className)}>{children}</span>;
}

export function Button({ children, variant = "primary", className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const v = {
    primary: "bg-brand text-white hover:bg-brand-2 dark:text-[#0a111e]",
    secondary: "border border-line bg-surface text-ink hover:bg-surface-2",
    ghost: "text-ink-2 hover:bg-surface-2",
  }[variant];
  return <button className={cx(base, v, className)} {...rest}>{children}</button>;
}

export function Delta({ value, kind, goodWhen = "up", text }: { value: number | null; kind: "money" | "ratio"; goodWhen?: "up" | "down"; text: string }) {
  if (value == null) return <span className="text-xs text-muted">sem comparação</span>;
  const good = goodWhen === "up" ? value >= 0 : value <= 0;
  return (
    <span className={cx("num inline-flex items-center gap-1 text-xs font-medium", good ? "text-good" : "text-bad")}>
      <span aria-hidden>{value >= 0 ? "▲" : "▼"}</span>
      {text}
      <span className="sr-only">{good ? "(favorável)" : "(desfavorável)"}</span>
      <span className="font-normal text-muted">{kind === "ratio" ? "" : " vs. comparação"}</span>
    </span>
  );
}
