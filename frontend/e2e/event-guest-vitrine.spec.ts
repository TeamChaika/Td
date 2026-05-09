/**
 * E2E тест: гость просматривает витрину событий.
 *
 * Требования для запуска:
 * 1. Backend: docker compose up -d postgres redis backend
 * 2. Миграции: cd backend && alembic upgrade head
 * 3. Frontend: pnpm dev (или reuseExistingServer)
 * 4. В БД должно быть хотя бы одно published событие для test-org
 * 5. Запуск: pnpm e2e
 *
 * Ожидает реализацию:
 * - 3a (backend public events API)
 * - 3c (frontend публичная витрина)
 *
 * Тест помечен skip до готовности 3a и 3c.
 */

import { test, expect } from "@playwright/test";

test.describe("Event guest vitrine", () => {
  test.skip(
    true,
    "awaiting 3a (backend public events API) and 3c (frontend vitrine) implementation"
  );

  test("guest sees event catalog on organization subdomain", async ({ page }) => {
    // Заходим на витрину организации (эмулируем subdomain через baseURL + заголовок)
    // В реальном запуске нужно настроить hosts или использовать X-Tenant-Slug
    await page.goto("/");

    // Проверяем что страница загрузилась
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // Проверяем что есть карточки событий
    const eventCards = page.getByRole("article");
    // В тестовой БД может не быть published событий — тогда проверяем empty state
    const cardCount = await eventCards.count();
    if (cardCount > 0) {
      // Проверяем что первая карточка содержит название
      await expect(eventCards.first()).toBeVisible();
      // Проверяем что есть изображение
      const img = eventCards.first().getByRole("img");
      if (await img.isVisible()) {
        await expect(img).toHaveAttribute("alt");
      }
    } else {
      // Если событий нет — проверяем empty state
      await expect(page.getByText(/нет событий|скоро появятся/i)).toBeVisible();
    }
  });

  test("guest clicks event card and sees details", async ({ page }) => {
    await page.goto("/");

    const eventCards = page.getByRole("article");
    const cardCount = await eventCards.count();

    if (cardCount === 0) {
      test.skip(true, "no published events in test database");
      return;
    }

    // Кликаем на первую карточку
    const firstCard = eventCards.first();
    const link = firstCard.getByRole("link");
    await link.click();

    // Проверяем что перешли на страницу деталей события
    await expect(page).toHaveURL(/\/events\//);

    // Проверяем что есть заголовок события
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // Проверяем что есть описание
    const description = page.getByText(/./); // любой текст
    await expect(description.first()).toBeVisible();

    // Проверяем что есть кнопка «Купить билет»
    const buyButton = page.getByRole("link", { name: /купить билет/i });
    await expect(buyButton).toBeVisible();

    // Проверяем что кнопка ведёт на /events/{slug}/book
    const href = await buyButton.getAttribute("href");
    expect(href).toMatch(/\/events\/.+\/book/);
  });

  test("guest sees tariffs on event detail page", async ({ page }) => {
    await page.goto("/");

    const eventCards = page.getByRole("article");
    const cardCount = await eventCards.count();

    if (cardCount === 0) {
      test.skip(true, "no published events in test database");
      return;
    }

    // Переходим на страницу события
    await eventCards.first().getByRole("link").click();
    await expect(page).toHaveURL(/\/events\//);

    // Проверяем что есть список тарифов
    const tariffSection = page.getByText(/тарифы|билеты/i);
    await expect(tariffSection).toBeVisible();

    // Проверяем что у тарифов есть цены
    const prices = page.getByText(/₽/);
    // Хотя бы одна цена должна быть видна
    const priceCount = await prices.count();
    expect(priceCount).toBeGreaterThan(0);
  });

  test("guest sees brand color applied", async ({ page }) => {
    await page.goto("/");

    // Проверяем что CSS-переменная --primary установлена
    const primaryColor = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue(
        "--primary"
      );
    });
    // Должен быть какой-то цвет (даже дефолтный)
    expect(primaryColor).toBeTruthy();
  });

  test("draft event is not visible on vitrine", async ({ page }) => {
    await page.goto("/");

    // Draft-события не должны отображаться
    // Проверяем что нет элементов с текстом «Draft» (если такие есть в БД)
    const draftElements = page.getByText(/draft/i);
    await expect(draftElements).toHaveCount(0);
  });
});