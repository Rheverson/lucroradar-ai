import { expect, test } from "@playwright/test";

test("1. identifica a queda de margem na visão executiva", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Explorar demonstração" }).click();
  await expect(page).toHaveURL(/\/executivo/);
  await expect(page.getByRole("heading", { name: /Estou vendendo mais/ })).toBeVisible();
  await expect(page.getByText("Dados sintéticos").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Receita líquida" })).toBeVisible();
  await expect(page.getByText(/Margem de contribuição caiu/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "O que explica a variação da margem" })).toBeVisible();
});

test("filtros compartilhados alteram os números e persistem entre telas", async ({ page }) => {
  await page.goto("/executivo");
  const kpi = page.locator("section", { has: page.getByRole("heading", { name: "Receita líquida" }) }).locator("p.num").first();
  await expect(kpi).toContainText("R$");
  const before = await kpi.textContent();
  await page.getByLabel("Segmento").selectOption("Eventos");
  await expect(page).toHaveURL(/segment=Eventos/);
  await expect(kpi).not.toHaveText(before ?? "");
  await page.getByRole("link", { name: "Clientes e produtos" }).first().click();
  await expect(page).toHaveURL(/clientes-produtos.*segment=Eventos/);
  await expect(page.getByLabel("Segmento")).toHaveValue("Eventos");
});

test("2. investiga cliente até o registro de origem", async ({ page }) => {
  await page.goto("/clientes-produtos");
  const firstRow = page.locator("table tbody tr").first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByText("Linhas de venda faturadas")).toBeVisible();
  await drawer.getByRole("button", { name: /Ver registro de origem/ }).first().click();
  await expect(page.getByText(/Registro preservado na camada/)).toBeVisible();
  await expect(page.getByText("order_item_id").last()).toBeVisible();
});

test("3. pergunta ao copiloto no modo demonstração", async ({ page }) => {
  await page.goto("/copiloto");
  await page.getByRole("button", { name: /Por que a margem de contribuição caiu/ }).click();
  const answer = page.locator("article").first();
  await expect(answer.getByText("Demonstração sem modelo generativo")).toBeVisible();
  await expect(answer.getByText("Evidências (calculadas no servidor)")).toBeVisible();
  await expect(answer.getByText("E1", { exact: true })).toBeVisible();
  await expect(answer.getByText(/não comprovam causa/)).toBeVisible();
});

test("4 e 5. simula e gera proposta; restaurar volta à base", async ({ page }) => {
  await page.goto("/simulador");
  const diff = page.getByRole("row", { name: /^Margem de contribuição R\$/ }).locator("td").last();
  await expect(diff).toContainText("R$ 0");
  const slider = page.getByLabel("Desconto médio na venda");
  await slider.focus();
  for (let i = 0; i < 4; i++) await page.keyboard.press("ArrowLeft");
  await expect(page.locator("output[for=disc]")).toContainText("-2");
  await expect(diff).toContainText("+R$", { timeout: 10_000 });
  await expect(diff).not.toContainText("+R$ 0");
  await page.getByRole("button", { name: "Gerar proposta" }).click();
  await expect(page.getByText(/Revisar a alçada de desconto/)).toBeVisible();
  await page.getByRole("button", { name: "Restaurar" }).click();
  await expect(page.locator("output[for=disc]")).toContainText("0");
  await expect(diff).toContainText("R$ 0", { timeout: 10_000 });
});

test("qualidade dos dados mostra reconciliação e duplicidades", async ({ page }) => {
  await page.goto("/qualidade");
  await expect(page.getByRole("heading", { name: "Reconciliação de totais" })).toBeVisible();
  await expect(page.getByText("divergente")).toHaveCount(0);
  await expect(page.getByText(/Nenhum cadastro é unificado automaticamente/)).toBeVisible();
});

test("operações mostra utilização, manutenção e etapas", async ({ page }) => {
  await page.goto("/operacoes");
  await expect(page.getByRole("heading", { name: "Utilização da frota por produto" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Equipamentos em manutenção" })).toBeVisible();
  await expect(page.getByText("Análise de crédito").first()).toBeVisible();
});

test("navegação por teclado: link para pular ao conteúdo @mobile", async ({ page }) => {
  await page.goto("/executivo");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Pular para o conteúdo" })).toBeFocused();
});

test("layout sem rolagem horizontal no celular @mobile", async ({ page }) => {
  test.setTimeout(180_000);
  for (const path of ["/", "/executivo", "/clientes-produtos", "/operacoes", "/qualidade", "/simulador", "/copiloto", "/como-foi-construido"]) {
    await page.goto(path);
    await page.waitForLoadState("load");
    await expect(page.locator("h1").first()).toBeVisible();
    await page.waitForTimeout(2500); // dados carregados (gráficos/tabelas influenciam a largura)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(1);
  }
});
