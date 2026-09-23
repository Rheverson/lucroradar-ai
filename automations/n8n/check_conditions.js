// Lógica do nó "Verificar condições" do workflow n8n.
// Mantida em arquivo próprio para ser testada fora do n8n (ver test_check_conditions.mjs)
// e embutida no workflow por build_workflow.py.
function checkConditions(summary, config) {
  const k = summary.kpis;
  const brl = (v) => (v == null ? "—" : "R$ " + Math.round(v).toLocaleString("pt-BR"));
  const pct = (v) => (v == null ? "—" : (v * 100).toFixed(1).replace(".", ",") + "%");
  const pp = (v) => (v == null ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(1).replace(".", ",") + " p.p.");
  const reasons = [];
  if (k.margin_pct.delta != null && k.margin_pct.delta <= -config.margin_drop_pp / 100) {
    reasons.push(`Margem de contribuição variou ${pp(k.margin_pct.delta)} (limite: -${config.margin_drop_pp} p.p.)`);
  }
  if (k.overdue.delta_pct != null && k.overdue.delta_pct >= config.overdue_growth_pct) {
    reasons.push(`Saldo vencido cresceu ${pct(k.overdue.delta_pct)} (limite: ${pct(config.overdue_growth_pct)})`);
  }
  if (summary.high_severity_count >= config.min_high_alerts) {
    reasons.push(`${summary.high_severity_count} alerta(s) de severidade alta na API`);
  }
  const period = summary.generated_for.period.label;
  const lines = [
    `Resumo executivo — ${period} (dados sintéticos)`,
    `Receita líquida: ${brl(k.net_revenue.current)} (${pct(k.net_revenue.delta_pct)} vs. comparação)`,
    `Margem de contribuição: ${pct(k.margin_pct.current)} (${pp(k.margin_pct.delta)})`,
    `Recebimentos: ${brl(k.receipts.current)} · Vencidos: ${brl(k.overdue.current)}`,
    "",
    "Alertas:",
    ...summary.alerts.map((a) => `- [${a.severity}] ${a.title}`),
  ];
  return {
    should_alert: reasons.length > 0,
    reasons,
    subject: reasons.length ? `[LucroRadar] Atenção: ${reasons[0]}` : `[LucroRadar] Resumo executivo ${period}`,
    body: [...(reasons.length ? ["Condições acionadas:", ...reasons.map((r) => `• ${r}`), ""] : []), ...lines].join("\n"),
    period,
    synthetic_data: summary.synthetic_data === true,
  };
}

if (typeof module !== "undefined") module.exports = { checkConditions };
