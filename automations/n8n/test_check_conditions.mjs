// node automations/n8n/test_check_conditions.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { checkConditions } = require("./check_conditions.js");
const summary = JSON.parse(readFileSync(new URL("./examples/summary-response.json", import.meta.url)));
const cfg = { margin_drop_pp: 1.5, overdue_growth_pct: 0.15, min_high_alerts: 1 };

const out = checkConditions(summary, cfg);
assert.equal(out.synthetic_data, true);
assert.ok(out.body.includes("Resumo executivo"));
assert.equal(out.should_alert, summary.high_severity_count >= 1 || out.reasons.length > 0);

const calm = checkConditions({ ...summary, high_severity_count: 0,
  kpis: { ...summary.kpis, margin_pct: { ...summary.kpis.margin_pct, delta: 0.01 }, overdue: { ...summary.kpis.overdue, delta_pct: 0 } } }, cfg);
assert.equal(calm.should_alert, false);
assert.ok(calm.subject.startsWith("[LucroRadar] Resumo executivo"));
console.log("check_conditions: ok —", out.subject);
