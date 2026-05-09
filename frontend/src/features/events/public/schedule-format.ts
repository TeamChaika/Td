/**
 * Форматирование расписания события для отображения.
 * Работает с EventSchedule — discriminated union (синхронизирован с backend).
 */
import { format, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale';
import type { EventSchedule } from '@/types/api';

/** Форматировать ISO-строку в читаемую дату */
function fmt(iso: string, pattern: string): string {
  try {
    return format(parseISO(iso), pattern, { locale: ru });
  } catch {
    return iso;
  }
}

/**
 * Человекочитаемое представление расписания.
 * - single: "31 декабря 2025, 21:00"
 * - period: "15–17 августа 2026"
 * - sessions: "11, 18, 25 января 2026"
 */
export function formatSchedule(schedule: EventSchedule): string {
  switch (schedule.type) {
    case 'single':
      return fmt(schedule.starts_at, "d MMMM yyyy, HH:mm");

    case 'period': {
      const start = parseISO(schedule.starts_at);
      const end = parseISO(schedule.ends_at);
      const sameMonth = start.getMonth() === end.getMonth();
      const sameYear = start.getFullYear() === end.getFullYear();

      if (sameMonth && sameYear) {
        return `${fmt(schedule.starts_at, 'd')}–${fmt(schedule.ends_at, 'd MMMM yyyy')}`;
      }
      if (sameYear) {
        return `${fmt(schedule.starts_at, 'd MMMM')} – ${fmt(schedule.ends_at, 'd MMMM yyyy')}`;
      }
      return `${fmt(schedule.starts_at, 'd MMMM yyyy')} – ${fmt(schedule.ends_at, 'd MMMM yyyy')}`;
    }

    case 'sessions': {
      if (schedule.sessions.length === 0) return '';
      const first = schedule.sessions[0];
      if (!first) return '';
      const dates = schedule.sessions.map((s) => fmt(s.starts_at, 'd MMMM'));
      const year = fmt(first.starts_at, 'yyyy');
      return `${dates.join(', ')} ${year}`;
    }
  }
}

/**
 * Краткое представление для карточки.
 * - single: "31 декабря, 21:00"
 * - period: "15–17 августа"
 * - sessions: "3 сессии с 11 января"
 */
export function formatScheduleShort(schedule: EventSchedule): string {
  switch (schedule.type) {
    case 'single':
      return fmt(schedule.starts_at, "d MMMM, HH:mm");

    case 'period':
      return `${fmt(schedule.starts_at, 'd')}–${fmt(schedule.ends_at, 'd MMMM')}`;

    case 'sessions': {
      const count = schedule.sessions.length;
      const firstDate = schedule.sessions[0]
        ? fmt(schedule.sessions[0].starts_at, 'd MMMM')
        : '';
      return `${count} ${pluralizeSession(count)} с ${firstDate}`;
    }
  }
}

function pluralizeSession(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return 'сессия';
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return 'сессии';
  return 'сессий';
}