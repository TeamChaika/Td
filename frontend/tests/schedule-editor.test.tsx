/**
 * Unit/component тесты ScheduleEditor.
 *
 * Ожидает реализацию coder-frontend (3b):
 * - components/ScheduleEditor или features/events/schedule-editor
 *
 * Все тесты помечены skip до готовности 3b.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ---------------------------------------------------------------------------
// Заглушка компонента — будет заменена на реальный импорт из 3b
// ---------------------------------------------------------------------------

// import { ScheduleEditor } from '@/features/events/schedule-editor';

// Временная заглушка для компиляции
const ScheduleEditor = (_props: Record<string, unknown>) => null;

// ---------------------------------------------------------------------------
// Тесты
// ---------------------------------------------------------------------------

describe.skip('ScheduleEditor', () => {
  describe('Type switching', () => {
    it('renders single schedule fields by default', () => {
      // render(<ScheduleEditor />);
      // expect(screen.getByLabelText(/начало/i)).toBeInTheDocument();
      // expect(screen.getByLabelText(/окончание/i)).toBeInTheDocument();
      expect(true).toBe(true);
    });

    it('switches to sessions type', async () => {
      // render(<ScheduleEditor />);
      // const sessionsRadio = screen.getByLabelText(/несколько сеансов/i);
      // await userEvent.click(sessionsRadio);
      // expect(screen.getByText(/добавить сеанс/i)).toBeInTheDocument();
      expect(true).toBe(true);
    });

    it('switches to period type', async () => {
      // render(<ScheduleEditor />);
      // const periodRadio = screen.getByLabelText(/период/i);
      // await userEvent.click(periodRadio);
      // expect(screen.getByLabelText(/начало периода/i)).toBeInTheDocument();
      // expect(screen.getByLabelText(/конец периода/i)).toBeInTheDocument();
      expect(true).toBe(true);
    });

    it('switches back to single type preserving data', async () => {
      // render(<ScheduleEditor />);
      // Заполнить single
      // Переключить на sessions
      // Переключить обратно на single
      // Проверить что данные single сохранились
      expect(true).toBe(true);
    });
  });

  describe('Validation', () => {
    it('validates end > start for single', async () => {
      // render(<ScheduleEditor />);
      // Ввести end < start
      // Проверить ошибку валидации
      expect(true).toBe(true);
    });

    it('validates end > start for period', async () => {
      // render(<ScheduleEditor />);
      // Переключить на period
      // Ввести end < start
      // Проверить ошибку валидации
      expect(true).toBe(true);
    });

    it('validates end > start for each session', async () => {
      // render(<ScheduleEditor />);
      // Переключить на sessions
      // Добавить сеанс с end < start
      // Проверить ошибку валидации
      expect(true).toBe(true);
    });

    it('validates at least one session required', async () => {
      // render(<ScheduleEditor />);
      // Переключить на sessions
      // Удалить все сеансы
      // Проверить ошибку «нужен хотя бы один сеанс»
      expect(true).toBe(true);
    });

    it('validates dates not in the past', async () => {
      // render(<ScheduleEditor />);
      // Ввести дату в прошлом
      // Проверить предупреждение или ошибку
      expect(true).toBe(true);
    });
  });

  describe('Sessions management', () => {
    it('adds a new session', async () => {
      // render(<ScheduleEditor />);
      // Переключить на sessions
      // Нажать «Добавить сеанс»
      // Проверить что появился новый блок с полями дат
      expect(true).toBe(true);
    });

    it('removes a session', async () => {
      // render(<ScheduleEditor />);
      // Переключить на sessions
      // Добавить сеанс
      // Нажать «Удалить» на сеансе
      // Проверить что сеанс исчез
      expect(true).toBe(true);
    });
  });
});