"""Consolida os relatórios reais dos testes em apps/web/public/test-summary.json.

Lê apenas arquivos produzidos pelas ferramentas (JUnit do pytest e do Playwright,
run_results.json do dbt). Suítes sem relatório ficam de fora — nada é inventado.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps" / "web" / "public" / "test-summary.json"


def junit(path: Path, name: str, tool: str, command: str) -> dict | None:
    if not path.exists():
        return None
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(s.get("tests", 0)) for s in suites)
    failed = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    return {"name": name, "tool": tool, "command": command, "total": total, "failed": failed,
            "skipped": skipped, "passed": total - failed - skipped}


def dbt(path: Path) -> dict | None:
    if not path.exists():
        return None
    results = json.loads(path.read_text())["results"]
    tests = [r for r in results if r["unique_id"].startswith("test.")]
    failed = sum(1 for r in tests if r["status"] in ("fail", "error"))
    return {"name": "Testes de dados (dbt)", "tool": "dbt build", "command": "dbt build",
            "total": len(tests), "failed": failed, "skipped": sum(1 for r in tests if r["status"] == "skipped"),
            "passed": sum(1 for r in tests if r["status"] == "pass")}


def main() -> None:
    suites = [s for s in [
        junit(ROOT / "reports" / "pytest.xml", "Python (unitários, integração e avaliações do copiloto)", "pytest",
              "pytest --junitxml=reports/pytest.xml"),
        dbt(ROOT / "analytics" / "dbt" / "target" / "run_results.json"),
        junit(ROOT / "apps" / "web" / "test-results" / "e2e-junit.xml", "Ponta a ponta (Playwright)", "Playwright",
              "npx playwright test"),
        junit(ROOT / "reports" / "n8n.xml", "Workflow n8n (lógica de condições)", "node", "node automations/n8n/test_check_conditions.mjs"),
    ] if s]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "suites": suites},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for s in suites:
        print(f"{s['name']}: {s['passed']}/{s['total']} (falhas: {s['failed']})")


if __name__ == "__main__":
    main()
