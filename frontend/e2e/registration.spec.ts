/**
 * E2E тест: регистрация организации.
 *
 * Требования для запуска:
 * 1. Backend: docker compose up -d postgres redis backend
 * 2. Миграции: cd backend && alembic upgrade head
 * 3. Frontend: pnpm dev (или использует reuseExistingServer)
 * 4. Запуск: pnpm e2e
 */

import { test, expect } from "@playwright/test";

test.describe("Registration flow", () => {
  test("user can register and see moderation message", async ({ page }) => {
    await page.goto("/register");

    // Ждём загрузки формы
    await expect(
      page.getByRole("heading", { name: /регистраци/i })
    ).toBeVisible();

    const timestamp = Date.now();

    // Заполняем форму через data-testid
    await page.getByTestId("register-email").fill(`e2e-${timestamp}@example.com`);
    await page.getByTestId("register-password").fill("StrongPass123!");
    await page.getByTestId("register-password-confirm").fill("StrongPass123!");
    await page.getByTestId("register-first-name").fill("Иван");
    await page.getByTestId("register-last-name").fill("Иванов");
    await page.getByTestId("register-org-name").fill("E2E Test Org");
    await page
      .getByTestId("register-org-slug")
      .fill(`e2e-test-org-${timestamp.toString(36)}`);

    // Принимаем условия
    await page.getByTestId("register-consent-privacy").check();
    await page.getByTestId("register-consent-offer").check();

    // Отправляем форму
    await page.getByTestId("register-submit").click();

    // Ждём сообщение об отправке на модерацию
    await expect(page.getByText(/заявка отправлена|на модерации/i)).toBeVisible({
      timeout: 10000,
    });
  });
});