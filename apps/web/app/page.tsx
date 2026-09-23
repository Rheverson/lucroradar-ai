import { ArrowRight, Bot, Database, Gauge, SlidersHorizontal, Users } from "lucide-react";
import Link from "next/link";
import { Brand } from "@/components/shell";

const STEPS = [
  { icon: Gauge, title: "Identificar a queda de margem", text: "Receita, margem de contribuição, recebimentos e vencidos com comparação de período.", href: "/executivo" },
  { icon: Users, title: "Investigar clientes, produtos e contratos", text: "Da visão agregada até a linha do arquivo de origem.", href: "/clientes-produtos" },
  { icon: Bot, title: "Perguntar ao copiloto", text: "Respostas com evidências calculadas no servidor, filtros e limitações.", href: "/copiloto" },
  { icon: SlidersHorizontal, title: "Simular mudanças", text: "Desconto, utilização da frota e prazo de recebimento, com premissas visíveis.", href: "/simulador" },
  { icon: Database, title: "Gerar proposta fundamentada", text: "Ações ligadas aos alertas e ao cenário simulado, prontas para discutir.", href: "/simulador#proposta" },
];

export default function Home() {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Brand />
        <Link href="/como-foi-construido" className="text-sm font-medium text-ink-2 hover:text-ink">Como foi construído</Link>
      </header>
      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        <section className="relative overflow-hidden rounded-3xl bg-brand px-6 py-12 text-white sm:px-12 sm:py-16 dark:bg-[#0f2440]">
          <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-[radial-gradient(circle,rgba(27,175,122,0.45),transparent_65%)]" />
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">Inteligência de margem, caixa e produtividade</p>
          <h1 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight tracking-tight sm:text-5xl">
            “Estou vendendo mais. Por que o dinheiro não está sobrando?”
          </h1>
          <p className="mt-4 max-w-2xl text-base text-blue-100 sm:text-lg">
            O LucroRadar AI separa receita, margem de contribuição e caixa, mostra o que puxou a margem para baixo e
            onde o dinheiro ficou preso — com números conciliados, qualidade de dados visível e um copiloto que só
            responde com evidências.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/executivo" className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-[#0b2f5b] shadow-sm hover:bg-blue-50">
              Explorar demonstração <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link href="/copiloto" className="inline-flex items-center gap-2 rounded-xl border border-white/30 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10">
              Perguntar ao copiloto
            </Link>
          </div>
          <p className="mt-6 text-xs text-blue-200">
            Dados 100% sintéticos de uma empresa fictícia de venda e locação de equipamentos. Sem login; nada do que você fizer altera os dados compartilhados.
          </p>
        </section>

        <section aria-labelledby="jornada" className="mt-12">
          <h2 id="jornada" className="text-xl font-semibold tracking-tight">A jornada em cinco passos</h2>
          <ol className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {STEPS.map(({ icon: Icon, title, text, href }, i) => (
              <li key={title}>
                <Link href={href} className="group flex h-full flex-col rounded-2xl border border-line bg-surface p-5 hover:border-brand-2">
                  <span className="flex items-center gap-2 text-xs font-semibold text-accent">
                    <span className="grid size-6 place-items-center rounded-full bg-accent-soft">{i + 1}</span>
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <span className="mt-3 text-sm font-semibold text-ink">{title}</span>
                  <span className="mt-1 text-xs leading-relaxed text-muted">{text}</span>
                </Link>
              </li>
            ))}
          </ol>
        </section>

        <section className="mt-12 grid gap-4 md:grid-cols-3">
          {[
            ["Engenharia de dados", "Lotes inicial e incremental, reexecução sem duplicação, quarentena, testes de integridade e reconciliação de totais."],
            ["Regras de negócio explícitas", "Receita reconhecida × recebimento, margem de contribuição × lucro, utilização com denominador declarado."],
            ["IA com evidências", "Ferramentas controladas, sem SQL gerado pelo modelo; modo demonstração funciona sem chave de API."],
          ].map(([t, d]) => (
            <div key={t} className="rounded-2xl border border-line bg-surface p-5">
              <h3 className="text-sm font-semibold">{t}</h3>
              <p className="mt-1 text-sm text-ink-2">{d}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
