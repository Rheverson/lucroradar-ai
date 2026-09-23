#!/usr/bin/env bash
# Executa o teste da lógica do workflow n8n e grava um JUnit mínimo com o resultado real.
set -u
cd "$(dirname "$0")/.."
mkdir -p reports
if node automations/n8n/test_check_conditions.mjs; then f=0; else f=1; fi
printf '<testsuite name="n8n" tests="1" failures="%s" skipped="0"><testcase name="check_conditions"/></testsuite>\n' "$f" > reports/n8n.xml
exit $f
