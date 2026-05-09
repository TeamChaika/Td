/**
 * Unit/component тесты EventWizard (админский wizard создания события).
 *
 * Ожидает реализацию coder-frontend (3b):
 * - features/events/event-wizard или app/admin/events/new
 *
 * Все тесты помечены skip до готовности 3b.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ---------------------------------------------------------------------------
// Заглушка компонента — будет заменена на реальный импорт из 3b
// ---------------------------------------------------------------------------

// import { EventWizard } from '@/features/events/event-wizard';

// Временная заглушка для компиляции
const EventWizard = (_props: Record<string, unknown>) => null;

// ---------------------------------------------------------------------------
// Тесты
// ---------------------------------------------------------------------------

describe.skip('EventWizard', () => {
  describe('Step 1 — Basic Info', () => {
    it('validates title is required', async () => {
      // render(<EventWizard />);
      // const nextButton = screen.getByRole('button', { name: /далее/i });
      // await userEvent.click(nextButton);
      // expect(screen.getByText(/название обязательно/i)).toBeInTheDocument();
      expect(true).toBe(true);
    });

    it('validates slug pattern (latin, dashes)', async () => {
      // render(<EventWizard />);
      // const slugInput = screen.getByLabelText(/slug/i);
      // await userEvent.type(slugInput, 'русский слаг!');
      // const nextButton = screen.getByRole('button', { name: /далее/i });
      // await userEvent.click(nextButton);
      // expect(screen.getByText(/только латиница/i)).toBeInTheDocument();
      expect(true).toBe(true);
    });

    it('auto-generates slug from title', async () => {
      // render(<EventWizard />);
      // const titleInput = screen.getByLabelText(/название/i);
      // await userEvent.type(titleInput, 'Новый год 2026');
      // const slugInput = screen.getByLabelText(/slug/i);
      // expect(slugInput).toHaveValue('novyj-god-2026');
      expect(true).toBe(true);
    });

    it('allows manual slug override', async () => {
      // render(<EventWizard />);
      // const slugInput = screen.getByLabelText(/slug/i);
      // await userEvent.clear(slugInput);
      // await userEvent.type(slugInput, 'my-custom-slug');
      // expect(slugInput).toHaveValue('my-custom-slug');
      expect(true).toBe(true);
    });
  });

  describe('Step 2 — Tariffs & Capacity', () => {
    it('capacity_policy=per_tariff makes capacity_limit required on tariffs', async () => {
      // render(<EventWizard />);
      // Выбрать per_tariff
      // Добавить тариф без capacity_limit
      // Проверить ошибку валидации
      expect(true).toBe(true);
    });

    it('at least one tariff is required', async () => {
      // render(<EventWizard />);
      // Перейти на шаг 2
      // Удалить все тарифы
      // Нажать далее
      // Проверить ошибку «нужен хотя бы один тариф»
      expect(true).toBe(true);
    });

    it('tariff price must be >= 0', async () => {
      // render(<EventWizard />);
      // Добавить тариф с отрицательной ценой
      // Проверить ошибку валидации
      expect(true).toBe(true);
    });
  });

  describe('Step 3 — Custom Fields', () => {
    it('max 10 custom fields', async () => {
      // render(<EventWizard />);
      // Добавить 11 полей
      // Проверить что кнопка «добавить поле» заблокирована
      // или появляется ошибка
      expect(true).toBe(true);
    });

    it('custom field id must be unique', async () => {
      // render(<EventWizard />);
      // Добавить два поля с одинаковым id
      // Проверить ошибку валидации
      expect(true).toBe(true);
    });

    it('select type requires options', async () => {
      // render(<EventWizard />);
      // Добавить поле типа select без options
      // Проверить ошибку валидации
      expect(true).toBe(true);
    });
  });

  describe('Navigation', () => {
    it('back/forward preserves state', async () => {
      // render(<EventWizard />);
      // Заполнить шаг 1
      // Перейти на шаг 2
      // Вернуться на шаг 1
      // Проверить что данные сохранились
      expect(true).toBe(true);
    });

    it('submit sends all steps in one POST', async () => {
      // render(<EventWizard />);
      // Заполнить все шаги
      // Нажать «Отправить»
      // Проверить что был один POST с полными данными
      expect(true).toBe(true);
    });

    it('save draft works from any step', async () => {
      // render(<EventWizard />);
      // На шаге 1 нажать «Сохранить черновик»
      // Проверить что событие создано со статусом draft
      expect(true).toBe(true);
    });
  });
});