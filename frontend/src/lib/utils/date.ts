/**
 * Форматирование дат с русской локалью.
 * Для тяжёлых операций использовать date-fns напрямую.
 */
import { format, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale';

/** Форматировать ISO-строку по паттерну date-fns (русская локаль). */
export function formatDate(iso: string | null | undefined, pattern = 'd MMMM yyyy'): string {
  if (!iso) return '';
  try {
    return format(parseISO(iso), pattern, { locale: ru });
  } catch {
    return '';
  }
}

/** Дата + время: `15 июня 2026, 19:00`. */
export function formatDateTime(iso: string | null | undefined): string {
  return formatDate(iso, "d MMMM yyyy, HH:mm");
}

/** Только время: `19:00`. */
export function formatTime(iso: string | null | undefined): string {
  return formatDate(iso, 'HH:mm');
}

/** Короткая дата: `15.06.2026`. */
export function formatShortDate(iso: string | null | undefined): string {
  return formatDate(iso, 'dd.MM.yyyy');
}
