/**
 * E2E тест: организатор создаёт событие через wizard.
 *
 * Требования для запуска:
 * 1. Backend: docker compose up -d postgres redis backend minio
 * 2. Миграции: cd backend && alembic upgrade head
 * 3. Frontend: pnpm dev (или reuseExistingServer)
 * 4. Запуск: pnpm e2e
 *
 * Ожидает реализацию:
 * - 3a (backend events API)
 * - 3b (frontend admin wizard)
 *
 * Тест помечен skip до готовности 3a и 3b.
 */

import { test, expect } from "@playwright/test";

test.describe("Event organizer flow", () => {
  test.skip(
    true,
    "awaiting 3a (backend events API) and 3b (frontend admin wizard) implementation"
  );

  test("organizer creates event through wizard", async ({ page }) => {
    // Шаг 0: Логин как организатор
    await page.goto("/admin/login");
    await page.getByLabel(/email/i).fill("organizer@test-org.example.com");
    await page.getByLabel(/пароль/i).fill("Organizer123!");
    await page.getByRole("button", { name: /войти/i }).click();

    // Ждём редиректа на /admin/events
    await expect(page).toHaveURL(/\/admin\/events/);

    // Шаг 1: Нажать «Создать событие»
    await page.getByRole("link", { name: /создать событие/i }).click();
    await expect(page).toHaveURL(/\/admin\/events\/new/);

    // Шаг 2: Заполнить основную информацию
    await page.getByLabel(/название/i).fill("E2E Test Event");
    // Slug должен автосгенерироваться
    const slugInput = page.getByLabel(/slug/i);
    await expect(slugInput).not.toHaveValue("");
    await page.getByLabel(/описание/i).fill("Описание тестового события");
    await page.getByLabel(/место проведения/i).fill("Тестовый ресторан");
    await page.getByLabel(/адрес/i).fill("ул. Тестовая, д. 1");

    // Выбрать тип расписания single
    await page.getByLabel(/начало/i).fill("2026-12-31T20:00");
    await page.getByLabel(/окончание/i).fill("2027-01-01T03:00");

    // Перейти на шаг 2
    await page.getByRole("button", { name: /далее/i }).click();

    // Шаг 3: Добавить тариф
    await page.getByRole("button", { name: /добавить тариф/i }).click();
    await page.getByLabel(/название тарифа/i).fill("Standard");
    await page.getByLabel(/цена/i).fill("2000");
    await page.getByLabel(/лимит мест/i).fill("100");

    // Перейти на шаг 3
    await page.getByRole("button", { name: /далее/i }).click();

    // Шаг 4: Кастомные поля (опционально, пропускаем)
    // Перейти к отправке
    await page.getByRole("button", { name: /далее/i }).click();

    // Шаг 5: Отправить на модерацию
    await page.getByRole("button", { name: /отправить на модерацию/i }).click();

    // Проверить что вернулись к списку событий
    await expect(page).toHaveURL(/\/admin\/events/);

    // Проверить что событие появилось в списке
    await expect(page.getByText("E2E Test Event")).toBeVisible();

    // Проверить статус (pending_moderation или published — зависит от auto_publish)
    const statusBadge = page.getByText(/на модерации|опубликовано/i);
    await expect(statusBadge).toBeVisible();
  });

  test("organizer saves event as draft", async ({ page }) => {
    // Логин
    await page.goto("/admin/login");
    await page.getByLabel(/email/i).fill("organizer@test-org.example.com");
    await page.getByLabel(/пароль/i).fill("Organizer123!");
    await page.getByRole("button", { name: /войти/i }).click();
    await expect(page).toHaveURL(/\/admin\/events/);

    // Создать событие
    await page.getByRole("link", { name: /создать событие/i }).click();

    // Заполнить минимум
    await page.getByLabel(/название/i).fill("Draft Event");
    await page.getByLabel(/начало/i).fill("2026-12-31T20:00");
    await page.getByLabel(/окончание/i).fill("2027-01-01T03:00");

    // Сохранить черновик
    await page.getByRole("button", { name: /сохранить черновик/i }).click();

    // Проверить что вернулись к списку
    await expect(page).toHaveURL(/\/admin\/events/);

    // Проверить что событие в статусе draft
    await expect(page.getByText("Draft Event")).toBeVisible();
    await expect(page.getByText(/черновик/i)).toBeVisible();
  });
});